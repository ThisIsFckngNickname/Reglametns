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


# Singleton
prompt_builder = PromptBuilder()
