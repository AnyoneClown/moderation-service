"""
app/main.py — Application entry-point and route definitions.

Responsibilities:
  1. Initialise the FastAPI application and Jinja2 templates.
  2. Create database tables on startup.
  3. Define routes:
       GET  /              → Dashboard (submit text / image for moderation)
       POST /moderate      → Process content, store result, redirect to result
       GET  /result/id     → Detailed moderation result
       GET  /result/id/pdf → Download PDF report
       GET  /history       → List all past moderation records
       GET  /health        → Healthcheck endpoint for Docker
       GET  /api/records   → JSON API for fetching records
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import init_db, get_db
from app.models.moderation import ModerationRecord
from app.services.aggregator import aggregate_moderation
from app.services.pdf_service import generate_pdf
from app.i18n import get_translations, DEFAULT_LANGUAGE

# ── Logging configuration ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ── Uploads directory ──
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Lifespan: startup / shutdown logic ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs DB table creation on startup and downloads NLTK data."""
    logger.info("🚀  Starting %s v%s", settings.APP_TITLE, settings.APP_VERSION)
    await init_db()
    logger.info("✅  Database tables ensured.")

    # Pre-download VADER lexicon (used by sentiment_service)
    import nltk
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)
    logger.info("✅  NLTK VADER lexicon ready.")

    yield
    logger.info("🛑  Shutting down.")


# ── FastAPI application instance ──
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ── Static files & Jinja2 templates ──
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")


def _lang(request: Request) -> str:
    """Read the preferred language from the ``lang`` cookie."""
    return request.cookies.get("lang", DEFAULT_LANGUAGE)


def _ctx(request: Request, **extra) -> dict:
    """Build a template context with translations + any extra vars."""
    lang = _lang(request)
    return {"request": request, "t": get_translations(lang), "lang": lang, **extra}


# ────────────────────────────────────────────────────────────
# ROUTES
# ────────────────────────────────────────────────────────────

@app.get("/set-lang/{lang}")
async def set_language(lang: str, request: Request):
    """Set the UI language via a cookie and redirect back."""
    if lang not in ("en", "uk"):
        lang = "en"
    referer = request.headers.get("referer", "/")
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie("lang", lang, max_age=365 * 24 * 3600, samesite="lax")
    return response

@app.get("/health")
async def health():
    """Simple healthcheck used by Docker Compose."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main input form."""
    return templates.TemplateResponse("dashboard.html", _ctx(request))


@app.post("/moderate")
async def moderate_text(
    request: Request,
    text: str = Form(""),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Core endpoint — receives user text and/or image, runs the moderation
    pipeline, stores results in PostgreSQL, and redirects to result page.
    """
    # ── Validate that at least one input is provided ──
    has_text = bool(text and text.strip())
    has_image = bool(image and image.filename)

    t = get_translations(_lang(request))

    if not has_text and not has_image:
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, message=t["err_no_input"]),
            status_code=400,
        )

    logger.info("Received moderation request (text=%d chars, image=%s).",
                len(text) if text else 0, bool(has_image))

    # ── Read & save uploaded image ──
    image_bytes: bytes | None = None
    image_filename: str | None = None

    if has_image:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            return templates.TemplateResponse(
                "error.html",
                _ctx(request, message=f"{t['err_unsupported_image']} {image.content_type}"),
                status_code=400,
            )
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_SIZE:
            return templates.TemplateResponse(
                "error.html",
                _ctx(request, message=t["err_image_too_large"]),
                status_code=400,
            )
        ext = image.filename.rsplit(".", 1)[-1].lower() if "." in image.filename else "bin"
        image_filename = f"{uuid.uuid4().hex}.{ext}"
        (UPLOAD_DIR / image_filename).write_bytes(image_bytes)

    # ── Run moderation checks ──
    result = await aggregate_moderation(
        text=text if has_text else None,
        image_bytes=image_bytes,
    )

    # ── Extract image sub-scores ──
    img = result.get("image")
    image_nsfw_score = None
    image_scam_score = None
    image_details = None
    if img is not None:
        nsfw = img.get("nsfw", {})
        caption = img.get("caption", {})
        image_nsfw_score = nsfw.get("score")
        image_scam_score = caption.get("scam_score")
        image_details = img

    # ── Persist to database ──
    record = ModerationRecord(
        text=result["text"],
        input_type=result["input_type"],
        image_filename=image_filename,
        toxicity_score=result["toxicity"]["score"],
        spam_score=result["spam"]["score"],
        profanity_score=result["profanity"].get("score", 0.0) if has_text else None,
        fraud_score=result["fraud"].get("score", 0.0) if has_text else None,
        sentiment_score=result["sentiment"].get("score", 0.0) if has_text else None,
        image_nsfw_score=image_nsfw_score,
        image_scam_score=image_scam_score,
        toxicity_details=result["toxicity"].get("details"),
        spam_details=result["spam"].get("details"),
        profanity_details=result["profanity"].get("details"),
        fraud_details=result["fraud"].get("details"),
        sentiment_details=result["sentiment"].get("details"),
        image_details=image_details,
        final_score=result["final_score"],
        status=result["status"],
        is_partial="true" if result["is_partial"] else "false",
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()

    logger.info("Moderation complete → %s (score=%.4f, partial=%s, type=%s)",
                result["status"], result["final_score"], result["is_partial"],
                result["input_type"])

    # ── Redirect to the result page ──
    return RedirectResponse(url=f"/result/{record.id}", status_code=303)


@app.get("/result/{record_id}", response_class=HTMLResponse)
async def result_page(
    request: Request,
    record_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Show detailed moderation result for a single record."""
    stmt = select(ModerationRecord).where(ModerationRecord.id == record_id)
    row = await db.execute(stmt)
    record = row.scalar_one_or_none()

    if record is None:
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, message=get_translations(_lang(request))["err_not_found"]),
            status_code=404,
        )

    return templates.TemplateResponse(
        "result.html", _ctx(request, record=record)
    )


@app.get("/result/{record_id}/pdf")
async def result_pdf(
    request: Request,
    record_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate and download a PDF report for a moderation record."""
    stmt = select(ModerationRecord).where(ModerationRecord.id == record_id)
    row = await db.execute(stmt)
    record = row.scalar_one_or_none()

    if record is None:
        return Response(content="Record not found", status_code=404)

    lang = _lang(request)
    pdf_bytes = generate_pdf(record, lang=lang)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="moderation-report-{record_id}.pdf"'
        },
    )


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request, db: AsyncSession = Depends(get_db)):
    """List all past moderation records, newest first."""
    stmt = select(ModerationRecord).order_by(ModerationRecord.created_at.desc()).limit(100)
    rows = await db.execute(stmt)
    records = rows.scalars().all()

    return templates.TemplateResponse(
        "history.html", _ctx(request, records=records)
    )


@app.get("/api/records")
async def api_records(db: AsyncSession = Depends(get_db)):
    """JSON API — returns the latest 100 moderation records."""
    stmt = select(ModerationRecord).order_by(ModerationRecord.created_at.desc()).limit(100)
    rows = await db.execute(stmt)
    records = rows.scalars().all()

    return [
        {
            "id": str(r.id),
            "text": (r.text or "")[:120],
            "input_type": r.input_type or "text",
            "has_image": bool(r.image_filename),
            "status": r.status,
            "final_score": r.final_score,
            "is_partial": r.is_partial,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
