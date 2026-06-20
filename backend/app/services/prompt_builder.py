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
Твоя задача — создать структурированный документ регламента/политики на русском языке.

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

ВАЖНЫЕ ПРАВИЛА:
1. Все ссылки на законы и нормативные акты должны быть реальными. Если не уверен — не указывай.
2. Используй официально-деловой стиль.
3. Каждый раздел должен содержать содержательный текст.
4. Если указан ГОСТ — соблюдай его требования к структуре.
5. ОТВЕТ ДОЛЖЕН БЫТЬ ТОЛЬКО В ФОРМАТЕ JSON (без markdown-обертки).
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
    ) -> list[dict]:
        """Build system + user messages for GigaChat.

        Args:
            holding: Holding profile with structure/style settings.
            context_description: User's description of what the document should regulate.
            drafts_content: Extracted text from uploaded draft files, or empty string.
            terms: List of term dicts with 'term' and 'definition'.
            influencing_docs: List of influencing document dicts with 'title' and 'source'.

        Returns:
            List of message dicts compatible with GigaChat API.
        """
        system_prompt = self._build_system_prompt(holding, terms, influencing_docs)
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

        return SYSTEM_PROMPT_TEMPLATE.format(
            holding_name=holding.name,
            holding_legal_form=holding.legal_form,
            use_gost_hint=use_gost_hint,
            template_structure=template_structure,
            terms=terms_text,
            influencing_docs=influencing_text,
        )

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
