"""
Generate sample documents for testing.
Run: python tests/test_data/generate_samples.py
"""

import os


def generate_sample_docx(path: str):
    """Generate a minimal .docx file with headings, paragraphs, and a table."""
    from docx import Document
    from docx.shared import Pt, Inches

    doc = Document()

    # Title heading
    doc.add_heading("Тестовый документ", level=1)

    # Introduction paragraph
    doc.add_paragraph(
        "Настоящий документ является тестовым для проверки парсинга документов."
    )

    # Section 1
    doc.add_heading("Общие положения", level=1)
    doc.add_paragraph(
        "Настоящий регламент устанавливает порядок взаимодействия между подразделениями."
    )

    # Subsection 1.1
    doc.add_heading("Область применения", level=2)
    doc.add_paragraph(
        "Настоящий регламент распространяется на все подразделения холдинга."
    )

    # Subsection 1.2
    doc.add_heading("Нормативные ссылки", level=2)
    doc.add_paragraph(
        "ГОСТ Р 7.0.97-2016 Система стандартов по информации, библиотечному и издательскому делу."
    )

    # Section 2 - Terms
    doc.add_heading("Термины и определения", level=1)
    doc.add_paragraph(
        "Регламент — документ, устанавливающий порядок выполнения бизнес-процессов."
    )
    doc.add_paragraph(
        "Холдинг — совокупность юридических лиц, связанных отношениями управления."
    )
    doc.add_paragraph(
        "Подразделение — структурная единица холдинга, выполняющая определённые функции."
    )

    # Section 3 - Abbreviations
    doc.add_heading("Сокращения", level=1)
    doc.add_paragraph(
        "ООО — Общество с ограниченной ответственностью"
    )
    doc.add_paragraph(
        "АО — Акционерное общество"
    )
    doc.add_paragraph(
        "СЭД (Система электронного документооборота)"
    )

    # Section 4
    doc.add_heading("Порядок взаимодействия", level=1)
    doc.add_paragraph(
        "Взаимодействие между подразделениями осуществляется через СЭД."
    )

    # Subsection 4.1
    doc.add_heading("Обмен документами", level=2)
    doc.add_paragraph(
        "Передача документов осуществляется в электронном виде."
    )

    # Add a table
    doc.add_heading("Формы документов", level=2)
    table = doc.add_table(rows=4, cols=3)
    table.style = 'Table Grid'

    # Header
    hdr = table.rows[0].cells
    hdr[0].text = 'Код формы'
    hdr[1].text = 'Наименование'
    hdr[2].text = 'Срок хранения'

    # Data rows
    data = [
        ('Ф-001', 'Заявка на закупку', '5 лет'),
        ('Ф-002', 'Акт приёма-передачи', '3 года'),
        ('Ф-003', 'Служебная записка', '1 год'),
    ]
    for i, (code, name, period) in enumerate(data):
        row = table.rows[i + 1].cells
        row[0].text = code
        row[1].text = name
        row[2].text = period

    # Section 5 - Another with terms
    doc.add_heading("Заключительные положения", level=1)
    doc.add_paragraph(
        "Настоящий регламент вступает в силу с даты утверждения."
    )

    doc.save(path)
    print(f"Generated sample DOCX at: {path}")


def generate_sample_pdf(path: str):
    """Generate a minimal PDF file with text content."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        # Fallback: try fpdf2
        try:
            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=12)
            pdf.cell(200, 10, text="Test Document", new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.set_font("Helvetica", size=10)
            pdf.cell(200, 10, text="This is a test PDF document.", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(200, 10, text="Section 1: General Provisions", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(200, 10, text="This regulation establishes the order.", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(200, 10, text="Terms and definitions:", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(200, 10, text="Regulation - a document that establishes.", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(200, 10, text="Abbreviations:", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(200, 10, text="LLC - Limited Liability Company", new_x="LMARGIN", new_y="NEXT")
            pdf.output(path)
            print(f"Generated sample PDF at: {path}")
            return
        except ImportError:
            print("WARNING: Neither reportlab nor fpdf2 available. Generating empty PDF.")
            # Create a minimal valid PDF manually
            pdf_content = (
                b"%PDF-1.4\n"
                b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
                b"xref\n"
                b"0 4\n"
                b"0000000000 65535 f \n"
                b"0000000009 00000 n \n"
                b"0000000058 00000 n \n"
                b"0000000115 00000 n \n"
                b"trailer<</Size 4/Root 1 0 R>>\n"
                b"startxref\n"
                b"190\n"
                b"%%EOF"
            )
            with open(path, "wb") as f:
                f.write(pdf_content)
            print(f"Generated minimal PDF at: {path}")
            return

    # Use reportlab
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Test Document")
    c.setFont("Helvetica", 12)
    c.drawString(100, 720, "This is a test PDF document for parsing tests.")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 690, "Section 1: General Provisions")
    c.setFont("Helvetica", 12)
    c.drawString(100, 660, "This regulation establishes the order of interaction.")
    c.drawString(100, 640, "Terms and definitions:")
    c.drawString(120, 620, "Regulation - a document that establishes business processes.")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 590, "Abbreviations:")
    c.setFont("Helvetica", 12)
    c.drawString(120, 570, "LLC - Limited Liability Company")
    c.drawString(120, 550, "JSC (Joint Stock Company)")
    c.save()
    print(f"Generated sample PDF at: {path}")


if __name__ == "__main__":
    data_dir = os.path.dirname(os.path.abspath(__file__))
    generate_sample_docx(os.path.join(data_dir, "sample.docx"))
    generate_sample_pdf(os.path.join(data_dir, "sample.pdf"))
    print("Done!")
