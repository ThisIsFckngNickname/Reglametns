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

from app.models.holding import Holding

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """
Ты — эксперт по корпоративным регламентам и политикам.
Твоя задача — создать ПОЛНЫЙ, ДЕТАЛЬНЫЙ, РАЗВЁРНУТЫЙ документ регламента/политики на русском языке.

ВАЖНО: Документ должен быть ОБЪЁМНЫМ и СОДЕРЖАТЕЛЬНЫМ (20-50 страниц в Word).
Каждый раздел должен содержать минимум 5-10 предложений с детальным описанием.
Не пиши "общие фразы" — каждый пункт должен содержать конкретные указания.

[ПРОФИЛЬ ХОЛДИНГА]
Название: {holding_name}
Юридическая форма: {holding_legal_form}
{use_gost_hint}

[СТРУКТУРА ДОКУМЕНТА]
{template_structure}

[ТЕРМИНЫ И ОПРЕДЕЛЕНИЯ ХОЛДИНГА]
{terms}

[ВЛИЯЮЩИЕ ДОКУМЕНТЫ]
{influencing_docs}

[СТИЛИСТИЧЕСКИЕ ПАТТЕРНЫ ХОЛДИНГА]
{style_patterns}

ВАЖНЫЕ ПРАВИЛА:
1. Все ссылки на законы и нормативные акты должны быть реальными. Если не уверен — не указывай.
2. Используй официально-деловой стиль. Используй типовые обороты из паттернов холдинга.
3. Каждый раздел должен содержать содержательный текст (минимум 5-10 предложений).
4. Если указан ГОСТ — соблюдай его требования к структуре.
5. Документ должен быть ПОЛНЫМ: введение, основная часть (детальные разделы по каждому этапу/процессу), заключение.
6. ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО В ФОРМАТЕ JSON (без markdown-обертки).
7. НЕ ИСПОЛЬЗУЙ шаблонные фразы типа "настоящий регламент определяет порядок" — пиши конкретно по теме.
"""

USER_PROMPT_TEMPLATE = """
[КОНТЕКСТНОЕ ОПИСАНИЕ]
{context_description}

[ЧЕРНОВИКИ]
{drafts_content}

Сгенерируй документ в следующем JSON-формате:
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
        holding: Holding,
        context_description: str,
        drafts_content: Optional[str],
        terms: list[dict],
        influencing_docs: list[dict],
        style_patterns: Optional[str] = None,
    ) -> list[dict]:
        """Build system + user messages for LLM.

        Args:
            holding: Holding profile with structure/style settings.
            context_description: User's description of what the document should regulate.
            drafts_content: Extracted text from uploaded draft files, or empty string.
            terms: List of term dicts with 'term' and 'definition'.
            influencing_docs: List of influencing document dicts with 'title' and 'source'.
            style_patterns: Optional pre-formatted style patterns string.
                           If None, extracted from holding.style_settings.

        Returns:
            List of message dicts compatible with LLM API.
        """
        system_prompt = self._build_system_prompt(
            holding, terms, influencing_docs, style_patterns
        )
        user_prompt = self._build_user_prompt(context_description, drafts_content)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_system_prompt(
        self,
        holding: Holding,
        terms: list[dict],
        influencing_docs: list[dict],
        style_patterns: Optional[str] = None,
    ) -> str:
        """Build the system prompt with holding profile and knowledge base."""
        use_gost_hint = ""
        if holding.use_gost:
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
        if holding.document_structure:
            try:
                if isinstance(holding.document_structure, str):
                    template_structure = holding.document_structure
                else:
                    template_structure = json.dumps(
                        holding.document_structure, ensure_ascii=False, indent=2
                    )
            except (TypeError, ValueError):
                template_structure = str(holding.document_structure)

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
                if source:
                    docs_lines.append(f"  - {title} ({source})")
                else:
                    docs_lines.append(f"  - {title}")
            if docs_lines:
                influencing_text = "\n".join(docs_lines)

        # Format style patterns
        if style_patterns is None:
            style_patterns = self._format_style_patterns(holding.style_settings)

        return SYSTEM_PROMPT_TEMPLATE.format(
            holding_name=holding.name,
            holding_legal_form=holding.legal_form,
            use_gost_hint=use_gost_hint,
            template_structure=template_structure,
            terms=terms_text,
            influencing_docs=influencing_text,
            style_patterns=style_patterns,
        )

    def _format_style_patterns(self, style_settings: Optional[dict]) -> str:
        """Format style settings into a readable string for the prompt.

        Args:
            style_settings: Raw style_settings dict from holding.

        Returns:
            Formatted string with typical phrases and statistics.
        """
        if not style_settings or not isinstance(style_settings, dict):
            return "Стилистические паттерны не обнаружены."

        lines = []

        # Typical phrases
        typical_phrases = style_settings.get("typical_phrases", [])
        if typical_phrases and isinstance(typical_phrases, list):
            lines.append("Типичные фразы, используемые в документах холдинга:")
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
