"""
app/services/profanity_service.py — Enhanced local profanity filter.

Uses the ``better-profanity`` library for instant, offline detection
of swear words and prohibited language.  This service is always
available regardless of external API status — it acts as the
reliability backbone of the system.

Enhancements over the basic binary check:
  - Severity scoring (0.0 – 1.0) based on the ratio of censored words
  - Censored text output for display
"""

import re
from better_profanity import profanity
import logging

logger = logging.getLogger(__name__)

# ── Load the default word list on module import ──
profanity.load_censor_words()


def _calculate_severity(original: str, censored: str) -> float:
    """
    Calculate a severity score between 0.0 and 1.0 based on
    how many words in the text were flagged as profane.

    A single swear word in a long sentence scores lower than
    a message consisting entirely of profanity.
    """
    original_words = re.findall(r'\b\w+\b', original.lower())

    if not original_words:
        return 0.0

    # Count asterisk groups in the censored version (each = one replaced word)
    asterisk_groups = re.findall(r'\*{2,}', censored)
    flagged_count = len(asterisk_groups)

    # Severity = ratio of profane words, capped at 1.0
    ratio = flagged_count / len(original_words)
    return min(round(ratio, 4), 1.0)


async def check_profanity(text: str) -> dict:
    """
    Check *text* for profanity using the local word list.

    Returns
    -------
    dict
        {
            "score": float,         # 0.0 – 1.0 severity score
            "flagged": bool,        # True if any profanity was detected
            "censored_text": str,   # text with swear words replaced by ****
            "details": dict,        # breakdown of the analysis
            "error": None           # local — never fails with an API error
        }
    """
    try:
        contains_profanity = profanity.contains_profanity(text)
        censored = profanity.censor(text)

        if contains_profanity:
            severity = _calculate_severity(text, censored)
            # Ensure minimum score of 0.5 when profanity is detected
            score = max(severity, 0.5)
        else:
            score = 0.0

        return {
            "score": round(score, 4),
            "flagged": contains_profanity,
            "censored_text": censored,
            "details": {
                "contains_profanity": contains_profanity,
                "severity": round(score, 4),
                "original_length": len(text),
            },
            "error": None,
        }

    except Exception as exc:
        # Extremely unlikely for a local library, but guard anyway
        logger.error("Profanity check failed: %s", exc)
        return {
            "score": 0.0,
            "flagged": False,
            "censored_text": text,
            "details": {"error": str(exc)},
            "error": str(exc),
        }
