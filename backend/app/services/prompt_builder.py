"""
Prompt builder service.

Builds structured system and user prompts for GigaChat based on:
  - Holding profile (name, legal form, document structure, style, GOST)
  - Terms and definitions from knowledge base
  - Influencing documents
  - Draft files content
  - Context description from the user
"""

import json
import logging
from typing import Optional

from app.config import settings
from app.models.company import Company

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """
Ты — эксперт по корпоративным регламентам и политикам.
Твоя задача — создать ПОЛНЫЙ и ПОДРОБНЫЙ документ регламента/политики на русском языке на основе предоставленных черновиков и контекста.

[ПРОФИЛЬ КОМПАНИИ]
Название: {holding_name}
Юридическая форма: {holding_legal_form}
{use_gost_hint}

[СТРУКТУРА ДОКУМЕНТА]
{template_structure}

[ТЕРМИНЫ И ОПРЕДЕЛЕНИЯ КОМПАНИИ]
{terms}

[ВЛИЯЮЩИЕ ДОКУМЕНТЫ]
{influencing_docs}

[СТИЛИСТИЧЕСКИЕ ПАТТЕРНЫ КОМПАНИИ]
{style_patterns}

[РЕЛЕВАНТНЫЕ ФРАГМЕНТЫ УТВЕРЖДЁННЫХ ДОКУМЕНТОВ]
{rag_context}

[РЕЗУЛЬТАТЫ ПОИСКА В ИНТЕРНЕТЕ]
{web_context}

ВАЖНЫЕ ПРАВИЛА:
1. ГЛАВНОЕ: Используй черновики как ОСНОВУ документа. Сохраняй их структуру, терминологию, таблицы и ключевые положения. Дополняй и детализируй, но не заменяй их суть.
2. Все ссылки на законы и нормативные акты должны быть реальными. Если не уверен — не указывай. Используй свои знания актуального законодательства РФ.
3. Используй официально-деловой стиль. Используй типовые обороты из паттернов компании.
4. Если указан ГОСТ — соблюдай его требования к структуре.
5. **ДЕТАЛИЗАЦИЯ: КАЖДЫЙ раздел должен содержать от 3 до 7 пунктов с полным раскрытием темы.**
   **Минимальный объём документа: 5-7 страниц формата A4 (3000-5000 слов).**
   **Каждый пункт должен содержать 2-4 предложения с конкретикой: сроки, ответственные, процедуры, исключения.**
   **Используй подразделы (1.1, 1.2, 1.3...) для структурирования.**
6. ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО В ФОРМАТЕ JSON (без markdown-обертки).
7. Извлекай из черновиков конкретные правила, сроки, роли, ответственность и включай их в документ.
8. Если в черновиках есть таблицы — переноси их содержание в текст разделов.
9. Если тебе не хватает информации из черновиков — используй свои знания актуальных норм и правил РФ по данной теме, но всегда указывай, что основа — это черновики.
10. **ПРИМЕР ДЕТАЛИЗАЦИИ ПУНКТА:**
    Вместо: «Контроль осуществляется ответственными лицами»
    Пиши: «Контроль за выполнением требований настоящего регламента осуществляется руководителями структурных подразделений не реже одного раза в квартал. При выявлении нарушений составляется акт проверки в двух экземплярах, один из которых направляется в отдел внутреннего контроля в течение трёх рабочих дней.»
"""

USER_PROMPT_TEMPLATE = """
[ЧЕРНОВИКИ — ОСНОВА документа]
Содержимое загруженных файлов (структура, термины, таблицы, правила):
{drafts_content}

[КОНТЕКСТНОЕ ОПИСАНИЕ]
{context_description}

На основе черновиков (в первую очередь) и контекстного описания сгенерируй документ.
Сохрани структуру, терминологию и содержание черновиков.
Раскрой и детализируй каждый раздел, сделай документ ПОЛНЫМ и ПОДРОБНЫМ.
Обязательный объём: не менее 3000 слов. Каждый пункт должен содержать конкретные процедуры, сроки, ответственных лиц.

Используй актуальные нормы законодательства РФ по теме документа.

Формат ответа (строго JSON, без markdown-обертки):
{{
  "title": "Название документа",
  "description": "Краткое описание назначения документа",
  "sections": [
    {{
      "title": "1. Название раздела",
      "level": 1,
      "content": "Текст раздела...",
      "subsections": [
        {{
          "title": "1.1. Название подраздела",
          "level": 2,
          "content": "Текст..."
        }}
      ]
    }}
  ],
  "terms": [{{"term": "...", "definition": "..."}}],
  "abbreviations": [{{"abbreviation": "...", "full_form": "..."}}],
  "references": [{{"title": "...", "source": "..."}}]
}}
"""


class PromptBuilder:
    """Builds structured prompts for GigaChat."""

    def build_messages(
        self,
        company: Company,
        context_description: str,
        drafts_content: Optional[str],
        terms: list[dict],
        influencing_docs: list[dict],
        style_patterns: Optional[str] = None,
        rag_chunks: Optional[list[dict]] = None,
        web_results: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build system + user messages for LLM.

        Args:
            company: Company profile with structure/style settings.
            context_description: User's description of what the document should regulate.
            drafts_content: Extracted text from uploaded draft files, or empty string.
            terms: List of term dicts with 'term' and 'definition'.
            influencing_docs: List of influencing document dicts with 'title' and 'source'.
            style_patterns: Optional pre-formatted style patterns string.
                           If None, extracted from holding.style_settings.
            rag_chunks: List of relevant document chunks from RAG search.
            web_results: List of web search results.

        Returns:
            List of message dicts compatible with LLM API.
        """
        system_prompt = self._build_system_prompt(
            company, terms, influencing_docs, style_patterns, rag_chunks, web_results
        )
        user_prompt = self._build_user_prompt(context_description, drafts_content)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_system_prompt(
        self,
        company: Company,
        terms: list[dict],
        influencing_docs: list[dict],
        style_patterns: Optional[str] = None,
        rag_chunks: Optional[list[dict]] = None,
        web_results: Optional[list[dict]] = None,
    ) -> str:
        """Build the system prompt with company profile and knowledge base."""
        use_gost_hint = ""
        if company.use_gost:
            use_gost_hint = (
                "Применяется ГОСТ Р 7.0.97-2016. \n"
                "Требования: \n"
                "- шрифт Times New Roman, 14pt; \n"
                "- межстрочный интервал 1.5; \n"
                "- поля: левое 30мм, правое 15мм, верхнее/нижнее 20мм; \n"
                "- нумерация страниц внизу по центру; \n"
                "- заголовки разделов — полужирный, выравнивание по центру."
            )

        template_structure = "Стандартная структура документа."
        if company.document_structure:
            try:
                if isinstance(company.document_structure, str):
                    template_structure = company.document_structure
                else:
                    template_structure = json.dumps(
                        company.document_structure, ensure_ascii=False, indent=2
                    )
            except (TypeError, ValueError):
                template_structure = str(company.document_structure)

        terms_text = "Термины не указаны."
        if terms:
            terms_lines = []
            for t in terms:
                term_str = t.get("term", "")
                def_str = t.get("definition", "")
                if term_str and def_str:
                    terms_lines.append(f"  - {term_str}: {def_str}")
            if terms_lines:
                terms_text = "\n".join(terms_lines)

        influencing_text = "Влияющие документы не указаны."
        if influencing_docs:
            docs_lines = []
            for d in influencing_docs:
                title = d.get("title", "Без названия")
                source = d.get("source", "")
                full_text = d.get("full_text", "")
                if source:
                    docs_lines.append(f"  - {title} ({source})")
                else:
                    docs_lines.append(f"  - {title}")
                if full_text:
                    docs_lines.append(f"    Содержание: {full_text[:2000]}")
            if docs_lines:
                influencing_text = "\n".join(docs_lines)

        # Format style patterns
        if style_patterns is None:
            style_patterns = self._format_style_patterns(company.style_settings)

        # Format RAG chunks
        rag_context = "Релевантные фрагменты не найдены."
        if rag_chunks:
            chunk_lines = []
            for i, chunk in enumerate(rag_chunks[:settings.rag_max_chunks], 1):
                text = chunk.get("text", chunk.get("content", ""))
                source = chunk.get("title", chunk.get("source", "Неизвестный документ"))
                chunk_lines.append(f"  Фрагмент {i} (из: {source}):")
                chunk_lines.append(f"    {text[:500]}")
            if chunk_lines:
                rag_context = "\n".join(chunk_lines)

        # Format web results
        web_context = "Результаты поиска не найдены."
        if web_results:
            result_lines = []
            for i, result in enumerate(web_results[:5], 1):
                title = result.get("title", "")
                snippet = result.get("snippet", result.get("content", ""))
                url = result.get("url", "")
                result_lines.append(f"  Результат {i}: {title}")
                if snippet:
                    result_lines.append(f"    {snippet[:300]}")
                if url:
                    result_lines.append(f"    Источник: {url}")
            if result_lines:
                web_context = "\n".join(result_lines)

        return SYSTEM_PROMPT_TEMPLATE.format(
            holding_name=company.name,
            holding_legal_form=company.legal_form,
            use_gost_hint=use_gost_hint,
            template_structure=template_structure,
            terms=terms_text,
            influencing_docs=influencing_text,
            style_patterns=style_patterns,
            rag_context=rag_context,
            web_context=web_context,
        )

    def _format_style_patterns(self, style_settings: Optional[dict]) -> str:
        """Format style settings into a readable string for the prompt.

        Args:
            style_settings: Raw style_settings dict from company.

        Returns:
            Formatted string with typical phrases and statistics.
        """
        if not style_settings or not isinstance(style_settings, dict):
            return "Стилистические паттерны не обнаружены."

        lines = []

        # Typical phrases
        typical_phrases = style_settings.get("typical_phrases", [])
        if typical_phrases and isinstance(typical_phrases, list):
            lines.append("Типичные фразы, используемые в документах компании:")
            for phrase in typical_phrases[:10]:
                lines.append(f"  - «{phrase}…»")

        # Average sentence length
        avg_len = style_settings.get("avg_sentence_length")
        if avg_len:
            lines.append(f"Средняя длина предложения: {avg_len} слов.")

        # Documents analyzed
        doc_count = style_settings.get("documents_analyzed", 0)
        if doc_count:
            lines.append(f"Проанализировано документов: {doc_count}.")

        if not lines:
            return "Стилистические паттерны не обнаружены."

        return "\n".join(lines)

    def _build_user_prompt(
        self,
        context_description: str,
        drafts_content: Optional[str],
    ) -> str:
        """Build the user prompt with context and drafts."""
        if not drafts_content:
            drafts_content = "Черновики не загружены."

        return USER_PROMPT_TEMPLATE.format(
            context_description=context_description,
            drafts_content=drafts_content,
        )


    # ── V2 (B1): New super-prompt format ─────────────────────────────

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

    SYSTEM_PROMPT_V2_TEMPLATE = """
Ты — юрист холдинга «{company_name}» ({company_legal_form}).
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
"""

    USER_PROMPT_V2_TEMPLATE = """
ЧЕРНОВИК ПОЛЬЗОВАТЕЛЯ (используй как основу, дополни и структурируй):
{draft_text}

Тема документа: {topic}
Тип документа: {document_type_label}

На основе черновика (в первую очередь) и темы сгенерируй документ.
Сохрани структуру, терминологию и содержание черновика.
Раскрой и детализируй каждый раздел.

Формат ответа (строго JSON, без markdown-обертки):
{{
  "title": "Название документа",
  "description": "Краткое описание",
  "sections": [
    {{
      "title": "1. Название раздела",
      "level": 1,
      "content": "Текст раздела...",
      "subsections": [
        {{
          "title": "1.1. Название подраздела",
          "level": 2,
          "content": "Текст..."
        }}
      ]
    }}
  ],
  "terms": [{{"term": "...", "definition": "..."}}],
  "abbreviations": [{{"abbreviation": "...", "full_form": "..."}}],
  "references": [{{"title": "...", "source": "..."}}]
}}
"""

    @staticmethod
    def get_document_type_label(document_type: str) -> str:
        """Get human-readable label for document type."""
        return PromptBuilder.DOCUMENT_TYPES.get(
            document_type, {}
        ).get("label", document_type)

    def build_messages_v2(
        self,
        company,
        topic: str,
        document_type: str = "regulation",
        company_terms: list | None = None,
        company_abbreviations: list | None = None,
        similar_chunks: list[dict] | None = None,
        web_results_text: str | None = None,
        draft_text: str | None = None,
        influencing_docs: list[dict] | None = None,
    ) -> list[dict]:
        """Build V2 system + user messages for LLM using super-prompt format.

        Args:
            company: Company model instance.
            topic: Document topic.
            document_type: Document type key.
            company_terms: List of {"term": str, "definition": str}.
            company_abbreviations: List of {"abbreviation": str, "full_form": str}.
            similar_chunks: List of chunks from ChromaDB.
            web_results_text: Formatted web search results string or None.
            draft_text: Extracted draft text or empty string.
            influencing_docs: List of influencing document dicts.

        Returns:
            List of message dicts compatible with LLM API.
        """
        system_prompt = self._build_system_prompt_v2(
            company=company,
            document_type=document_type,
            company_terms=company_terms or [],
            company_abbreviations=company_abbreviations or [],
            similar_chunks=similar_chunks or [],
            web_results_text=web_results_text,
            influencing_docs=influencing_docs or [],
        )
        user_prompt = self._build_user_prompt_v2(
            topic=topic,
            document_type=document_type,
            draft_text=draft_text or "",
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_system_prompt_v2(
        self,
        company,
        document_type: str,
        company_terms: list[dict],
        company_abbreviations: list[dict],
        similar_chunks: list[dict],
        web_results_text: str | None,
        influencing_docs: list[dict],
    ) -> str:
        """Build V2 system prompt with all knowledge sources."""
        doc_type_label = self.get_document_type_label(document_type)

        # Structure text
        structure_text = self._format_structure_v2(company, document_type)

        # Terms text
        terms_text = self._format_terms_v2(company_terms)

        # Abbreviations text
        abbreviations_text = self._format_abbreviations_v2(company_abbreviations)

        # Similar chunks text
        similar_chunks_text = self._format_similar_chunks_v2(similar_chunks)

        # Web results text
        web_text = self._format_web_results_v2(web_results_text)

        # Influencing docs text
        influencing_text = self._format_influencing_docs_v2(influencing_docs)

        return self.SYSTEM_PROMPT_V2_TEMPLATE.format(
            company_name=company.name,
            company_legal_form=company.legal_form,
            document_type_label=doc_type_label,
            structure_text=structure_text,
            terms_text=terms_text,
            abbreviations_text=abbreviations_text,
            similar_chunks_text=similar_chunks_text,
            web_results_text=web_text,
            influencing_docs_text=influencing_text,
        )

    def _build_user_prompt_v2(
        self,
        topic: str,
        document_type: str,
        draft_text: str,
    ) -> str:
        """Build V2 user prompt with draft + topic."""
        doc_type_label = self.get_document_type_label(document_type)
        if not draft_text:
            draft_text = "Черновик не загружен."

        return self.USER_PROMPT_V2_TEMPLATE.format(
            draft_text=draft_text,
            topic=topic,
            document_type_label=doc_type_label,
        )

    def _format_structure_v2(self, company, document_type: str) -> str:
        """Format document structure for V2 prompt."""
        doc_type_info = self.DOCUMENT_TYPES.get(document_type, {})
        default_structure = doc_type_info.get("default_structure", "Стандартная структура документа.")

        if company.document_structure:
            if isinstance(company.document_structure, str):
                return company.document_structure
            try:
                import json
                return json.dumps(company.document_structure, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                return str(company.document_structure)

        return default_structure

    def _format_terms_v2(self, terms: list[dict]) -> str:
        """Format company terms for V2 prompt."""
        if not terms:
            return "Термины холдинга не определены."

        # Limit to 50 terms
        display_terms = terms[:50]
        lines = [f"  - {t['term']}: {t['definition']}" for t in display_terms if t.get("term") and t.get("definition")]

        if len(terms) > 50:
            lines.append(f"  ... и ещё {len(terms) - 50} терминов.")

        return "\n".join(lines) if lines else "Термины холдинга не определены."

    def _format_abbreviations_v2(self, abbreviations: list[dict]) -> str:
        """Format company abbreviations for V2 prompt."""
        if not abbreviations:
            return "Сокращения холдинга не определены."

        # Limit to 20 abbreviations
        display_abbrs = abbreviations[:20]
        lines = [f"  - {a['abbreviation']} — {a['full_form']}" for a in display_abbrs if a.get("abbreviation") and a.get("full_form")]

        return "\n".join(lines) if lines else "Сокращения холдинга не определены."

    def _format_similar_chunks_v2(self, chunks: list[dict]) -> str:
        """Format similar chunks from ChromaDB for V2 prompt."""
        if not chunks:
            return "Похожие документы не найдены."

        lines = []
        for i, chunk in enumerate(chunks[:5], 1):
            text = chunk.get("text", chunk.get("content", ""))
            source = chunk.get("title", chunk.get("source", "Неизвестный документ"))
            lines.append(f"  Фрагмент {i} (из: {source}):")
            lines.append(f"    {text[:600]}")

        return "\n".join(lines)

    def _format_web_results_v2(self, web_text: str | None) -> str:
        """Format web search results for V2 prompt."""
        if web_text:
            return web_text
        return "Поиск в интернете не выполнялся или недоступен."

    def _format_influencing_docs_v2(self, docs: list[dict]) -> str:
        """Format influencing documents for V2 prompt."""
        if not docs:
            return "Влияющие документы не указаны."

        lines = []
        for d in docs:
            title = d.get("title", "Без названия")
            source = d.get("source", "Внутренний документ")
            full_text = d.get("full_text", "")
            lines.append(f"  - {title} ({source})")
            if full_text:
                lines.append(f"    Содержание: {full_text[:2000]}")

        return "\n".join(lines)


# Singleton
prompt_builder = PromptBuilder()
