"""
app/services/profanity_service.py — Enhanced local profanity filter.

Uses the ``better-profanity`` library for instant, offline detection
of swear words and prohibited language.  This service is always
available regardless of external API status — it acts as the
reliability backbone of the system.

Enhancements over the basic binary check:
  - Severity scoring (0.0 – 1.0) based on the ratio of censored words
  - Censored text output for display
  - Ukrainian profanity detection via a custom word list
"""

import re
from better_profanity import profanity
import logging

logger = logging.getLogger(__name__)

# ── Load the default English word list on module import ──
profanity.load_censor_words()

# ── Ukrainian profanity word list ──
# Common Ukrainian swear / vulgar words and their morphological variants.
# This runs as a secondary regex-based check alongside better-profanity.
_UA_PROFANITY_WORDS: list[str] = [
    # Core vulgar roots and common inflections
    r"бля[тдь]",
    r"блять",
    r"сук[аиіо]",
    r"хуй",
    r"хує",
    r"хуя",
    r"хуї",
    r"хуйн[яюіі]",
    r"хуйов",
    r"піздець",
    r"пізд[аеуюоі]",
    r"піздат",
    r"їб[аеуіо]",
    r"єб[аеуіо]",
    r"ебат",
    r"йоб",
    r"їбан",
    r"єбан",
    r"заїб",
    r"заєб",
    r"наїб",
    r"наєб",
    r"виїб",
    r"відїб",
    r"розїб",
    r"підїб",
    r"доїб",
    r"перєб",
    r"переїб",
    r"оїб",
    r"залуп",
    r"муд[аоіи]",
    r"мудак",
    r"мудил",
    r"гандон",
    r"гнид[аиі]",
    r"довбо[йє]б",
    r"стерв[аоі]",
    r"падлюк",
    r"шлюх[аиі]",
    r"курв[аиі]",
    r"дрочи",
    r"дроч",
    r"дебіл",
    r"відстал",
    r"тупиц",
    r"ублюд",
    r"виблядок",
    r"виблядк",
    r"срак[аиі]",
    r"сран",
    r"задниц",
    r"жоп[аиіу]",
    r"засран",
]

_UA_PATTERN = re.compile(
    r"(?:^|\s|[^\wа-яіїєґ'])(" + "|".join(_UA_PROFANITY_WORDS) + r")",
    re.I | re.UNICODE,
)


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


def _check_ukrainian_profanity(text: str) -> tuple[bool, int]:
    """
    Check text for Ukrainian profanity using regex patterns.
    Returns (contains_profanity, match_count).
    """
    matches = _UA_PATTERN.findall(text)
    return bool(matches), len(matches)


async def check_profanity(text: str) -> dict:
    """
    Check *text* for profanity using the local English word list
    **and** a custom Ukrainian word list.

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
        # ── English detection (better-profanity) ──
        contains_profanity_en = profanity.contains_profanity(text)
        censored = profanity.censor(text)

        # ── Ukrainian detection (regex) ──
        contains_profanity_ua, ua_match_count = _check_ukrainian_profanity(text)

        # Censor Ukrainian matches in the censored output
        if contains_profanity_ua:
            censored = _UA_PATTERN.sub(
                lambda m: " " + "*" * len(m.group(1)),
                censored,
            )

        contains_profanity = contains_profanity_en or contains_profanity_ua

        if contains_profanity:
            if contains_profanity_en:
                severity = _calculate_severity(text, censored)
            else:
                # Ukrainian-only: estimate severity from match count vs word count
                word_count = len(re.findall(r'\b\w+\b', text.lower()))
                severity = min(ua_match_count / max(word_count, 1), 1.0)
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
                "en_profanity": contains_profanity_en,
                "ua_profanity": contains_profanity_ua,
                "ua_match_count": ua_match_count,
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
