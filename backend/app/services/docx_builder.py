"""
Docx builder service.

Converts structured generation result (JSON) into a .docx file.
Uses python-docx library.

Supports:
  - Title, description, sections/subsections
  - Terms and definitions table
  - Abbreviations table
  - References list
  - Holding-specific styling (fonts, margins)
  - GOST R 7.0.97-2016 formatting
"""

import logging
import os
from typing import Optional

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from docx.oxml.ns import qn

from app.models.holding import Holding

logger = logging.getLogger(__name__)


class DocxBuilder:
    """Converts structured generation result (JSON) into .docx file."""

    def build(
        self,
        result: dict,
        holding: Holding,
        output_path: str,
    ) -> str:
        """Build .docx from generation result.

        Args:
            result: Parsed generation result with title, sections, terms, etc.
            holding: Holding profile for styling.
            output_path: Full path where the .docx file will be saved.

        Returns:
            The output_path where the file was saved.
        """
        doc = DocxDocument()

        # Apply base styling
        self._setup_default_style(doc)

        # Apply GOST if enabled
        if holding.use_gost:
            self._apply_gost(doc)

        # Apply holding-specific style
        self._apply_holding_style(doc, holding)

        # Build document content
        self._add_title(doc, result.get("title", "Документ"))
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

    def _add_title(self, doc: DocxDocument, title: str) -> None:
        """Add document title (centered, bold, 14pt)."""
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(title)
        run.bold = True
        run.font.size = Pt(14)
        run.font.name = "Times New Roman"
        paragraph.space_after = Pt(12)

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
        heading = doc.add_heading(title, level=min(level, 3))

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

    def _set_cell_bold(self, cell) -> None:
        """Make cell text bold."""
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True

    def _apply_holding_style(self, doc: DocxDocument, holding: Holding) -> None:
        """Apply holding-specific styling (fonts, margins, etc.)."""
        if not holding.style_settings:
            return

        style_settings = holding.style_settings
        if not isinstance(style_settings, dict):
            try:
                import json
                style_settings = json.loads(str(style_settings))
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Invalid style_settings for holding {holding.id}")
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

        # Page number in footer (bottom center)
        self._add_page_numbers(doc)

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
            instrText = run2._element.makeelement(
                qn("w:instrText"), {}
            )
            instrText.text = " PAGE "
            run2._element.append(instrText)

            run3 = paragraph.add_run()
            fldChar2 = run3._element.makeelement(qn("w:fldChar"), {qn("w:fldCharType"): "end"})
            run3._element.append(fldChar2)


# Singleton
docx_builder = DocxBuilder()
