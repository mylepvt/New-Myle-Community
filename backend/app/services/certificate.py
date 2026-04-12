"""Training certificate PDF generation service."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import black, darkblue, gold, white
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


async def generate_certificate_pdf(
    username: str,
    fbo_id: str | None,
    completion_date: datetime,
    test_score: int,
    test_total: int,
) -> bytes:
    """
    Generate a professional training certificate PDF.
    
    Args:
        username: User's display name
        fbo_id: User's FBO ID (optional)
        completion_date: Date of training completion
        test_score: Test score achieved
        test_total: Total test questions
    
    Returns:
        PDF file as bytes
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
    
    # Custom styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=darkblue,
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=black,
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=14,
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    
    signature_style = ParagraphStyle(
        'CustomSignature',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        alignment=TA_CENTER,
        textColor=black,
    )
    
    # Build certificate content
    story = []
    
    # Certificate border and header
    story.append(Spacer(1, 0.5*inch))
    
    # Title
    story.append(Paragraph("Certificate of Completion", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Subtitle
    story.append(Paragraph("Myle Community Training Program", subtitle_style))
    story.append(Spacer(1, 0.4*inch))
    
    # Main certificate text
    cert_text = f"""
    <b>This is to certify that</b><br/>
    <b><font size=18>{username.upper()}</font></b><br/>
    has successfully completed the 7-day training program<br/>
    and passed the certification examination.
    """
    story.append(Paragraph(cert_text, body_style))
    story.append(Spacer(1, 0.4*inch))
    
    # Certificate details table
    details_data = [
        ['FBO ID:', fbo_id or 'N/A'],
        ['Completion Date:', completion_date.strftime('%d %B %Y')],
        ['Test Score:', f'{test_score}/{test_total} ({int(test_score/test_total*100)}%)'],
        ['Program Duration:', '7 Days'],
        ['Certificate ID:', f'MYLE-{completion_date.year}-{username.upper()}'],
    ]
    
    details_table = Table(details_data, colWidths=[2*inch, 3*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), white),
        ('TEXTCOLOR', (0, 0), (-1, -1), black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(details_table)
    story.append(Spacer(1, 0.6*inch))
    
    # Achievement statement
    achievement_text = """
    <b>Achievement:</b> Demonstrated comprehensive understanding of<br/>
    the Myle Community business model, sales techniques,<br/>
    and team leadership principles.
    """
    story.append(Paragraph(achievement_text, body_style))
    story.append(Spacer(1, 0.8*inch))
    
    # Signature section
    signature_data = [
        ['', '', ''],
        ['_________________________', '', '_________________________'],
        [Paragraph('Participant Signature', signature_style), '', Paragraph('Authorized Signatory', signature_style)],
        [Paragraph(username, signature_style), '', Paragraph('Myle Community', signature_style)],
    ]
    
    signature_table = Table(signature_data, colWidths=[2.5*inch, 1*inch, 2.5*inch])
    signature_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), white),
        ('TEXTCOLOR', (0, 0), (-1, -1), black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    
    story.append(signature_table)
    story.append(Spacer(1, 0.4*inch))
    
    # Footer note
    footer_text = """
    <font size=10>This certificate is issued upon successful completion of the Myle Community<br/>
    training program and is valid for professional recognition within the organization.</font>
    """
    story.append(Paragraph(footer_text, signature_style))
    
    # Generate PDF
    doc.build(story)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def _create_certificate_background(canvas: canvas.Canvas, width: float, height: float) -> None:
    """Create decorative background for certificate."""
    # Draw border
    canvas.setStrokeColor(darkblue)
    canvas.setLineWidth(2)
    canvas.rect(50, 50, width - 100, height - 100)
    
    # Draw inner border
    canvas.setStrokeColor(gold)
    canvas.setLineWidth(1)
    canvas.rect(60, 60, width - 120, height - 120)
    
    # Add decorative elements
    canvas.setFillColor(darkblue)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawCentredText(width/2, height - 80, "MYLE COMMUNITY")
    
    canvas.setFont("Helvetica", 10)
    canvas.drawCentredText(width/2, height - 100, "Training Excellence Certificate")
