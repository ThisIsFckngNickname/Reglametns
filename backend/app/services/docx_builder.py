"""
docx_builder — преобразование markdown-ответа от LLM в .docx файл.

Правила парсинга (из спецификации раздел 5.3):
- `# ` → Heading 1 (18pt, bold)
- `## ` → Heading 2 (16pt, bold)
- `### ` → Heading 3 (14pt, bold)
- `#### ` → Heading 4 (14pt, italic)
- `- ` / `* ` → маркированный список
- `1. `, `2. ` → нумерованный список
- `| ... | ... |` → таблица (pipe-синтаксис)
- Обычный текст → параграф (Times New Roman, 14pt, межстрочный 1.5)
- `---` → игнорируется
- `*текст*` → курсив, `**текст**` → жирный
"""

import logging
import os
import re
from typing import List, Optional, Tuple

from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)

# ───────────────────────────── Настройки стилей ─────────────────────────────

FONT_NAME = "Times New Roman"
FONT_SIZE_BODY = Pt(14)
FONT_SIZE_H1 = Pt(18)
FONT_SIZE_H2 = Pt(16)
FONT_SIZE_H3 = Pt(14)
FONT_SIZE_H4 = Pt(14)
LINE_SPACING = 1.5

# Транслитерация кириллицы в латиницу для имён файлов
TRANSLIT_TABLE = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D",
    "Е": "E", "Ё": "Yo", "Ж": "Zh", "З": "Z", "И": "I",
    "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N",
    "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
    "У": "U", "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch",
    "Ш": "Sh", "Щ": "Shch", "Ъ": "", "Ы": "Y", "Ь": "",
    "Э": "E", "Ю": "Yu", "Я": "Ya",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}

# Регулярки для inline-форматирования
BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
ITALIC_PATTERN = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def transliterate(text: str) -> str:
    """Транслитерация кириллицы в латиницу."""
    result = []
    for char in text:
        result.append(TRANSLIT_TABLE.get(char, char))
    return "".join(result)


def make_filename(topic: str) -> str:
    """Создать безопасное имя файла из темы.

    Пример: "Регламент по учёту ГСМ на АЗС" → "Reglament-po-uchetu-GSM-na-AZS.docx"
    """
    # Транслитерация
    latin = transliterate(topic.strip())
    # Замена пробелов и небуквенно-цифровых символов на дефис
    latin = re.sub(r"[^\w\-]", "-", latin)
    # Схлопывание повторяющихся дефисов
    latin = re.sub(r"-{2,}", "-", latin)
    # Удаление дефисов в начале и конце
    latin = latin.strip("-")
    # Fallback если имя пустое (например, если тема содержит только неподдерживаемые символы)
    if not latin:
        import uuid
        latin = uuid.uuid4().hex[:8]
    # Ограничение длины
    if len(latin) > 100:
        latin = latin[:100]
    return f"{latin}.docx"


# ───────────────────────────── Inline formatting ─────────────────────────────


def _apply_inline_formatting(paragraph, text: str):
    """Применить **жирный** и *курсив* к тексту параграфа."""
    # Сначала обрабатываем **жирный**
    parts = re.split(r"(\*\*.+?\*\*)", text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            inner = part[2:-2]
            run = paragraph.add_run(inner)
            run.bold = True
        else:
            # Затем *курсив* внутри обычного текста
            sub_parts = re.split(r"(\*[^*]+\*)", part)
            for sub_part in sub_parts:
                if sub_part.startswith("*") and sub_part.endswith("*") and len(sub_part) > 2:
                    inner = sub_part[1:-1]
                    run = paragraph.add_run(inner)
                    run.italic = True
                else:
                    run = paragraph.add_run(sub_part)
    return paragraph


# ───────────────────────────── Параграф / Заголовок ─────────────────────────────


def _add_paragraph(doc: Document, text: str, style_name: Optional[str] = None):
    """Добавить параграф с форматированием.

    Args:
        doc: Document python-docx.
        text: Текст параграфа.
        style_name: Имя стиля (опционально).
    """
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Межстрочный интервал 1.5
    pf = paragraph.paragraph_format
    pf.line_spacing = LINE_SPACING
    pf.space_after = Pt(6)

    if style_name == "Heading 1":
        _apply_inline_formatting(paragraph, text)
        _set_run_font(paragraph, size=FONT_SIZE_H1, bold=True)
        return paragraph
    elif style_name == "Heading 2":
        _apply_inline_formatting(paragraph, text)
        _set_run_font(paragraph, size=FONT_SIZE_H2, bold=True)
        return paragraph
    elif style_name == "Heading 3":
        _apply_inline_formatting(paragraph, text)
        _set_run_font(paragraph, size=FONT_SIZE_H3, bold=True)
        return paragraph
    elif style_name == "Heading 4":
        _apply_inline_formatting(paragraph, text)
        _set_run_font(paragraph, size=FONT_SIZE_H4, bold=False, italic=True)
        return paragraph
    else:
        # Обычный параграф
        _apply_inline_formatting(paragraph, text)
        _set_run_font(paragraph, size=FONT_SIZE_BODY)
        return paragraph


def _set_run_font(paragraph, size: Pt, bold: bool = False, italic: bool = False):
    """Установить шрифт для всех run в параграфе."""
    for run in paragraph.runs:
        run.font.name = FONT_NAME
        run.font.size = size
        run.bold = bold
        run.italic = italic
        # Для поддержки кириллицы в шрифте
        r = run._element
        rPr = r.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = _make_element("w:rFonts")
            rPr.insert(0, rFonts)
        rFonts.set(qn("w:eastAsia"), FONT_NAME)
        rFonts.set(qn("w:cs"), FONT_NAME)


def _make_element(tag: str):
    """Создать XML элемент для docx."""
    from docx.oxml import OxmlElement
    return OxmlElement(tag)


# ───────────────────────────── Списки ─────────────────────────────


def _add_bullet_item(doc: Document, text: str):
    """Добавить маркированный список."""
    paragraph = doc.add_paragraph(style="List Bullet")
    paragraph.clear()
    _apply_inline_formatting(paragraph, text)
    _set_run_font(paragraph, size=FONT_SIZE_BODY)
    pf = paragraph.paragraph_format
    pf.line_spacing = LINE_SPACING
    pf.space_after = Pt(2)


def _add_numbered_item(doc: Document, text: str, level: int = 0):
    """Добавить нумерованный список."""
    paragraph = doc.add_paragraph(style="List Number")
    paragraph.clear()
    _apply_inline_formatting(paragraph, text)
    _set_run_font(paragraph, size=FONT_SIZE_BODY)
    pf = paragraph.paragraph_format
    pf.line_spacing = LINE_SPACING
    pf.space_after = Pt(2)


# ───────────────────────────── Таблицы ─────────────────────────────


def _add_table(doc: Document, rows_data: List[List[str]]):
    """Добавить таблицу из данных."""
    if len(rows_data) < 2:
        return  # Минимум: заголовок + строка с данными

    # Определяем количество столбцов по первой строке
    num_cols = len(rows_data[0])
    if num_cols == 0:
        return

    # Пропускаем строку-разделитель (|---|)
    data_rows = [rows_data[0]]
    for row in rows_data[1:]:
        # Проверяем, не является ли строка разделителем (все ячейки содержат только дефисы)
        if all(re.match(r"^-+$", cell.strip()) for cell in row):
            continue
        data_rows.append(row)

    if len(data_rows) < 1:
        return

    table = doc.add_table(rows=len(data_rows), cols=num_cols)
    table.style = "Table Grid"

    for i, row in enumerate(data_rows):
        for j, cell_text in enumerate(row):
            if j >= num_cols:
                break
            cell = table.cell(i, j)
            cell.text = ""
            paragraph = cell.paragraphs[0]
            run = paragraph.add_run(cell_text.strip())
            run.font.name = FONT_NAME
            run.font.size = Pt(12)
            if i == 0:
                run.bold = True

    doc.add_paragraph()  # отступ после таблицы


# ───────────────────────────── Парсинг markdown ─────────────────────────────


def _parse_table_line(line: str) -> List[str]:
    """Распарсить строку таблицы вида | a | b | c | в список ячеек."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    # Разбиваем по |
    cells = [cell.strip() for cell in line.split("|")]
    return cells


def _is_table_row(line: str) -> bool:
    """Проверить, является ли строка строкой таблицы."""
    line = line.strip()
    return line.startswith("|") and line.count("|") >= 2


def build_docx(markdown_text: str, filename: str, output_dir: str = "generated") -> str:
    """Парсинг markdown-текста в .docx файл.

    Args:
        markdown_text: Ответ от LLM в markdown-формате.
        filename: Имя файла для сохранения (без пути).
        output_dir: Директория для сохранения.

    Returns:
        Полный путь к сохранённому .docx файлу.

    Raises:
        ValueError: Если markdown_text пустой.
        OSError: Если не удалось сохранить файл.
    """
    if not markdown_text or not markdown_text.strip():
        raise ValueError("Markdown text is empty, cannot build .docx")

    doc = Document()

    # Настройка стилей документа по умолчанию
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = FONT_SIZE_BODY
    style.paragraph_format.line_spacing = LINE_SPACING

    # Поля страницы
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    lines = markdown_text.split("\n")
    i = 0
    in_table = False
    table_rows: List[List[str]] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ─── Таблицы ───
        if _is_table_row(line):
            cells = _parse_table_line(line)
            table_rows.append(cells)
            in_table = True
            i += 1
            continue
        elif in_table:
            # Закончились строки таблицы — добавляем таблицу
            _add_table(doc, table_rows)
            table_rows = []
            in_table = False
            # Не переходим к следующей строке — обработаем её в этой итерации
            continue

        # ─── Пустые строки ───
        if not stripped:
            i += 1
            continue

        # ─── Разделитель ───
        if stripped == "---":
            i += 1
            continue

        # ─── Заголовки ───
        if stripped.startswith("#### "):
            text = stripped[5:].strip()
            _add_paragraph(doc, text, style_name="Heading 4")
        elif stripped.startswith("### "):
            text = stripped[4:].strip()
            _add_paragraph(doc, text, style_name="Heading 3")
        elif stripped.startswith("## "):
            text = stripped[3:].strip()
            _add_paragraph(doc, text, style_name="Heading 2")
        elif stripped.startswith("# "):
            text = stripped[2:].strip()
            _add_paragraph(doc, text, style_name="Heading 1")

        # ─── Маркированные списки ───
        elif stripped.startswith("- ") or stripped.startswith("* "):
            text = stripped[2:].strip()
            _add_bullet_item(doc, text)

        # ─── Нумерованные списки ───
        elif re.match(r"^\d+\.\s", stripped):
            text = re.sub(r"^\d+\.\s", "", stripped, count=1).strip()
            _add_numbered_item(doc, text)

        else:
            # ─── Обычный параграф ───
            _add_paragraph(doc, stripped)

        i += 1

    # Если таблица была последней и не закрыта
    if in_table and table_rows:
        _add_table(doc, table_rows)

    # Сохранение
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    doc.save(filepath)
    logger.info("Saved .docx to %s", filepath)

    return os.path.abspath(filepath)
