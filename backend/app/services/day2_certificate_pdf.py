"""Landscape PDF for Day 2 Business Evaluation — Certificate of Qualification."""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _wrap_lines(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        trial = " ".join(cur + [word])
        if len(trial) <= max_chars:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines


def _corner_accents(c, w: float, h: float, m: float, inner: float, span: float) -> None:
    """Light gold L-shaped corner marks (outer frame)."""
    c.saveState()
    c.setStrokeColor(colors.Color(0.72, 0.55, 0.12, alpha=1))
    c.setLineWidth(1.1)
    o = m + inner + 2 * mm
    # top-left
    c.line(o, h - o, o + span, h - o)
    c.line(o, h - o, o, h - o - span)
    # top-right
    c.line(w - o, h - o, w - o - span, h - o)
    c.line(w - o, h - o, w - o, h - o - span)
    # bottom-left
    c.line(o, o, o + span, o)
    c.line(o, o, o, o + span)
    # bottom-right
    c.line(w - o, o, w - o - span, o)
    c.line(w - o, o, w - o, o + span)
    c.restoreState()


def build_day2_business_certificate_pdf(
    recipient_name: str,
    score: int,
    total_questions: int,
    date_display: str,
) -> bytes:
    recipient_name = (recipient_name or "").strip() or "Participant"
    date_display = (date_display or "").strip() or "—"
    w, h = landscape(A4)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    c.setFillColorRGB(0.992, 0.969, 0.902)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    margin = 16 * mm
    inner = 5 * mm
    span = 11 * mm

    c.setStrokeColorRGB(0.05, 0.05, 0.05)
    c.setLineWidth(2.2)
    c.rect(margin, margin, w - 2 * margin, h - 2 * margin, fill=0, stroke=1)

    c.setStrokeColor(colors.Color(0.72, 0.55, 0.12, alpha=1))
    c.setLineWidth(1.2)
    c.rect(
        margin + inner,
        margin + inner,
        w - 2 * margin - 2 * inner,
        h - 2 * margin - 2 * inner,
        fill=0,
        stroke=1,
    )
    _corner_accents(c, w, h, margin, inner, span)

    c.saveState()
    c.setFillColor(colors.Color(0.78, 0.68, 0.35, alpha=0.14))
    c.setFont("Helvetica-Bold", 98)
    c.drawCentredString(w / 2, h / 2 - 8 * mm, "MYLE")
    c.restoreState()

    c.setFillColorRGB(0.55, 0.42, 0.08)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(w / 2, h - margin - 20 * mm, "M")

    c.setFillColorRGB(0.08, 0.08, 0.08)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(w / 2, h - margin - 30 * mm, "MYLE COMMUNITY")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(w / 2, h - margin - 38 * mm, "CERTIFICATE OF QUALIFICATION")

    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, h - margin - 48 * mm, "This is to certify that")

    c.setFont("Helvetica-Bold", 16)
    name_y = h - margin - 58 * mm
    c.drawCentredString(w / 2, name_y, recipient_name)
    nw = c.stringWidth(recipient_name, "Helvetica-Bold", 16)
    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.setLineWidth(0.9)
    underline_y = name_y - 2 * mm
    c.line(w / 2 - nw / 2, underline_y, w / 2 + nw / 2, underline_y)

    body = (
        "has successfully completed the Day 2 Business Evaluation Process and demonstrated the required "
        "understanding, discipline, and clarity to move forward within the MYLE Community system. "
        "This certification confirms eligibility for the Interview Stage."
    )
    c.setFont("Helvetica", 9)
    y_line = h - margin - 70 * mm
    for line in _wrap_lines(body, 96):
        c.drawCentredString(w / 2, y_line, line)
        y_line -= 4.2 * mm

    y_block = y_line - 10 * mm
    bx_w = 132 * mm
    bx_l = w / 2 - bx_w / 2
    rows = [
        ("Score Achieved", f"{score} / {total_questions}"),
        ("Status", "Approved for Interview Stage"),
        ("Date", date_display),
    ]
    c.setFont("Helvetica", 9)
    for i, (lbl, val) in enumerate(rows):
        yy = y_block - i * 9.5 * mm
        c.setStrokeColorRGB(0.25, 0.25, 0.25)
        c.setLineWidth(0.55)
        c.line(bx_l, yy + 8 * mm, bx_l + bx_w, yy + 8 * mm)
        c.drawString(bx_l + 1.5 * mm, yy + 1.2 * mm, lbl)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(bx_l + bx_w - 1.5 * mm, yy + 1.2 * mm, val)
        c.setFont("Helvetica", 9)

    seal_x = w / 2
    seal_y = margin + 20 * mm
    c.setFillColor(colors.Color(0.86, 0.71, 0.20, alpha=0.92))
    c.setStrokeColorRGB(0.45, 0.35, 0.08)
    c.setLineWidth(1)
    c.circle(seal_x, seal_y, 12 * mm, fill=1, stroke=1)
    c.setFillColorRGB(0.18, 0.14, 0.06)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(seal_x, seal_y - 5 * mm, "M")

    sig_y = margin + 42 * mm
    sig_left = margin + 20 * mm
    sig_right = w - margin - 20 * mm
    c.setFillColorRGB(0.12, 0.12, 0.12)
    c.setFont("Helvetica", 8)
    c.drawString(sig_left, sig_y + 8 * mm, "Certified by:")
    c.setFont("Helvetica-Oblique", 11)
    c.drawString(sig_left, sig_y + 2 * mm, "Karanveer Singh")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(sig_left, sig_y - 3 * mm, "CEO & Founder · MYLE Community")

    c.setFont("Helvetica-Oblique", 11)
    c.drawRightString(sig_right, sig_y + 2 * mm, "Shikha Chaudhry")
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(sig_right, sig_y - 3 * mm, "Management · MYLE Community")

    c.showPage()
    c.save()
    return buf.getvalue()
