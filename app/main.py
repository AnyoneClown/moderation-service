"""
app/main.py — Application entry-point and route definitions.

Responsibilities:
  1. Initialise the FastAPI application and Jinja2 templates.
  2. Create database tables on startup.
  3. Define routes:
       GET  /          → Dashboard (submit text for moderation)
       POST /moderate  → Process text, store result, redirect to result
       GET  /result/id → Detailed moderation result
       GET  /history   → List all past moderation records
       GET  /health    → Healthcheck endpoint for Docker
       GET  /api/records → JSON API for fetching records
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import init_db, get_db
from app.models.moderation import ModerationRecord
from app.services.aggregator import aggregate_moderation

# ── Logging configuration ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


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
templates = Jinja2Templates(directory="templates")


# ────────────────────────────────────────────────────────────
# ROUTES
# ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Simple healthcheck used by Docker Compose."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main input form."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.post("/moderate")
async def moderate_text(
    request: Request,
    text: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Core endpoint — receives user text, runs the 5-source moderation
    pipeline, stores results in PostgreSQL, and redirects to result page.
    """
    logger.info("Received moderation request (%d chars).", len(text))

    # ── Run all five moderation checks concurrently ──
    result = await aggregate_moderation(text)

    # ── Persist to database ──
    record = ModerationRecord(
        text=result["text"],
        toxicity_score=result["toxicity"]["score"],
        spam_score=result["spam"]["score"],
        profanity_score=result["profanity"]["score"],
        fraud_score=result["fraud"]["score"],
        sentiment_score=result["sentiment"]["score"],
        toxicity_details=result["toxicity"].get("details"),
        spam_details=result["spam"].get("details"),
        profanity_details=result["profanity"].get("details"),
        fraud_details=result["fraud"].get("details"),
        sentiment_details=result["sentiment"].get("details"),
        final_score=result["final_score"],
        status=result["status"],
        is_partial="true" if result["is_partial"] else "false",
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()

    logger.info("Moderation complete → %s (score=%.4f, partial=%s)",
                result["status"], result["final_score"], result["is_partial"])

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
            {"request": request, "message": "Record not found."},
            status_code=404,
        )

    return templates.TemplateResponse(
        "result.html", {"request": request, "record": record}
    )


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request, db: AsyncSession = Depends(get_db)):
    """List all past moderation records, newest first."""
    stmt = select(ModerationRecord).order_by(ModerationRecord.created_at.desc()).limit(100)
    rows = await db.execute(stmt)
    records = rows.scalars().all()

    return templates.TemplateResponse(
        "history.html", {"request": request, "records": records}
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
            "text": r.text[:120],
            "status": r.status,
            "final_score": r.final_score,
            "is_partial": r.is_partial,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
