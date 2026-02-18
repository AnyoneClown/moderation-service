"""
app/services/pdf_service.py — PDF report generation for moderation results.

Uses ReportLab to produce a clean, single-page (or multi-page) PDF
containing the full moderation breakdown for a given record.
Supports English and Ukrainian via the ``lang`` parameter.
Uses DejaVu Sans TTF font for full Cyrillic/Ukrainian support.
"""

import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from app.i18n import get_translations

# ── Register DejaVu Sans (Cyrillic-capable) TTF fonts ──
_FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_FONT_REGISTERED = False

def _register_fonts():
    """Register DejaVu Sans TTF fonts for Cyrillic support (once)."""
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    regular = os.path.join(_FONT_DIR, "DejaVuSans.ttf")
    bold = os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")
    if os.path.exists(regular):
        pdfmetrics.registerFont(TTFont("DejaVu", regular))
    if os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
    _FONT_REGISTERED = True

_CYR_FONT = "DejaVu"
_CYR_FONT_BOLD = "DejaVu-Bold"


# ── Colour palette ──
_GREEN = colors.HexColor("#16a34a")
_YELLOW = colors.HexColor("#ca8a04")
_RED = colors.HexColor("#dc2626")
_INDIGO = colors.HexColor("#4f46e5")
_GRAY = colors.HexColor("#6b7280")
_LIGHT_GRAY = colors.HexColor("#f3f4f6")
_WHITE = colors.white


def _status_colour(status: str) -> colors.Color:
    return {"APPROVED": _GREEN, "FLAGGED": _YELLOW, "REJECTED": _RED}.get(status, _GRAY)


def _bar_text(score: float | None) -> str:
    """Return a simple ASCII bar + percentage for the PDF table."""
    if score is None:
        return "N/A"
    pct = int(score * 100)
    filled = pct // 5  # 20-char bar
    return f"{'█' * filled}{'░' * (20 - filled)}  {pct}%"


# ────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────

def generate_pdf(record, lang: str = "en") -> bytes:
    """
    Generate a PDF report for a ``ModerationRecord`` ORM object.

    Returns the raw PDF bytes (ready to be sent as an HTTP response).
    """
    t = get_translations(lang)
    _register_fonts()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # ── Custom styles (DejaVu Sans for full Cyrillic support) ──
    title_style = ParagraphStyle(
        "PDFTitle",
        parent=styles["Title"],
        fontName=_CYR_FONT_BOLD,
        fontSize=22,
        textColor=_INDIGO,
        spaceAfter=4 * mm,
    )
    subtitle_style = ParagraphStyle(
        "PDFSubtitle",
        parent=styles["Normal"],
        fontName=_CYR_FONT,
        fontSize=10,
        textColor=_GRAY,
        spaceAfter=6 * mm,
    )
    heading_style = ParagraphStyle(
        "PDFHeading",
        parent=styles["Heading2"],
        fontName=_CYR_FONT_BOLD,
        fontSize=13,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    )
    body_style = ParagraphStyle(
        "PDFBody",
        parent=styles["Normal"],
        fontName=_CYR_FONT,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#374151"),
    )
    small_style = ParagraphStyle(
        "PDFSmall",
        parent=styles["Normal"],
        fontName=_CYR_FONT,
        fontSize=8,
        textColor=_GRAY,
    )

    elements: list = []

    # ── Header ──
    elements.append(Paragraph(t["pdf_title"], title_style))
    created = record.created_at
    if created.tzinfo is None:
        pass  # naive datetime — use as-is
    elements.append(
        Paragraph(
            f"{t['pdf_generated_from']} "
            f"{created.strftime('%Y-%m-%d at %H:%M:%S UTC')}",
            subtitle_style,
        )
    )
    elements.append(HRFlowable(width="100%", thickness=0.5, color=_LIGHT_GRAY))
    elements.append(Spacer(1, 4 * mm))

    # ── Verdict ──
    status_color = _status_colour(record.status)
    elements.append(Paragraph(t["final_verdict"], heading_style))
    verdict_data = [
        [
            Paragraph(f'<font color="{status_color.hexval()}" size="18"><b>{record.status}</b></font>', body_style),
            Paragraph(f'<font size="14"><b>{record.final_score:.4f}</b></font>', body_style),
        ],
        [
            Paragraph(t["col_status"], small_style),
            Paragraph(t["aggregate_score"] + " (0–1)", small_style),
        ],
    ]
    verdict_table = Table(verdict_data, colWidths=["50%", "50%"])
    verdict_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_GRAY),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
    ]))
    elements.append(verdict_table)
    elements.append(Spacer(1, 4 * mm))

    # ── Partial warning ──
    if record.is_partial == "true":
        elements.append(
            Paragraph(
                f'<font color="#b45309"><b>{t["pdf_partial_warning"]}</b></font>',
                body_style,
            )
        )
        elements.append(Spacer(1, 3 * mm))

    # ── Input type ──
    input_type = getattr(record, "input_type", "text") or "text"
    elements.append(Paragraph(f"{t['pdf_input_type']} <b>{input_type.upper()}</b>", body_style))
    elements.append(Spacer(1, 2 * mm))

    # ── Submitted text ──
    if record.text:
        elements.append(Paragraph(t["pdf_submitted_text"], heading_style))
        # Wrap long text to avoid overflow
        safe_text = record.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        elements.append(Paragraph(safe_text, body_style))
        elements.append(Spacer(1, 4 * mm))

    # ── Source score breakdown ──
    elements.append(Paragraph(t["pdf_score_breakdown"], heading_style))

    score_data = [
        [
            Paragraph(f"<b>{t['pdf_col_source']}</b>", small_style),
            Paragraph(f"<b>{t['pdf_col_score']}</b>", small_style),
            Paragraph(f"<b>{t['pdf_col_visual']}</b>", small_style),
        ],
    ]

    sources = [
        (t["lbl_toxicity"], record.toxicity_score),
        (t["lbl_spam"], record.spam_score),
        (t["lbl_profanity"], record.profanity_score),
        (t["lbl_fraud"], record.fraud_score),
        (t["lbl_sentiment"], record.sentiment_score),
    ]

    for label, score in sources:
        score_str = f"{score:.4f}" if score is not None else "N/A"
        bar_str = _bar_text(score)
        score_data.append([
            Paragraph(label, body_style),
            Paragraph(f"<b>{score_str}</b>", body_style),
            Paragraph(f'<font face="{_CYR_FONT}" size="8">{bar_str}</font>', body_style),
        ])

    score_table = Table(score_data, colWidths=["30%", "15%", "55%"])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _INDIGO),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, _LIGHT_GRAY]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Footer / metadata ──
    elements.append(HRFlowable(width="100%", thickness=0.5, color=_LIGHT_GRAY))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(f"{t['pdf_record_id']} {record.id}", small_style))
    elements.append(
        Paragraph(
            f"{t['pdf_analysed_at']} {created.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            small_style,
        )
    )
    elements.append(
        Paragraph(t["pdf_footer"], small_style)
    )

    doc.build(elements)
    return buf.getvalue()
