"""
app/services/profanity_service.py — NVIDIA NIM profanity moderation.

Uses NVIDIA's OpenAI-compatible NIM API to detect English/Ukrainian
profanity and toxic language while preserving the response shape expected
by the aggregator and UI.
"""

import json
import logging
import re

from openai import APIError, APIStatusError

from app.services.nvidia_nim_service import is_nim_configured, nim_chat_completion

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {"en_profanity", "ua_profanity", "ua_toxic"}

_SYSTEM_PROMPT = (
    "You are a strict multilingual profanity and toxic-language moderation "
    "classifier for English, Ukrainian, and mixed-language text.\n\n"
    "Return ONLY one JSON object with this schema:\n"
    "{\n"
    '  "score": number,\n'
    '  "flagged": boolean,\n'
    '  "censored_text": string,\n'
    '  "matches": [\n'
    '    {"text": "exact substring from input", "category": "en_profanity|ua_profanity|ua_toxic"}\n'
    "  ],\n"
    '  "reason": "short neutral explanation"\n'
    "}\n\n"
    "Scoring rules:\n"
    "- 0.0 means no profanity or toxic language.\n"
    "- 0.3-0.5 means mild insult, vulgarity, or isolated profanity.\n"
    "- 0.6-0.8 means repeated profanity, direct abuse, threats, or hate.\n"
    "- 0.9-1.0 means extreme abuse, explicit threats, or severe hateful content.\n\n"
    "Rules:\n"
    "1. Only include exact substrings that appear in the input.\n"
    "2. Keep matches short: one word or the shortest harmful phrase.\n"
    "3. Replace only matched characters in censored_text with asterisks; preserve all other text.\n"
    "4. If the text is clean, return score 0.0, flagged false, censored_text equal to the input, and matches [].\n"
    "5. Do not add markdown fences or commentary outside the JSON object."
)


def _extract_json_object(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


def _clamp_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(score, 1.0)), 4)


def _find_all_positions(text: str, substring: str) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    needle = substring.strip()
    if not needle:
        return positions

    lower_text = text.lower()
    lower_needle = needle.lower()
    start = 0
    while True:
        idx = lower_text.find(lower_needle, start)
        if idx == -1:
            break
        positions.append((idx, idx + len(needle)))
        start = idx + 1
    return positions


def _normalize_matches(data: dict, text: str) -> list[dict]:
    spans: list[dict] = []
    for item in data.get("matches", []):
        if not isinstance(item, dict):
            continue

        match_text = str(item.get("text", "")).strip()
        category = str(item.get("category", "")).strip()
        if not match_text or category not in _VALID_CATEGORIES:
            continue

        for start, end in _find_all_positions(text, match_text):
            spans.append({
                "text": text[start:end],
                "start": start,
                "end": end,
                "source": "profanity",
                "category": category,
            })

    return spans


def _censor_from_spans(text: str, spans: list[dict]) -> str:
    if not spans:
        return text

    chars = list(text)
    for span in spans:
        for idx in range(span["start"], span["end"]):
            if not chars[idx].isspace():
                chars[idx] = "*"
    return "".join(chars)


async def check_profanity(text: str) -> dict:
    """
    Check *text* for profanity and toxic language via NVIDIA NIM.

    Returns the same schema as the previous local profanity service.
    """
    if not is_nim_configured():
        logger.warning("NVIDIA API key not configured — skipping profanity check.")
        return {
            "score": None,
            "flagged": False,
            "censored_text": text,
            "details": None,
            "triggered_words": [],
            "error": "API token not configured",
        }

    try:
        raw_content = await nim_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=1024,
            temperature=0.0,
        )
        data = _extract_json_object(raw_content)
        triggered = _normalize_matches(data, text)

        score = _clamp_score(data.get("score"))
        flagged = bool(data.get("flagged")) or bool(triggered) or score >= 0.3
        censored = str(data.get("censored_text") or "")
        if not censored or len(censored) != len(text):
            censored = _censor_from_spans(text, triggered)

        categories = {span["category"] for span in triggered}
        details = {
            "contains_profanity": flagged,
            "en_profanity": "en_profanity" in categories,
            "ua_profanity": "ua_profanity" in categories,
            "ua_match_count": sum(1 for span in triggered if span["category"] == "ua_profanity"),
            "ua_toxic_detected": "ua_toxic" in categories,
            "ua_toxic_matches": sum(1 for span in triggered if span["category"] == "ua_toxic"),
            "ua_toxic_max_weight": score if "ua_toxic" in categories else 0.0,
            "severity": score,
            "original_length": len(text),
            "model_reason": str(data.get("reason", ""))[:500],
            "provider": "nvidia_nim",
        }

        return {
            "score": score,
            "flagged": flagged,
            "censored_text": censored,
            "details": details,
            "triggered_words": triggered,
            "error": None,
        }

    except json.JSONDecodeError as exc:
        logger.error("NVIDIA NIM profanity JSON parse failed: %s", exc)
        return {
            "score": None,
            "flagged": False,
            "censored_text": text,
            "details": {"error": "Invalid model JSON"},
            "triggered_words": [],
            "error": "Invalid model JSON",
        }

    except APIStatusError as exc:
        logger.error("NVIDIA NIM profanity HTTP error: %s", str(exc)[:300])
        return {
            "score": None,
            "flagged": False,
            "censored_text": text,
            "details": None,
            "triggered_words": [],
            "error": f"HTTP {exc.status_code}",
        }

    except APIError as exc:
        logger.error("NVIDIA NIM profanity API error: %s", exc)
        return {
            "score": None,
            "flagged": False,
            "censored_text": text,
            "details": None,
            "triggered_words": [],
            "error": str(exc),
        }

    except Exception as exc:
        logger.error("NVIDIA NIM profanity check failed: %s", exc)
        return {
            "score": None,
            "flagged": False,
            "censored_text": text,
            "details": {"error": str(exc)},
            "triggered_words": [],
            "error": str(exc),
        }
