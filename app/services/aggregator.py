"""
app/services/aggregator.py — Scoring aggregator & decision engine.

Combines results from **five text** moderation sources into a single weighted score
and maps it to a human-readable status: APPROVED, FLAGGED, or REJECTED.

Text scoring weights:
    ┌─────────────────────┬────────┐
    │ Source               │ Weight │
    ├─────────────────────┼────────┤
    │ HuggingFace Toxicity │  0.25  │
    │ HuggingFace Spam     │  0.20  │
    │ Profanity Filter     │  0.20  │
    │ Fraud Detector       │  0.25  │
    │ Sentiment (VADER)    │  0.10  │
    └─────────────────────┴────────┘

Decision thresholds:
    score < 0.25  → APPROVED
    score < 0.55  → FLAGGED
    score ≥ 0.55  → REJECTED

Critical-score overrides (applied *after* the weighted average):
    Any single source score ≥ 0.75  → at least REJECTED
    Any single source score ≥ 0.45  → at least FLAGGED

This prevents obvious fraud/spam/toxicity from being diluted
into an APPROVED verdict when the other sources score low.

If an external API is unavailable the weight is redistributed among
the remaining sources so that the final score is still on a 0–1 scale.
"""

import asyncio
import html as html_module
import logging
from typing import Optional

from app.services.hf_service import check_hf_spam
from app.services.hf_toxicity_service import check_hf_toxicity
from app.services.profanity_service import check_profanity
from app.services.fraud_service import check_fraud
from app.services.sentiment_service import check_sentiment

logger = logging.getLogger(__name__)

# ── Weight configuration (text sources) ──
WEIGHTS = {
    "toxicity": 0.25,
    "spam": 0.20,
    "profanity": 0.20,
    "fraud": 0.25,
    "sentiment": 0.10,
}

# ── Decision thresholds ──
THRESHOLD_APPROVED = 0.25
THRESHOLD_FLAGGED = 0.55  # scores ≥ this are REJECTED

# ── Critical single-source overrides ──
# If ANY individual source score meets these thresholds the verdict
# is elevated regardless of the weighted average.
CRITICAL_REJECT = 0.75   # single source ≥ this → REJECTED
CRITICAL_FLAG   = 0.45   # single source ≥ this → at least FLAGGED

# ── X-Ray source colour mapping (CSS class suffix) ──
# Each source maps to a distinct visual style applied via CSS.
_XRAY_SOURCE_CSS = {
    "profanity":  "xray-profanity",   # red
    "fraud":      "xray-fraud",       # orange
    "sentiment":  "xray-sentiment",   # purple
}

# ── X-Ray category labels (human-readable, for tooltips) ──
_CATEGORY_LABELS = {
    "en_profanity":       "Profanity (EN)",
    "ua_profanity":       "Profanity (UA)",
    "ua_toxic":           "Toxic language (UA)",
    "financial_scam":     "Financial scam",
    "crypto_scam":        "Crypto scam",
    "phishing":           "Phishing",
    "suspicious_url":     "Suspicious URL",
    "urgency":            "Urgency / pressure",
    "pii_request":        "PII request",
    "lottery_scam":       "Lottery / prize scam",
    "advance_fee":        "Advance-fee fraud",
    "impersonation":      "Impersonation",
    "negative_sentiment": "Negative sentiment",
}


def _build_xray_html(text: str, all_spans: list[dict]) -> str:
    """
    Produce an HTML string where every triggered word/phrase is wrapped
    in a ``<mark>`` tag with a source-specific CSS class and a tooltip.

    Overlapping spans are resolved by source priority:
    profanity > fraud > sentiment.

    Always returns the full HTML-escaped text so that the X-Ray section
    is visible for every input type (typed text, audio transcription, etc.).
    """
    if not text:
        return ""

    if not all_spans:
        return html_module.escape(text)

    # Deduplicate by (start, end)
    seen: set[tuple[int, int]] = set()
    unique: list[dict] = []
    for span in all_spans:
        key = (span["start"], span["end"])
        if key not in seen:
            seen.add(key)
            unique.append(span)

    # Sort by start position; for ties, longer span first
    unique.sort(key=lambda s: (s["start"], -s["end"]))

    # Merge overlapping spans — keep higher-priority source
    _PRIORITY = {"profanity": 3, "fraud": 2, "sentiment": 1}
    merged: list[dict] = []
    for span in unique:
        if merged and span["start"] < merged[-1]["end"]:
            prev = merged[-1]
            if _PRIORITY.get(span["source"], 0) > _PRIORITY.get(prev["source"], 0):
                merged[-1] = span
            # else: keep existing (higher or equal priority)
        else:
            merged.append(dict(span))  # copy to avoid mutating originals

    # Build HTML
    parts: list[str] = []
    last_end = 0

    for span in merged:
        start = max(span["start"], last_end)
        # Append plain text before this span
        if start > last_end:
            parts.append(html_module.escape(text[last_end:start]))

        css_class = _XRAY_SOURCE_CSS.get(span["source"], "xray-other")
        category = span.get("category", span["source"])
        tooltip = html_module.escape(
            _CATEGORY_LABELS.get(category, category.replace("_", " ").title())
        )
        word = text[start:span["end"]]
        parts.append(
            f'<mark class="{css_class}" title="{tooltip}">'
            f'{html_module.escape(word)}</mark>'
        )
        last_end = span["end"]

    # Trailing text
    if last_end < len(text):
        parts.append(html_module.escape(text[last_end:]))

    return "".join(parts)


async def _run_text_checks(text: str) -> tuple[dict, dict, dict, dict, dict, bool, float]:
    """
    Execute the five text moderation checks concurrently and compute
    the weighted text score.

    Returns
    -------
    (toxicity_result, spam_result, profanity_result, fraud_result,
     sentiment_result, is_partial, text_final_score)
    """
    toxicity_result, spam_result, profanity_result, fraud_result, sentiment_result = (
        await asyncio.gather(
            check_hf_toxicity(text),
            check_hf_spam(text),
            check_profanity(text),
            check_fraud(text),
            check_sentiment(text),
        )
    )

    sources: dict[str, float] = {}
    is_partial = False

    if toxicity_result["score"] is not None:
        sources["toxicity"] = toxicity_result["score"]
    else:
        is_partial = True
        logger.warning("Toxicity result unavailable — partial scoring.")

    if spam_result["score"] is not None:
        sources["spam"] = spam_result["score"]
    else:
        is_partial = True
        logger.warning("Spam result unavailable — partial scoring.")

    sources["profanity"] = profanity_result["score"]

    if fraud_result["score"] is not None:
        sources["fraud"] = fraud_result["score"]
    else:
        is_partial = True
        logger.warning("Fraud result unavailable — partial scoring.")

    sources["sentiment"] = sentiment_result["score"]

    # Calculate weighted score based on available sources
    weighted_score = 0.0
    active_weight_sum = 0.0

    # First pass: sum weights of available sources
    for src in sources:
        if sources[src] is not None:
            active_weight_sum += WEIGHTS[src]
    
    # Second pass: compute weighted score
    if active_weight_sum > 0:
        for src, score in sources.items():
            if score is not None:
                weighted_score += (WEIGHTS[src] / active_weight_sum) * score
    else:
        # Fallback if no sources are available (should replace with error handling if critical)
        weighted_score = 0.0

    final_score = round(weighted_score, 4)

    return (
        toxicity_result, spam_result, profanity_result,
        fraud_result, sentiment_result, is_partial, final_score,
    )


async def aggregate_moderation(text: str) -> dict:
    """
    Run text moderation checks **concurrently** and produce a moderator verdict.

    Parameters
    ----------
    text : str
        Text content to moderate.

    Returns
    -------
    dict  (ready to be stored in the DB and rendered on the frontend)
    """
    
    if not text or not text.strip():
        # Should ideally not happen if validated upstream, but safe fallback
        return {
            "text": "",
            "input_type": "text",
            "toxicity": {"score": None, "details": None},
            "spam": {"score": None, "details": None},
            "profanity": {"score": 0.0, "details": None},
            "fraud": {"score": 0.0, "details": None},
            "sentiment": {"score": 0.0, "details": None},
            "final_score": 0.0,
            "status": "APPROVED",
            "is_partial": False,
        }

    (
        toxicity_result, spam_result, profanity_result,
        fraud_result, sentiment_result, is_partial, final_score,
    ) = await _run_text_checks(text)

    # ── Map score to decision status (weighted average) ──
    if final_score < THRESHOLD_APPROVED:
        status = "APPROVED"
    elif final_score < THRESHOLD_FLAGGED:
        status = "FLAGGED"
    else:
        status = "REJECTED"

    # ── Critical single-source overrides ──
    # Prevents obvious fraud / spam / toxicity from being diluted
    # into APPROVED when the other sources score low.
    _source_scores = {
        "toxicity": toxicity_result.get("score"),
        "spam":     spam_result.get("score"),
        "profanity": profanity_result.get("score"),
        "fraud":    fraud_result.get("score"),
        "sentiment": sentiment_result.get("score"),
    }
    for src_name, src_score in _source_scores.items():
        if src_score is None:
            continue
        if src_score >= CRITICAL_REJECT and status != "REJECTED":
            logger.info(
                "Override: %s score %.2f ≥ %.2f → REJECTED",
                src_name, src_score, CRITICAL_REJECT,
            )
            status = "REJECTED"
            break
        if src_score >= CRITICAL_FLAG and status == "APPROVED":
            logger.info(
                "Override: %s score %.2f ≥ %.2f → FLAGGED",
                src_name, src_score, CRITICAL_FLAG,
            )
            status = "FLAGGED"

    # ── X-Ray: collect all triggered word spans ──
    all_triggered: list[dict] = []
    all_triggered.extend(profanity_result.get("triggered_words", []))
    all_triggered.extend(fraud_result.get("triggered_words", []))
    all_triggered.extend(sentiment_result.get("triggered_words", []))

    xray_html = _build_xray_html(text, all_triggered)

    return {
        "text": text,
        "input_type": "text",
        "toxicity": toxicity_result,
        "spam": spam_result,
        "profanity": profanity_result,
        "fraud": fraud_result,
        "sentiment": sentiment_result,
        "final_score": final_score,
        "status": status,
        "is_partial": is_partial,
        "xray_html": xray_html,
        "xray_data": all_triggered,
    }
