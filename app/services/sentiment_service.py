"""
app/services/sentiment_service.py — VADER sentiment analysis + Ukrainian keyword layer.

Uses NLTK's VADER (Valence Aware Dictionary and sEntiment Reasoner)
lexicon to assess the emotional tone of text.  Extremely negative
sentiment can be an additional signal for toxic or harmful content.

VADER is optimised for English social-media text.  For Ukrainian text
a supplementary keyword-based analysis is performed to detect strongly
negative sentiment that VADER cannot handle.

The ``compound`` score ranges from −1.0 (most negative) to +1.0
(most positive).  We convert this to a 0–1 risk score where
highly negative sentiment → high score.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Lazy-load VADER to avoid slow import at module level
_analyzer = None


def _get_analyzer():
    """Lazy-initialise the VADER SentimentIntensityAnalyzer."""
    global _analyzer
    if _analyzer is None:
        import nltk
        # Download the VADER lexicon if not already present
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


# ── Ukrainian sentiment keyword lists ──
# Strongly negative words / phrases (threats, insults, despair, hatred)
_UA_NEGATIVE: list[tuple[re.Pattern, float]] = [
    # Hatred / hostility
    (re.compile(r'\b(ненавидж[уіе]|ненависть|ненавис[тн])\b', re.I), -0.8),
    (re.compile(r'\b(огидн[иій]|бридк[иій]|мерзенн[иій]|відраз[аи])\b', re.I), -0.6),
    (re.compile(r'\b(жахлив[иійе]|страшн[иійе]|кошмарн[иійе]|жахітт[яі])\b', re.I), -0.6),
    # Insults
    (re.compile(r'\b(ідіот[иа]?|дурн[иійе]|тупи[йіцх]|кретин[иа]?|дебіл[иа]?)\b', re.I), -0.7),
    (re.compile(r'\b(нікчем[аний]|покидьк[иа]?|виродк[иа]?|нелюд[иа]?)\b', re.I), -0.7),
    # Wishes of harm / threats
    (re.compile(r'(сподіваюсь|надіюсь|бажаю|хочу).{0,30}(погано|зло|смерт|страждан)', re.I), -0.9),
    (re.compile(r'(щоб\s*(ти|ви|вони)\s*(здох|помер|стражда|зник))', re.I), -0.95),
    (re.compile(r'(трапи(ться|лось)\s*(щось\s*)?(жахлив|страшн|погано))', re.I), -0.8),
    (re.compile(r'(вб\'?ю|заб\'?ю|знищ[уі]|закопа|прибити|здохн|подихай)', re.I), -0.9),
    (re.compile(r'(світ\s*(був\s*би|буде|стане)\s*(кращ|ліпш).{0,20}без)', re.I), -0.85),
    # General negative
    (re.compile(r'\b(поган[иійое]|погано|жахлив|гірш[иійе]|найгірш)\b', re.I), -0.4),
    (re.compile(r'\b(злий|зла|зліст[ьі]|лют[иійе]|розлючен)\b', re.I), -0.5),
    (re.compile(r'\b(сумн[иійое]|смут[ок]|нещасн[иій]|горе|біда)\b', re.I), -0.4),
]

# Positive words (to balance)
_UA_POSITIVE: list[tuple[re.Pattern, float]] = [
    (re.compile(r'\b(чудов[иійое]|прекрасн[иійое]|відмінн[иійое]|неймовірн[иійое])\b', re.I), 0.7),
    (re.compile(r'\b(добрий|добре|хороший|гарний|гарне|гарна)\b', re.I), 0.5),
    (re.compile(r'\b(дякую|вдячн[иій]|подяк[аиу])\b', re.I), 0.6),
    (re.compile(r'\b(люблю|кохаю|обожнюю|радість|щастя|щасливий)\b', re.I), 0.7),
    (re.compile(r'\b(молодець|браво|супер|клас[сн])\b', re.I), 0.6),
    (re.compile(r'\b(сподобал[оа]сь|подобається|вражен[иій])\b', re.I), 0.5),
]


def _is_cyrillic_text(text: str) -> bool:
    """Return True if ≥ 30% of alpha chars are Cyrillic."""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return False
    cyrillic = sum(1 for c in alpha if '\u0400' <= c <= '\u04ff')
    return cyrillic / len(alpha) >= 0.3


def _ua_sentiment_score(text: str) -> float:
    """
    Compute a compound-like score (−1 … +1) for Ukrainian text
    using keyword matching.
    """
    total = 0.0
    count = 0
    for pat, weight in _UA_NEGATIVE:
        matches = pat.findall(text)
        if matches:
            total += weight * len(matches)
            count += len(matches)
    for pat, weight in _UA_POSITIVE:
        matches = pat.findall(text)
        if matches:
            total += weight * len(matches)
            count += len(matches)

    if count == 0:
        return 0.0
    # Average, clamped to [-1, 1]
    return max(-1.0, min(1.0, total / count))


async def check_sentiment(text: str) -> dict:
    """
    Analyse the sentiment of *text* using VADER (English) and a
    keyword-based Ukrainian layer.

    Returns
    -------
    dict
        {
            "score": float,         # risk score 0.0–1.0 (negative → high)
            "compound": float,      # effective compound score (−1 to +1)
            "details": dict,        # full breakdown
            "error": None
        }
    """
    try:
        analyzer = _get_analyzer()
        scores = analyzer.polarity_scores(text)
        vader_compound = scores["compound"]

        # Determine if text is predominantly Cyrillic (Ukrainian)
        cyrillic = _is_cyrillic_text(text)

        if cyrillic:
            # Use Ukrainian keyword layer as primary signal
            ua_compound = _ua_sentiment_score(text)
            # If both have opinions, blend; otherwise prefer the one with signal
            if ua_compound != 0.0:
                compound = ua_compound  # Ukrainian keywords take precedence
            else:
                compound = vader_compound
        else:
            compound = vader_compound
            ua_compound = 0.0

        # Convert compound (−1…+1) to risk score (0…1)
        # −1.0 → 1.0 risk, 0.0 → 0.5 risk, +1.0 → 0.0 risk
        risk_score = (1.0 - compound) / 2.0

        # Only flag as risky if genuinely negative (compound < -0.3)
        # Neutral or positive content should carry minimal risk
        if compound >= -0.1:
            risk_score = risk_score * 0.3  # Dampen neutral/positive

        return {
            "score": round(min(risk_score, 1.0), 4),
            "compound": round(compound, 4),
            "details": {
                "negative": scores["neg"],
                "neutral": scores["neu"],
                "positive": scores["pos"],
                "compound": scores["compound"],
                "ua_compound": round(ua_compound, 4) if cyrillic else None,
                "cyrillic_detected": cyrillic,
            },
            "error": None,
        }

    except Exception as exc:
        logger.error("Sentiment analysis failed: %s", exc)
        return {
            "score": 0.0,
            "compound": 0.0,
            "details": {"error": str(exc)},
            "error": str(exc),
        }
