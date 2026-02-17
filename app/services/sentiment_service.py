"""
app/services/sentiment_service.py — VADER sentiment analysis.

Uses NLTK's VADER (Valence Aware Dictionary and sEntiment Reasoner)
lexicon to assess the emotional tone of text.  Extremely negative
sentiment can be an additional signal for toxic or harmful content.

VADER is optimised for social-media text and handles:
  - Slang, emoticons, and internet abbreviations
  - Capitalisation emphasis (e.g., "GREAT" vs "great")
  - Degree modifiers ("very", "extremely")

The ``compound`` score ranges from −1.0 (most negative) to +1.0
(most positive).  We convert this to a 0–1 risk score where
highly negative sentiment → high score.
"""

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


async def check_sentiment(text: str) -> dict:
    """
    Analyse the sentiment of *text* using VADER.

    Returns
    -------
    dict
        {
            "score": float,         # risk score 0.0–1.0 (negative → high)
            "compound": float,      # raw VADER compound score (−1 to +1)
            "details": dict,        # full VADER breakdown (neg, neu, pos, compound)
            "error": None
        }
    """
    try:
        analyzer = _get_analyzer()
        scores = analyzer.polarity_scores(text)

        # Convert compound (−1…+1) to risk score (0…1)
        # −1.0 → 1.0 risk, 0.0 → 0.5 risk, +1.0 → 0.0 risk
        compound = scores["compound"]
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
