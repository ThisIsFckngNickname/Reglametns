"""
Docx builder service.

Converts structured generation result (JSON) into a .docx file.
Uses python-docx library.

Supports:
  - Title page with company name, document title, status, date
  - Table of Contents (TOC) field
  - Sections/subsections with hierarchy
  - Terms and definitions table
  - Abbreviations table
  - References list
  - Page numbers in footer
  - Holding-specific styling (fonts, margins)
  - GOST R 7.0.97-2016 formatting
"""

import logging
import os
from datetime import datetime
from typing import Optional

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from app.models.company import Company

logger = logging.getLogger(__name__)


class DocxBuilder:
    """Converts structured generation result (JSON) into .docx file."""

    def build(
        self,
        result: dict,
        company: Company,
        output_path: str,
    ) -> str:
        """Build .docx from generation result.

        Args:
            result: Parsed generation result with title, sections, terms, etc.
            company: Company profile for styling.
            output_path: Full path where the .docx file will be saved.

        Returns:
            The output_path where the file was saved.
        """
        doc = DocxDocument()

        # Apply base styling
        self._setup_default_style(doc)

        # Apply GOST if enabled (margins + page numbers)
        if company.use_gost:
            self._apply_gost(doc)

        # Apply company-specific style
        self._apply_company_style(doc, company)

        # Always add page numbers to footer
        self._add_page_numbers(doc)

        # === TITLE PAGE ===
        self._add_title_page(doc, result, company)

        # === TABLE OF CONTENTS ===
        self._add_toc(doc)

        # === DOCUMENT CONTENT ===
        # Description
        self._add_description(doc, result.get("description", ""))

        # Sections
        for section in result.get("sections", []):
            self._add_section(doc, section)

        # Terms table
        terms = result.get("terms", [])
        if terms:
            doc.add_page_break()
            doc.add_heading("Термины и определения", level=1)
            self._add_terms_table(doc, terms)

        # Abbreviations table
        abbreviations = result.get("abbreviations", [])
        if abbreviations:
            doc.add_heading("Список сокращений", level=1)
            self._add_abbreviations_table(doc, abbreviations)

        # References
        references = result.get("references", [])
        if references:
            doc.add_heading("Список использованных источников", level=1)
            self._add_references_list(doc, references)

        # Save
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)
        logger.info(f"Document saved to {output_path}")
        return output_path

    # ── Styling ──────────────────────────────────────────────────────────────

    def _setup_default_style(self, doc: DocxDocument) -> None:
        """Configure default document style."""
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Times New Roman"
        font.size = Pt(14)
        paragraph_format = style.paragraph_format
        paragraph_format.line_spacing = 1.5
        paragraph_format.space_after = Pt(6)
        paragraph_format.space_before = Pt(0)

    # ── Title page ───────────────────────────────────────────────────────────

    def _add_title_page(self, doc: DocxDocument, result: dict, company: Company) -> None:
        """Create a separate title page."""
        title = result.get("title", "Документ")
        now = datetime.now().strftime("%d.%m.%Y")

        # Empty paragraphs for vertical spacing (top margin push-down)
        for _ in range(6):
            doc.add_paragraph()

        # Company name
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(company.name)
        run.bold = True
        run.font.size = Pt(16)
        run.font.name = "Times New Roman"

        # Spacing
        for _ in range(3):
            doc.add_paragraph()

        # Document title
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(title)
        run.bold = True
        run.font.size = Pt(18)
        run.font.name = "Times New Roman"

        # Spacing
        for _ in range(3):
            doc.add_paragraph()

        # Status
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("Статус: Черновик")
        run.font.size = Pt(14)
        run.font.name = "Times New Roman"
        run.italic = True

        # Spacing
        doc.add_paragraph()

        # Date
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"Дата: {now}")
        run.font.size = Pt(14)
        run.font.name = "Times New Roman"

        # Page break to move to document content
        doc.add_page_break()

    # ── Table of Contents ────────────────────────────────────────────────────

    def _add_toc(self, doc: DocxDocument) -> None:
        """Add a Table of Contents field (auto-updates when opened in Word)."""
        # Heading
        doc.add_heading("Оглавление", level=1)

        # Create paragraph for TOC field
        paragraph = doc.add_paragraph()

        # TOC field: \o "1-3" = outline levels 1-3, \h = hyperlinks, \z = hide tab leader, \u = use applied style
        run = paragraph.add_run()
        fld_char_begin = run._element.makeelement(
            qn("w:fldChar"), {qn("w:fldCharType"): "begin"}
        )
        run._element.append(fld_char_begin)

        run2 = paragraph.add_run()
        instr_text = run2._element.makeelement(qn("w:instrText"), {})
        instr_text.text = ' TOC \\o "1-3" \\h \\z \\u '
        run2._element.append(instr_text)

        run3 = paragraph.add_run()
        fld_char_separate = run3._element.makeelement(
            qn("w:fldChar"), {qn("w:fldCharType"): "separate"}
        )
        run3._element.append(fld_char_separate)

        # Placeholder text (will be replaced when TOC is updated in Word)
        run4 = paragraph.add_run("[Обновите оглавление: правый клик → Обновить поле]")
        run4.font.color.rgb = None  # default color
        run4.font.size = Pt(11)
        run4.font.italic = True

        run5 = paragraph.add_run()
        fld_char_end = run5._element.makeelement(
            qn("w:fldChar"), {qn("w:fldCharType"): "end"}
        )
        run5._element.append(fld_char_end)

        # Page break after TOC
        doc.add_page_break()

    # ── Content blocks ──────────────────────────────────────────────────────

    def _add_description(self, doc: DocxDocument, description: str) -> None:
        """Add document description paragraph."""
        if not description:
            return
        paragraph = doc.add_paragraph()
        run = paragraph.add_run(description)
        run.font.size = Pt(12)
        run.font.name = "Times New Roman"
        paragraph.space_after = Pt(12)

    def _add_section(self, doc: DocxDocument, section: dict) -> None:
        """Add section with heading + content + subsections recursively."""
        title = section.get("title", "")
        content = section.get("content", "")
        level = section.get("level", 1)
        subsections = section.get("subsections", [])

        # Add heading
        doc.add_heading(title, level=min(level, 3))

        # Add content
        if content:
            paragraphs = content.split("\n")
            for para_text in paragraphs:
                if para_text.strip():
                    p = doc.add_paragraph(para_text.strip())
                    p.style.font.name = "Times New Roman"

        # Recursively add subsections
        for sub in subsections:
            self._add_section(doc, sub)

    def _add_terms_table(self, doc: DocxDocument, terms: list[dict]) -> None:
        """Add terms and definitions as a table."""
        if not terms:
            return

        table = doc.add_table(rows=1, cols=2)
        table.style = "Light Grid Accent 1"

        # Header row
        hdr = table.rows[0]
        hdr.cells[0].text = "Термин"
        hdr.cells[1].text = "Определение"
        self._set_cell_bold(hdr.cells[0])
        self._set_cell_bold(hdr.cells[1])

        for term_item in terms:
            row = table.add_row()
            row.cells[0].text = term_item.get("term", "")
            row.cells[1].text = term_item.get("definition", "")

        doc.add_paragraph()  # spacing

    def _add_abbreviations_table(self, doc: DocxDocument, abbreviations: list[dict]) -> None:
        """Add abbreviations table."""
        if not abbreviations:
            return

        table = doc.add_table(rows=1, cols=2)
        table.style = "Light Grid Accent 1"

        hdr = table.rows[0]
        hdr.cells[0].text = "Сокращение"
        hdr.cells[1].text = "Полная форма"
        self._set_cell_bold(hdr.cells[0])
        self._set_cell_bold(hdr.cells[1])

        for abbr_item in abbreviations:
            row = table.add_row()
            row.cells[0].text = abbr_item.get("abbreviation", "")
            row.cells[1].text = abbr_item.get("full_form", "")

        doc.add_paragraph()

    def _add_references_list(self, doc: DocxDocument, references: list[dict]) -> None:
        """Add numbered list of references."""
        for i, ref in enumerate(references, start=1):
            title = ref.get("title", "")
            source = ref.get("source", "")
            text = f"{i}. {title}"
            if source:
                text += f" — {source}"
            doc.add_paragraph(text, style="List Number")

    # ── Utilities ───────────────────────────────────────────────────────────

    def _set_cell_bold(self, cell) -> None:
        """Make cell text bold."""
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True

    def _apply_company_style(self, doc: DocxDocument, company: Company) -> None:
        """Apply company-specific styling (fonts, margins, etc.)."""
        if not company.style_settings:
            return

        style_settings = company.style_settings
        if not isinstance(style_settings, dict):
            try:
                import json
                style_settings = json.loads(str(style_settings))
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Invalid style_settings for company {company.id}")
                return

        try:
            font_name = style_settings.get("font_name")
            if font_name:
                style = doc.styles["Normal"]
                style.font.name = font_name

            font_size = style_settings.get("font_size")
            if font_size:
                style = doc.styles["Normal"]
                style.font.size = Pt(int(font_size))

            line_spacing = style_settings.get("line_spacing")
            if line_spacing:
                style = doc.styles["Normal"]
                style.paragraph_format.line_spacing = float(line_spacing)

            left_margin = style_settings.get("left_margin")
            if left_margin:
                for section in doc.sections:
                    section.left_margin = Cm(float(left_margin))

            right_margin = style_settings.get("right_margin")
            if right_margin:
                for section in doc.sections:
                    section.right_margin = Cm(float(right_margin))

            top_margin = style_settings.get("top_margin")
            if top_margin:
                for section in doc.sections:
                    section.top_margin = Cm(float(top_margin))

            bottom_margin = style_settings.get("bottom_margin")
            if bottom_margin:
                for section in doc.sections:
                    section.bottom_margin = Cm(float(bottom_margin))

        except Exception as e:
            logger.warning(f"Failed to apply holding style: {e}")

    def _apply_gost(self, doc: DocxDocument) -> None:
        """Apply GOST R 7.0.97-2016 formatting.

        GOST R 7.0.97-2016 requirements:
        - Font: Times New Roman, 14pt
        - Line spacing: 1.5
        - Margins: left 30mm, right 15mm, top 20mm, bottom 20mm
        - Page numbers: bottom center
        """
        # Font and spacing already set in _setup_default_style

        # Margins
        for section in doc.sections:
            section.left_margin = Cm(3.0)
            section.right_margin = Cm(1.5)
            section.top_margin = Cm(2.0)
            section.bottom_margin = Cm(2.0)

    def _add_page_numbers(self, doc: DocxDocument) -> None:
        """Add page numbers to footer (bottom center)."""
        for section in doc.sections:
            footer = section.footer
            footer.is_linked_to_previous = False
            paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Add page number field
            run = paragraph.add_run()
            fldChar1 = run._element.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "begin"})
            run._element.append(fldChar1)

            run2 = paragraph.add_run()
            instrText = run2._element.makeelement(qn("w:instrText"), {})
            instrText.text = " PAGE "
            run2._element.append(instrText)

            run3 = paragraph.add_run()
            fldChar2 = run3._element.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "end"})
            run3._element.append(fldChar2)


# Singleton
docx_builder = DocxBuilder()
