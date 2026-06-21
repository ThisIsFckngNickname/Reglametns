"""
Parser helpers — shared data structures and extraction functions.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a document."""
    sections: List[dict] = field(default_factory=list)
    tables: List[dict] = field(default_factory=list)
    terms: List[dict] = field(default_factory=list)
    abbreviations: List[dict] = field(default_factory=list)
    lists: List[dict] = field(default_factory=list)


TERM_SECTION_KEYWORDS = [
    "термин", "определение", "глоссарий", "понятий",
    "термины и определения", "основные понятия",
]

ABBREVIATION_SECTION_KEYWORDS = [
    "сокращение", "условное обозначение", "аббревиатур",
    "список сокращений", "принятые сокращения",
]


def _is_term_section(title: str) -> bool:
    title_lower = title.lower().strip()
    return any(kw in title_lower for kw in TERM_SECTION_KEYWORDS)


def _is_abbreviation_section(title: str) -> bool:
    title_lower = title.lower().strip()
    return any(kw in title_lower for kw in ABBREVIATION_SECTION_KEYWORDS)


def _extract_terms_from_text(text: str) -> List[dict]:
    """Extract term-definition pairs from text.

    Heuristics:
      1. "Термин — определение" (em dash)
      2. "Термин – определение" (en dash)
      3. "Термин: определение" (colon)
      4. "Термин\tопределение" (tab)
    """
    terms = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        term = None
        definition = None

        for sep in [" — ", " – ", " - ", ": ", "\t"]:
            if sep in line:
                parts = line.split(sep, 1)
                candidate_term = parts[0].strip()
                candidate_def = parts[1].strip()

                if (
                    candidate_term
                    and candidate_def
                    and len(candidate_term) < 100
                    and not re.match(r"^\d", candidate_term)
                ):
                    term = candidate_term
                    definition = candidate_def
                    break

        if term and definition:
            term = term.rstrip(".,;:")
            definition = re.sub(r"^[\s\-–—:.]+\s*", "", definition)

            if term and definition:
                terms.append({"term": term, "definition": definition})

    return terms


def _extract_abbreviations_from_text(text: str) -> List[dict]:
    """Extract abbreviation-full_form pairs from text."""
    abbreviations = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        abbr = None
        full_form = None

        # Pattern 1: "ABBR — full form"
        for sep in [" — ", " – ", " - "]:
            if sep in line:
                parts = line.split(sep, 1)
                candidate_abbr = parts[0].strip()
                candidate_full = parts[1].strip()

                if (
                    candidate_abbr
                    and candidate_full
                    and len(candidate_abbr) < 30
                    and (candidate_abbr.isupper() or re.match(r"^[А-ЯA-Z]{2,}", candidate_abbr))
                ):
                    abbr = candidate_abbr
                    full_form = candidate_full
                    break

        # Pattern 2: "ABBR (full form)"
        if not abbr:
            match = re.match(r"^([А-ЯA-Z]{2,})\s*[\(（](.+)[\)）]", line)
            if match:
                abbr = match.group(1).strip()
                full_form = match.group(2).strip()

        if abbr and full_form:
            abbr = abbr.rstrip(".,;:")
            full_form = full_form.rstrip(".,;:")
            abbreviations.append({"abbreviation": abbr, "full_form": full_form})

    return abbreviations


def _find_term_abbreviation_sections(sections: List[dict]) -> tuple:
    """Find sections that contain terms or abbreviations."""
    term_section_ids = set()
    abbreviation_section_ids = set()

    for section in sections:
        title = section.get("title", "")
        if _is_term_section(title):
            term_section_ids.add(section.get("order_num"))
        if _is_abbreviation_section(title):
            abbreviation_section_ids.add(section.get("order_num"))

    return term_section_ids, abbreviation_section_ids


def _build_section_hierarchy(sections: List[dict]) -> List[dict]:
    """Build parent-child relationships based on heading levels."""
    if not sections:
        return []

    sections = sorted(sections, key=lambda s: s["order_num"])
    result = []
    parent_stack: list = []

    for section in sections:
        level = section.get("level", 1)
        order_num = section.get("order_num", 0)

        while parent_stack and parent_stack[-1][0] >= level:
            parent_stack.pop()

        if parent_stack:
            section["parent_id"] = parent_stack[-1][1]
        else:
            section["parent_id"] = None

        parent_stack.append((level, order_num))
        result.append(section)

    return result


def _table_to_html(headers: List[str], rows: List[List[str]], caption: Optional[str] = None) -> str:
    """Convert table data to simple HTML."""
    html_parts = []
    if caption:
        html_parts.append(f"<caption>{caption}</caption>")

    html_parts.append("<table border='1' cellpadding='4' cellspacing='0'>")

    if headers:
        html_parts.append("<thead><tr>")
        for h in headers:
            html_parts.append(f"<th>{h}</th>")
        html_parts.append("</tr></thead>")

    if rows:
        html_parts.append("<tbody>")
        for row in rows:
            html_parts.append("<tr>")
            for cell in row:
                html_parts.append(f"<td>{cell}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody>")

    html_parts.append("</table>")
    return "\n".join(html_parts)
