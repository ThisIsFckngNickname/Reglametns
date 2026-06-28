# Phase 5 B1: RAG-enhanced Generator + PromptBuilder V2 Specification

> **Проект:** SRP (Service for Regulations and Policies)
> **Фаза:** 5 / Инкремент B1 — RAG-enhanced генератор
> **Дата:** 2026-06-28
> **Статус:** Черновик (готов к реализации)
> **Аудитория:** BE (Python/FastAPI), FE (React/TypeScript)

---

## Оглавление

1. [Контекст и цель](#1-контекст-и-цель)
2. [Формат супер-промпта (PromptBuilder V2)](#2-формат-супер-промпта-promptbuilder-v2)
   - 2.1 Системный промпт
   - 2.2 Пользовательский промпт
   - 2.3 Секции промпта
   - 2.4 Пример собранного промпта
3. [Порядок сбора контекста](#3-порядок-сбора-контекста)
   - 3.1 Pipeline сбора
   - 3.2 Token budget distribution
   - 3.3 Обработка ошибок при сборе
4. [Интеграция с существующим GeneratorService](#4-интеграция-с-существующим-generatorservice)
   - 4.1 GeneratorService V2 — новый метод
   - 4.2 DataLoader — загрузка CompanyTerm/CompanyAbbreviation
   - 4.3 PromptBuilder V2 — изменения
5. [Document type registry](#5-document-type-registry)
6. [Последовательность вызовов](#6-последовательность-вызовов)
7. [Контракты методов](#7-контракты-методов)

---

## 1. Контекст и цель

### 1.1 Текущее состояние

В Phase 1 был реализован базовый `GeneratorService` с:

- `PromptBuilder` — собирает системный + пользовательский промпт из: профиля компании, терминов из `DocumentTerm`, влияющих документов, стилевых паттернов, RAG chunks и веб-результатов
- `GeneratorService.generate()` — собирает контекст, зовёт LLM, парсит ответ, строит .docx, сохраняет документ
- `POST /api/v1/generator/generate` — endpoint с `multipart/form-data` (context + draft_files + influencing_document_ids)

### 1.2 Проблемы текущей реализации

1. **Термины загружаются только из `document_terms`** (привязаны к конкретным документам), нет общехолдингового перечня
2. **Нет типа документа** — структура промпта не зависит от типа (regulation/order/provision/policy/directive)
3. **Нет черновика как файла** — поддерживаются только `UploadFile` через multipart, нет загрузки по ID
4. **Веб-поиск опциональный** — выключается через settings, а должен быть обязательным
5. **Промпт не содержит ссылок на связанные документы** (document_links)

### 1.3 Цель B1

Создать V2 генератора, где:

- PromptBuilder собирает супер-промпт из 6 источников
- GeneratorService имеет новый метод `generate_document()` с полным набором параметров
- Тип документа влияет на структуру промпта
- Черновик можно загрузить как файл или указать ID ранее загруженного
- Веб-поиск — обязательный шаг (graceful degradation при ошибках)

---

## 2. Формат супер-промпта (PromptBuilder V2)

### 2.1 Архитектура

`PromptBuilderV2` — новый класс (или значительное расширение существующего `PromptBuilder`), который собирает промпт из 6 источников:

```
Источники:
1. Структура документа (из company.document_structure)
2. Термины холдинга (CompanyTerm) + сокращения (CompanyAbbreviation)
3. Похожие документы (ChromaDB через RagService.search, top-k=5)
4. Информация из интернета (WebSearchService.enrich_prompt)
5. Черновик пользователя (текст, извлечённый из загруженного файла)
6. Влияющие документы (Document с full_text из latest_version)
```

**Token budget distribution:**

```
Общий бюджет: generation_max_prompt_tokens (28000)

Распределение:
- Системный промпт (шаблон):        ~500 tokens  (фикс)
- Структура документа:               ~200 tokens  (фикс)
- Термины холдинга:                  ~2000 tokens (макс 50 терминов × 40 tok)
- Сокращения холдинга:               ~500 tokens  (макс 20 сокращений × 25 tok)
- Похожие документы (ChromaDB):      ~3000 tokens (5 чанков × 600 tok)
- Информация из интернета:           ~2000 tokens (3 результата × ~650 tok)
- Пользовательский промпт (шаблон):  ~300 tokens  (фикс)
- Черновик пользователя:             ~10000 tokens (пропорционально)
- Влияющие документы:                ~7500 tokens (пропорционально)
- Резерв:                            ~2000 tokens
```

Если фактические данные превышают бюджет — применяется пропорциональное усечение (как сейчас `_distribute_token_budget`).

### 2.2 Системный промпт (V2)

```
СИСТЕМНЫЙ ПРОМПТ:
Ты — юрист холдинга «{company.name}» ({company.legal_form}).
Составляй официальные corporate documents на русском языке.

СТРУКТУРА ДОКУМЕНТА (тип: {document_type_label}):
{structure_text}

ТЕРМИНЫ ХОЛДИНГА (обязательны к использованию):
{terms_text}

СОКРАЩЕНИЯ ХОЛДИНГА:
{abbreviations_text}

ПОХОЖИЕ ДОКУМЕНТЫ (из базы знаний холдинга):
{similar_chunks_text}

ИНФОРМАЦИЯ ИЗ ИНТЕРНЕТА (актуальное законодательство, практики):
{web_results_text}

ВЛИЯЮЩИЕ ДОКУМЕНТЫ:
{influencing_docs_text}

Требования к документу:
1. Строгая нумерация разделов и пунктов
2. Используй термины холдинга без искажения
3. Если нужен новый термин — добавь его в раздел "Термины и определения" 
   с пометкой [НОВЫЙ]
4. Ссылайся на внутренние документы холдинга, если релевантно
5. Ссылайся на законодательство, если релевантно
6. Каждый раздел: 3-7 пунктов, полное раскрытие темы
7. Ответ ТОЛЬКО в формате JSON (без markdown-обертки)
```

### 2.3 Пользовательский промпт (V2)

```
ЧЕРНОВИК ПОЛЬЗОВАТЕЛЯ (используй как основу, дополни и структурируй):
{draft_text}

Тема документа: {topic}
Тип документа: {document_type_label}

На основе черновика (в первую очередь) и темы сгенерируй документ.
Сохрани структуру, терминологию и содержание черновика.
Раскрой и детализируй каждый раздел.

Формат ответа (строго JSON, без markdown-обертки):
{
  "title": "Название документа",
  "description": "Краткое описание",
  "sections": [
    {
      "title": "1. Название раздела",
      "level": 1,
      "content": "Текст раздела...",
      "subsections": [
        {
          "title": "1.1. Название подраздела",
          "level": 2,
          "content": "Текст..."
        }
      ]
    }
  ],
  "terms": [{"term": "...", "definition": "..."}],
  "abbreviations": [{"abbreviation": "...", "full_form": "..."}],
  "references": [{"title": "...", "source": "..."}]
}
```

### 2.4 Форматирование секций промпта

#### 2.4.1 Структура документа (structure_text)

Берётся из `company.document_structure`. Если поле — строка, используется как есть. Если JSON-объект — сериализуется с отступами.

Для разных `document_type` может быть разная структура. На MVP: company.document_structure — единый для всех типов. В B2 будет разделение по типам.

```python
def _format_structure(company: Company, document_type: str) -> str:
    if company.document_structure:
        if isinstance(company.document_structure, str):
            return company.document_structure
        return json.dumps(company.document_structure, ensure_ascii=False, indent=2)
    return "Стандартная структура документа."
```

#### 2.4.2 Термины холдинга (terms_text)

Из `CompanyTerm` для данной компании. Формат:

```
- {term}: {definition}
- {term}: {definition}
...

Если терминов нет: "Термины холдинга не определены."
```

Лимит: максимум 50 терминов (если больше — первые 50 по алфавиту + пометка "и ещё N терминов").

#### 2.4.3 Сокращения холдинга (abbreviations_text)

Аналогично из `CompanyAbbreviation`. Формат:

```
- {abbreviation} — {full_form}
- {abbreviation} — {full_form}
...

Если сокращений нет: "Сокращения холдинга не определены."
```

Лимит: максимум 20 сокращений.

#### 2.4.4 Похожие документы (similar_chunks_text)

Из ChromaDB через `RagService.search(query=topic, company_id=company_id, top_k=5)`. Формат:

```
Фрагмент 1 (из: "Регламент по ..."):
    {text[:600]}

Фрагмент 2 (из: "Политика по ..."):
    {text[:600]}
...

Если чанков нет: "Похожие документы не найдены."
```

#### 2.4.5 Информация из интернета (web_results_text)

Из `WebSearchService.enrich_prompt(topic)`. Формат:

```
Источник 1: {title}
    {extracted_text[:500]}
    URL: {url}

Источник 2: ...
```

#### 2.4.6 Влияющие документы (influencing_docs_text)

Из `DataLoader.load_influencing_documents()`. Формат:

```
- {title} (Внутренний документ)
    Содержание: {full_text[:2000]}
```

Лимит: `_MAX_INFLUENCING_TEXT_CHARS = 10000` на документ.

---

## 3. Порядок сбора контекста

### 3.1 Pipeline сбора для generate_document()

```
1. Загрузить company (data_loader.load_company)
   → company_id, company.name, company.legal_form, company.document_structure

2. Загрузить CompanyTerm (новая функция data_loader.load_company_terms_list)
   → list[{"term": str, "definition": str}]

3. Загрузить CompanyAbbreviation (новая функция data_loader.load_company_abbreviations_list)
   → list[{"abbreviation": str, "full_form": str}]

4. Поиск по ChromaDB (rag_service.search)
   → query=topic, company_id=company_id, top_k=5
   → list[{"text": str, "title": str, "document_id": int}]

5. Веб-поиск (web_search_service.enrich_prompt)
   → topic=topic, max_results=5
   → str (отформатированный текст для промпта)
   → при ошибке: None (генерация продолжается)

6. Извлечение текста черновика (text_extractor.extract_draft_text)
   → если draft_file_id указан: загрузить файл из storage, извлечь текст
   → str | ""

7. Загрузка влияющих документов (data_loader.load_influencing_documents)
   → list[{"title": str, "source": str, "full_text": str}]
```

### 3.2 Token budget distribution

Механизм наследуется из существующего `_distribute_token_budget` и `_truncate_by_paragraphs` в `generator_service.py`.

**Изменения для V2:**

```python
def _distribute_v2_budget(
    context: GenerationContext,
    total_budget_tokens: int = 28000,
) -> GenerationContext:
    """
    Distribute token budget across all prompt sections.
    
    Fixed-cost sections first, then proportional distribution
    for variable sections (draft, influencing docs).
    """
    fixed_sections = {
        "system_prompt": 500,
        "structure": 200,
        "terms": min(2000, _estimate_tokens(context.terms_text)),
        "abbreviations": min(500, _estimate_tokens(context.abbreviations_text)),
        "similar_chunks": min(3000, _estimate_tokens(context.similar_chunks_text)),
        "web_results": min(2000, _estimate_tokens(context.web_results_text or "")),
        "user_prompt": 300,
        "reserve": 2000,
    }
    
    fixed_total = sum(fixed_sections.values())
    remaining = total_budget_tokens * _CHARS_PER_TOKEN - fixed_total * _CHARS_PER_TOKEN
    
    # Proportional distribution for draft + influencing docs
    total_variable = len(context.draft_text) + sum(
        len(d.get("full_text", "")) for d in context.influencing_docs
    )
    if total_variable > 0 and remaining > 0:
        draft_budget = int(remaining * len(context.draft_text) / total_variable)
        doc_budget_per = max(500, int(
            remaining * sum(len(d.get("full_text", "")) for d in context.influencing_docs) 
            / total_variable / max(len(context.influencing_docs), 1)
        ))
        
        context.draft_text = _truncate_by_paragraphs(context.draft_text, draft_budget)
        for doc in context.influencing_docs:
            if "full_text" in doc:
                doc["full_text"] = _truncate_by_paragraphs(
                    doc["full_text"], doc_budget_per
                )
    
    return context
```

### 3.3 Обработка ошибок при сборе

| Шаг | Действие при ошибке |
|-----|-------------------|
| Загрузка company | Исключение (не можем генерировать без холдинга) |
| Загрузка CompanyTerm | Пустой список, логирование |
| Загрузка CompanyAbbreviation | Пустой список, логирование |
| ChromaDB search | Пустой список, логирование |
| Веб-поиск | None (пропуск блока), логирование |
| Извлечение черновика | Пустая строка, логирование |
| Загрузка влияющих документов | Пустой список, логирование |

---

## 4. Интеграция с существующим GeneratorService

### 4.1 GeneratorService V2 — новый метод generate_document()

Существующий `generate()` сохраняется для обратной совместимости (Phase 1 API).

Новый метод:

```python
class GeneratorService:
    """V2 — RAG-enhanced generator with full context collection."""
    
    async def generate_document(
        self,
        topic: str,
        company_id: int,
        document_type: str = "regulation",  # regulation | order | provision | policy | directive
        user_id: int | None = None,
        draft_file_path: str | None = None,
        influence_document_ids: list[int] | None = None,
        search_enabled: bool = True,
        db: AsyncSession | None = None,
    ) -> DocumentResponse:
        """Generate a document using all available knowledge sources.
        
        Pipeline:
        1. Collect context (6 sources)
        2. Build prompt (PromptBuilder V2)
        3. Call LLM
        4. Parse response
        5. Build .docx
        6. Save document
        """
        ...
```

**GenerationContext dataclass:**

```python
@dataclass
class GenerationContext:
    topic: str
    document_type: str
    company: Company
    company_terms: list[dict]          # From CompanyTerm
    company_abbreviations: list[dict]  # From CompanyAbbreviation
    similar_chunks: list[dict]         # From ChromaDB
    web_results_text: str | None       # From WebSearchService
    draft_text: str                    # Extracted from draft file
    influencing_docs: list[dict]       # Influencing documents
```

### 4.2 DataLoader — новые методы

```python
class DataLoader:
    # Существующие методы:
    # - load_company(company_id, db) -> Company
    # - load_influencing_documents(document_ids, company_id, db) -> list[dict]
    # - load_company_terms(company_id, db) -> list[dict]  (из DocumentTerm)
    
    # НОВЫЕ методы:
    
    async def load_company_terms_list(
        self, company_id: int, db: AsyncSession
    ) -> list[dict]:
        """Load terms from CompanyTerm table (holding-wide)."""
        ...
    
    async def load_company_abbreviations_list(
        self, company_id: int, db: AsyncSession
    ) -> list[dict]:
        """Load abbreviations from CompanyAbbreviation table (holding-wide)."""
        ...
    
    async def load_draft_text(
        self, draft_file_path: str | None
    ) -> str:
        """Load draft text from file path."""
        ...
```

**Важно:** Существующий метод `load_company_terms()` грузит термины из `DocumentTerm` (привязаны к документам). Новый метод `load_company_terms_list()` грузит из `CompanyTerm` (общехолдинговый перечень). В V2 промпта используются **оба** источника: общехолдинговые термины как обязательные, термины конкретного документа как дополнительные.

### 4.3 PromptBuilder V2 — изменения

```python
class PromptBuilder:
    """V2 — builds super-prompt from 6 knowledge sources."""
    
    def build_messages_v2(
        self,
        context: GenerationContext,
    ) -> list[dict]:
        """Build system + user messages for LLM using V2 prompt format.
        
        Args:
            context: Fully populated GenerationContext.
        
        Returns:
            List of message dicts compatible with LLM API.
        """
        system_prompt = self._build_system_prompt_v2(context)
        user_prompt = self._build_user_prompt_v2(context)
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    
    def _build_system_prompt_v2(self, context: GenerationContext) -> str:
        """Build V2 system prompt with all knowledge sources."""
        ...
    
    def _build_user_prompt_v2(self, context: GenerationContext) -> str:
        """Build V2 user prompt with draft + topic."""
        ...
    
    # ── Formatters ──────────────────────────────────────
    
    def _format_terms_table(self, terms: list[dict]) -> str: ...
    def _format_abbreviations_table(self, abbreviations: list[dict]) -> str: ...
    def _format_similar_chunks(self, chunks: list[dict]) -> str: ...
    def _format_web_results(self, web_text: str | None) -> str: ...
    def _format_structure(self, company: Company, doc_type: str) -> str: ...
    def _format_influencing_docs(self, docs: list[dict]) -> str: ...
```

---

## 5. Document type registry

На MVP (B1) типы документов хранятся как константа, без модели в БД:

```python
DOCUMENT_TYPES = {
    "regulation": {
        "label": "Регламент",
        "description": "Нормативный документ, устанавливающий правила, процедуры и ответственность",
        "default_structure": "1. Общие положения\n2. Термины и определения\n3. Порядок выполнения\n4. Заключительные положения",
    },
    "order": {
        "label": "Приказ",
        "description": "Распорядительный документ руководителя",
        "default_structure": "1. Общие положения\n2. Приказываю\n3. Контроль исполнения",
    },
    "provision": {
        "label": "Положение",
        "description": "Нормативный документ, определяющий статус, цели, задачи и функции",
        "default_structure": "1. Общие положения\n2. Цели и задачи\n3. Функции и права\n4. Ответственность\n5. Заключительные положения",
    },
    "policy": {
        "label": "Политика",
        "description": "Документ, определяющий принципы и правила в определённой области",
        "default_structure": "1. Общие положения\n2. Принципы\n3. Правила и процедуры\n4. Мониторинг и контроль\n5. Заключительные положения",
    },
    "directive": {
        "label": "Распоряжение",
        "description": "Оперативный распорядительный документ",
        "default_structure": "1. Основание\n2. Распорядительная часть\n3. Контроль исполнения",
    },
}
```

В B2 будет добавлена модель `DocumentType` в БД.

---

## 6. Последовательность вызовов

```
Client                  API Gateway              GeneratorService                 LLM
  │                         │                        │                            │
  │ POST /generator/generate │                        │                            │
  │ (JSON body V2)          │                        │                            │
  │────────────────────────►│                        │                            │
  │                         │  verify JWT, company   │                            │
  │                         │───────────────────────►│                            │
  │                         │                        │                            │
  │                         │  ── Collect context ── │                            │
  │                         │                        │                            │
  │                         │  1. Load Company       │                            │
  │                         │  2. Load CompanyTerm   │                            │
  │                         │  3. Load CompanyAbbr   │                            │
  │                         │  4. ChromaDB search    │                            │
  │                         │  5. Web search         │                            │
  │                         │  6. Extract draft      │                            │
  │                         │  7. Load influencing   │                            │
  │                         │                        │                            │
  │                         │  ── Distribute budget ─│                            │
  │                         │                        │                            │
  │                         │  ── Build prompt ───── │                            │
  │                         │                        │                            │
  │                         │  ── Call LLM ─────────────────────────────────────►│
  │                         │                        │                            │
  │                         │◄──── response ─────────────────────────────────────│
  │                         │                        │                            │
  │                         │  ── Parse response ─── │                            │
  │                         │  ── Build .docx ────── │                            │
  │                         │  ── Save document ──── │                            │
  │                         │                        │                            │
  │◄─── DocumentResponse ───│                        │                            │
```

---

## 7. Контракты методов

### 7.1 GeneratorService.generate_document()

```python
async def generate_document(
    self,
    topic: str,
    company_id: int,
    document_type: str = "regulation",
    user_id: int | None = None,
    draft_file_path: str | None = None,
    influence_document_ids: list[int] | None = None,
    search_enabled: bool = True,
    db: AsyncSession | None = None,
) -> DocumentResponse:
    """Generate a document using all available knowledge sources.
    
    Args:
        topic: Document topic (e.g. "Регламент по ГСМ").
        company_id: Company (holding) ID.
        document_type: Document type key from DOCUMENT_TYPES.
        user_id: Creator user ID (optional, for audit).
        draft_file_path: Path to draft file in storage (optional).
        influence_document_ids: IDs of influencing documents (optional).
        search_enabled: Enable web search (default True).
        db: Database session.
    
    Returns:
        DocumentResponse with generated document metadata.
    
    Raises:
        BadRequestException: If topic is empty or company not found.
        LLMException: If LLM call fails (after retries).
    """
```

### 7.2 PromptBuilder.build_messages_v2()

```python
def build_messages_v2(
    self,
    context: GenerationContext,
) -> list[dict]:
    """Build V2 system + user messages.
    
    Args:
        context: Populated GenerationContext with all 6 sources.
    
    Returns:
        [{"role": "system", "content": str},
         {"role": "user", "content": str}]
    """
```

### 7.3 DataLoader — новые методы

```python
async def load_company_terms_list(
    self, company_id: int, db: AsyncSession
) -> list[dict]:
    """Load holding-wide terms from CompanyTerm.
    
    Returns:
        [{"term": str, "definition": str, "source_document_id": int|None,
          "is_manual": bool}, ...]
    """

async def load_company_abbreviations_list(
    self, company_id: int, db: AsyncSession
) -> list[dict]:
    """Load holding-wide abbreviations from CompanyAbbreviation.
    
    Returns:
        [{"abbreviation": str, "full_form": str, "source_document_id": int|None,
          "is_manual": bool}, ...]
    """

async def load_draft_text(
    self, draft_file_path: str | None
) -> str:
    """Load draft text from a file path.
    
    If path is None, returns empty string.
    Supports .txt and .docx files.
    """
```

### 7.4 GenerationContext dataclass

```python
@dataclass
class GenerationContext:
    """All context needed for V2 prompt building."""
    topic: str
    document_type: str
    company: Company
    company_terms: list[dict]
    company_abbreviations: list[dict]
    similar_chunks: list[dict]
    web_results_text: str | None
    draft_text: str
    influencing_docs: list[dict]
    
    @property
    def document_type_label(self) -> str:
        """Human-readable document type label."""
        return DOCUMENT_TYPES.get(
            self.document_type, {}
        ).get("label", self.document_type)
    
    @property
    def terms_text(self) -> str:
        """Formatted terms table for prompt."""
        ...
    
    @property 
    def abbreviations_text(self) -> str:
        """Formatted abbreviations table for prompt."""
        ...
    
    @property
    def similar_chunks_text(self) -> str:
        """Formatted similar chunks for prompt."""
        ...
    
    @property
    def web_results_text_safe(self) -> str:
        """Web results text or empty placeholder."""
        return self.web_results_text or "Поиск в интернете не выполнялся или недоступен."
    
    @property
    def structure_text(self) -> str:
        """Formatted document structure for prompt."""
        ...
```

---

## Приложение A: Пример собранного промпта (V2)

```
СИСТЕМНЫЙ ПРОМПТ:
Ты — юрист холдинга «АКМЭ-Инжиниринг» (ООО).
Составляй официальные corporate documents на русском языке.

СТРУКТУРА ДОКУМЕНТА (тип: Регламент):
1. Общие положения
2. Термины и определения
3. Порядок выполнения
4. Заключительные положения

ТЕРМИНЫ ХОЛДИНГА (обязательны к использованию):
  - ГСМ: горюче-смазочные материалы, включая бензин, дизельное топливо, масла и смазки
  - Ответственное лицо: сотрудник, назначенный приказом руководителя структурного подразделения
  - Учётная единица: единица измерения, принятая в системе учёта холдинга

СОКРАЩЕНИЯ ХОЛДИНГА:
  - ГСМ — горюче-смазочные материалы
  - МОЛ — материально-ответственное лицо
  - ERP — система управления ресурсами предприятия

ПОХОЖИЕ ДОКУМЕНТЫ (из базы знаний холдинга):
  Фрагмент 1 (из: "Регламент по учёту ТМЦ"):
    Настоящий регламент устанавливает порядок учёта товарно-материальных ценностей...
  Фрагмент 2 (из: "Политика по ГСМ"):
    3.1. Ответственное лицо назначается приказом руководителя...

ИНФОРМАЦИЯ ИЗ ИНТЕРНЕТА (актуальное законодательство, практики):
  Источник 1: Приказ Минтранса РФ от 11.08.2020 № 286
    Нормы расхода топлива и смазочных материалов на автомобильном транспорте...
    URL: https://www.consultant.ru/document/cons_doc_LAW_12345/

ВЛИЯЮЩИЕ ДОКУМЕНТЫ:
  - Регламент по учёту ТМЦ (Внутренний документ)
    Содержание: ...

Требования к документу:
1. Строгая нумерация разделов и пунктов
2. Используй термины холдинга без искажения
3. Если нужен новый термин — добавь его в раздел "Термины и определения" 
   с пометкой [НОВЫЙ]
4. Ссылайся на внутренние документы холдинга, если релевантно
5. Ссылайся на законодательство, если релевантно

=== ПОЛЬЗОВАТЕЛЬСКИЙ ПРОМПТ ===

ЧЕРНОВИК ПОЛЬЗОВАТЕЛЯ (используй как основу, дополни и структурируй):

1. Общие положения
1.1. Настоящий регламент определяет порядок приобретения, учёта и списания ГСМ...

Тема документа: Регламент по ГСМ
Тип документа: Регламент

На основе черновика и темы сгенерируй документ...
```
