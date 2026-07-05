"""
paragraph_extractor — извлечение структурированных параграфов из .docx.

Основная функция:
    extract_paragraphs(docx_path: str) -> list[ExtractedParagraph]

Логика:
    1. Открывает .docx через python-docx
    2. Итерирует все параграфы документа по порядку
    3. Детектирует заголовки (style.name начинается с "Heading")
    4. Отслеживает текущий заголовок раздела (section_title)
    5. Детектирует строки таблиц и элементы списков
    6. Фильтрует пустые и короткие параграфы (кроме заголовков)
    7. Извлекает текст из таблиц (включая вложенные)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from docx import Document
from docx.text.paragraph import Paragraph


# ──────────────────────────────────────────────
# Data class
# ──────────────────────────────────────────────


@dataclass
class ExtractedParagraph:
    """Один извлечённый параграф документа."""

    index: int
    """Порядковый номер параграфа в документе (0-based)."""

    text: str
    """Текст параграфа (plain text)."""

    section_title: str | None
    """Текст ближайшего предшествующего заголовка раздела."""

    is_heading: bool
    """True, если параграф является заголовком."""

    heading_level: int
    """Уровень заголовка: 0 для body, 1 для Heading 1, 2 для Heading 2 и т.д."""

    is_table_row: bool
    """True, если параграф извлечён из таблицы."""

    is_list_item: bool
    """True, если параграф похож на элемент списка."""

    char_count: int
    """Количество символов в тексте (len(text))."""

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


# Регулярка для детекции элементов списка:
#   - Начинаются с дефиса, звёздочки, буллита
#   - Начинаются с цифры с точкой/скобкой
#   - Начинаются с буквенных маркеров (а), б))
_LIST_PATTERN = re.compile(
    r"^(\s*[-*•\u2022\u2023\u25E6\u2043])"  # маркеры списка
    r"|"
    r"^(\s*\(?\d{1,3}\)?[\).])"  # нумерация: 1., 1), (1)
    r"|"
    r"^(\s*[а-я]\))"  # буквенные маркеры: а), б)
)


def _is_heading(paragraph: Paragraph) -> bool:
    """Проверяет, является ли параграф заголовком."""
    if paragraph.style is None:
        return False
    style_name = paragraph.style.name or ""
    return style_name.lower().startswith("heading")


def _get_heading_level(paragraph: Paragraph) -> int:
    """Возвращает уровень заголовка (1, 2, …) или 0 для body."""
    if not _is_heading(paragraph):
        return 0
    style_name = paragraph.style.name or "Heading 1"
    # style.name может быть "Heading 1", "Heading 2", "Heading 3", …
    # или "Heading1" (без пробела) — обрабатываем оба варианта
    match = re.search(r"(\d+)$", style_name)
    if match:
        return int(match.group(1))
    return 1  # fallback


def _is_in_table(paragraph: Paragraph) -> bool:
    """Проверяет, находится ли параграф внутри таблицы."""
    try:
        return paragraph._element.getparent().tag.endswith("tc")
    except Exception:
        return False


def _is_list_item(text: str) -> bool:
    """Проверяет, является ли текст элементарным списком."""
    if not text:
        return False
    return bool(_LIST_PATTERN.match(text))


def _extract_text_from_cell(cell) -> str:
    """Извлекает текст из ячейки таблицы, объединяя параграфы."""
    parts = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
    return " ".join(parts)


def _collect_all_tables(doc_or_cell) -> list:
    """
    Рекурсивно собирает все таблицы (включая вложенные).

    python-docx предоставляет .tables как на уровне Document,
    так и на уровне Cell — используем это для рекурсивного сбора.
    """
    tables = []
    for table in doc_or_cell.tables:
        tables.append(table)
        # Проверяем ячейки таблицы на наличие вложенных таблиц
        for row in table.rows:
            for cell in row.cells:
                nested = _collect_all_tables(cell)
                tables.extend(nested)
    return tables


# ──────────────────────────────────────────────
# Main function
# ──────────────────────────────────────────────


def extract_paragraphs(docx_path: str) -> list[ExtractedParagraph]:
    """
    Извлекает структурированные параграфы из .docx файла.

    Parameters
    ----------
    docx_path : str
        Путь к .docx файлу.

    Returns
    -------
    list[ExtractedParagraph]
        Список извлечённых параграфов.
    """
    doc = Document(docx_path)

    result: list[ExtractedParagraph] = []
    current_section: str | None = None

    # ── 1. Параграфы основного документа ──
    paragraph_index = 0

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()

        # Пропускаем пустые параграфы
        if not text:
            continue

        # Детектируем заголовок
        is_heading = _is_heading(paragraph)

        if is_heading:
            # Обновляем текущий раздел ДО фильтрации длины,
            # чтобы короткие заголовки всё равно обновляли раздел
            current_section = text
            # НЕ ПРОПУСКАЕМ заголовки по длине — они всегда включаются
        else:
            # Для body-параграфов: пропускаем слишком короткие (форматные артефакты)
            if len(text) < 20:
                continue

        heading_level = _get_heading_level(paragraph)
        is_table_row = _is_in_table(paragraph)
        is_list_item = _is_list_item(text)

        result.append(
            ExtractedParagraph(
                index=paragraph_index,
                text=text,
                section_title=current_section if not is_heading else None,
                is_heading=is_heading,
                heading_level=heading_level,
                is_table_row=is_table_row,
                is_list_item=is_list_item,
                char_count=len(text),
            )
        )
        paragraph_index += 1

    # ── 2. Параграфы из таблиц (включая вложенные) ──
    table_base_index = len(result)
    all_tables = _collect_all_tables(doc)

    for table in all_tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = _extract_text_from_cell(cell)
                if not cell_text:
                    continue
                # Для табличных данных тоже пропускаем короткие строки
                if len(cell_text) < 20:
                    continue

                is_list = _is_list_item(cell_text)

                result.append(
                    ExtractedParagraph(
                        index=table_base_index,
                        text=cell_text,
                        section_title=current_section,
                        is_heading=False,
                        heading_level=0,
                        is_table_row=True,
                        is_list_item=is_list,
                        char_count=len(cell_text),
                    )
                )
                table_base_index += 1

    return result


# ──────────────────────────────────────────────
# CLI / self-test
# ──────────────────────────────────────────────


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.services.paragraph_extractor <path_to_docx>")
        sys.exit(1)

    path = sys.argv[1]
    paragraphs = extract_paragraphs(path)

    print(f"Total paragraphs extracted: {len(paragraphs)}")
    print()

    # Показываем первые 10
    for p in paragraphs[:10]:
        print(
            f"  [{p.index:4d}] "
            f"heading={p.is_heading!s:5} "
            f"lvl={p.heading_level} "
            f"table={p.is_table_row!s:5} "
            f"list={p.is_list_item!s:5} "
            f"chars={p.char_count:4d} "
            f"section={p.section_title or ''}"
        )
        _preview = p.text[:90].replace("\n", " ")
        print(f"         {_preview}")
        print()

    # Статистика
    headings = sum(1 for p in paragraphs if p.is_heading)
    tables = sum(1 for p in paragraphs if p.is_table_row)
    lists = sum(1 for p in paragraphs if p.is_list_item)
    no_section = sum(1 for p in paragraphs if p.section_title is None and not p.is_heading)

    print("─── Stats ───")
    print(f"  Body paragraphs:       {len(paragraphs) - headings}")
    print(f"  Headings:              {headings}")
    print(f"  Table rows:            {tables}")
    print(f"  List items:            {lists}")
    print(f"  No section title:      {no_section}")
