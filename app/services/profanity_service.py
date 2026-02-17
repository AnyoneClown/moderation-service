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

# ── Ukrainian toxic / hateful language (insults, threats, hate speech) ──
# These are NOT vulgar words but still indicate harmful content.
# Each tuple: (compiled regex, weight 0.0–1.0)
_UA_TOXIC_PATTERNS: list[tuple[re.Pattern, float]] = [
    # Insults / dehumanisation
    (re.compile(r'\b(ідіот[иа]?|ідіотськ)\b', re.I), 0.45),
    (re.compile(r'\b(дур(ень|ні|не[ць]|н[яі]|ак))\b', re.I), 0.40),
    (re.compile(r'\b(кретин[иа]?|імбецил[иа]?|дебіл[иа]?)\b', re.I), 0.45),
    (re.compile(r'\b(тупи[йіцх]|тупак)\b', re.I), 0.35),
    (re.compile(r'\b(нікчем[аний]|покидьк[иа]?|відстал[иій])\b', re.I), 0.40),
    (re.compile(r'\b(бидл[оа]|швал[ьі]|мраз[ьіи]|наволоч)\b', re.I), 0.50),
    (re.compile(r'\b(виродк[иа]?|нелюд[иа]?|потвор[аи]?)\b', re.I), 0.50),
    (re.compile(r'\b(огид[аний]|мерзот[аний]|паскуд[аний])\b', re.I), 0.45),
    (re.compile(r'\b(нікчемн|жалюгідн|убог[иій])\b', re.I), 0.35),
    (re.compile(r'\b(недоумк[иа]?|недоум[ок])\b', re.I), 0.40),

    # Threats / wishes of harm
    (re.compile(r'(сподіваюсь|надіюсь|бажаю|хочу).{0,30}(жахлив|страшн|погано|зло|смерт|помер|здох)', re.I), 0.70),
    (re.compile(r'(щоб\s*(ти|ви|вони)\s*(здох|помер|стражда|мучи|зник))', re.I), 0.80),
    (re.compile(r'(трапи(ться|лось)\s*(щось\s*)?(жахлив|страшн|погано|лих[оіе]))', re.I), 0.65),
    (re.compile(r'(вб\'?ю|заб\'?ю|зарі[жз]|знищ[уі]|закопа[юєтиі]|прибити)', re.I), 0.80),
    (re.compile(r'(світ\s*(був\s*би|буде|стане)\s*(кращ|ліпш).{0,20}без)', re.I), 0.75),
    (re.compile(r'(не\s*заслуговуєш|не\s*заслуговують|не\s*варт[иі])\s*(жити|існуват|жит)', re.I), 0.80),
    (re.compile(r'(здохн|подихай|подохн|зникни|пішов?\s*геть)', re.I), 0.60),

    # General hate / hostility
    (re.compile(r'\b(ненавидж[уі]|ненависть|ненавис[тн])\b', re.I), 0.55),
    (re.compile(r'\b(огидн[иій]|бридк[иій]|відраз[аи]|гидот[аі])\b', re.I), 0.40),
    (re.compile(r'(такі[хм]?\s*(як\s*)?(ти|ви)\s*(не\s*повинн|не\s*має|не\s*потрібн))', re.I), 0.55),
    (re.compile(r'(горіти?\s*(в\s*пеклі|у\s*пеклі)|геть\s*(звідси|з\s*країни))', re.I), 0.60),
]


def _check_ua_toxic(text: str) -> tuple[float, int]:
    """
    Scan text for Ukrainian toxic/hateful patterns.
    Returns (max_weight_matched, total_match_count).
    """
    total = 0
    max_w = 0.0
    for pat, weight in _UA_TOXIC_PATTERNS:
        matches = pat.findall(text)
        if matches:
            total += len(matches)
            max_w = max(max_w, weight)
    return max_w, total


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

        # ── Ukrainian toxic / hateful language ──
        ua_toxic_weight, ua_toxic_count = _check_ua_toxic(text)

        # Censor Ukrainian profanity matches in the censored output
        if contains_profanity_ua:
            censored = _UA_PATTERN.sub(
                lambda m: " " + "*" * len(m.group(1)),
                censored,
            )

        contains_profanity = contains_profanity_en or contains_profanity_ua
        has_toxic_ua = ua_toxic_count > 0

        if contains_profanity or has_toxic_ua:
            if contains_profanity_en:
                severity = _calculate_severity(text, censored)
            elif contains_profanity_ua:
                # Ukrainian profanity: estimate severity from match count vs word count
                word_count = len(re.findall(r'\b\w+\b', text.lower()))
                severity = min(ua_match_count / max(word_count, 1), 1.0)
            else:
                severity = 0.0

            # Blend in the Ukrainian toxic keyword weight
            # The toxic weight (0.0-0.8) directly reflects how severe the match is
            score = max(severity, ua_toxic_weight, 0.5 if contains_profanity else 0.0)
        else:
            score = 0.0

        return {
            "score": round(score, 4),
            "flagged": contains_profanity or has_toxic_ua,
            "censored_text": censored,
            "details": {
                "contains_profanity": contains_profanity,
                "en_profanity": contains_profanity_en,
                "ua_profanity": contains_profanity_ua,
                "ua_match_count": ua_match_count,
                "ua_toxic_detected": has_toxic_ua,
                "ua_toxic_matches": ua_toxic_count,
                "ua_toxic_max_weight": round(ua_toxic_weight, 4),
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
