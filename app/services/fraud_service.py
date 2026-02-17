"""
app/services/fraud_service.py — Local fraud & phishing detection.

A pattern-based detector that identifies common fraud/scam/phishing
indicators in text.  Runs entirely locally with zero API dependencies.

Detection categories:
  1. Financial scams   — "wire transfer", "guaranteed profit", crypto scams
  2. Phishing          — fake URLs, credential harvesting, "verify your account"
  3. Urgency/pressure  — "act now", "limited time", "expires today"
  4. Personal info     — requests for SSN, credit card, bank account numbers
  5. Lottery/prize     — "you have won", "claim your prize"
  6. Advance fee       — "processing fee", "send money to receive"

Each matched pattern contributes to a cumulative score.  The final
score is normalised to the 0.0–1.0 range.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Pattern definitions ──────────────────────────────────────
# Each tuple: (compiled regex, weight, category label)
# Weights reflect severity; higher = more suspicious.

_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    # ── Financial scams ──
    (re.compile(r'\b(wire\s*transfer|money\s*transfer|western\s*union|moneygram)\b', re.I), 0.30, "financial_scam"),
    (re.compile(r'\b(guaranteed\s*(profit|return|income)|double\s*your\s*money)\b', re.I), 0.35, "financial_scam"),
    (re.compile(r'\b(bitcoin|crypto|btc|ethereum|eth)\s*(invest|send|deposit|transfer)\b', re.I), 0.25, "crypto_scam"),
    (re.compile(r'\b(invest(ment)?\s*opportunity|passive\s*income|financial\s*freedom)\b', re.I), 0.20, "financial_scam"),
    (re.compile(r'\b(make\s*money\s*(fast|quick|easy|online)|get\s*rich\s*quick)\b', re.I), 0.25, "financial_scam"),
    (re.compile(r'\b(no\s*risk|risk[\s-]*free|100\s*%\s*(guaranteed|safe|secure))\b', re.I), 0.20, "financial_scam"),

    # ── Phishing / credential harvesting ──
    (re.compile(r'\b(verify\s*your\s*(account|identity|email|password|information))\b', re.I), 0.30, "phishing"),
    (re.compile(r'\b(click\s*(here|below|this\s*link)|follow\s*this\s*link)\b', re.I), 0.15, "phishing"),
    (re.compile(r'\b(update\s*your\s*(payment|billing|account)\s*(info|information|details))\b', re.I), 0.30, "phishing"),
    (re.compile(r'\b(log\s*in\s*(immediately|now|urgent)|confirm\s*your\s*(identity|account))\b', re.I), 0.25, "phishing"),
    (re.compile(r'\b(suspended|deactivat(e|ed)|unauthorized\s*access|unusual\s*activity)\b', re.I), 0.20, "phishing"),
    (re.compile(r'https?://[a-z0-9\-]+\.(tk|ml|ga|cf|gq|xyz|top|buzz|club)\b', re.I), 0.25, "suspicious_url"),

    # ── Urgency / pressure tactics ──
    (re.compile(r'\b(act\s*now|limited\s*time|expires?\s*(today|soon|immediately))\b', re.I), 0.15, "urgency"),
    (re.compile(r'\b(urgent|immediately|right\s*away|don\'?t\s*(wait|delay|miss))\b', re.I), 0.10, "urgency"),
    (re.compile(r'\b(last\s*chance|final\s*(warning|notice)|only\s*\d+\s*(left|remaining))\b', re.I), 0.15, "urgency"),
    (re.compile(r'\b(within\s*\d+\s*(hour|minute|day)s?|before\s*it\'?s\s*too\s*late)\b', re.I), 0.10, "urgency"),

    # ── Personal information requests ──
    (re.compile(r'\b(social\s*security\s*(number)?|ssn)\b', re.I), 0.35, "pii_request"),
    (re.compile(r'\b(credit\s*card\s*(number|info|details)|card\s*number|cvv|cvc)\b', re.I), 0.35, "pii_request"),
    (re.compile(r'\b(bank\s*account\s*(number|details|info)|routing\s*number|iban|swift)\b', re.I), 0.30, "pii_request"),
    (re.compile(r'\b(passport\s*(number|details)|driver\'?s?\s*licen[sc]e\s*(number)?)\b', re.I), 0.25, "pii_request"),
    (re.compile(r'\b(send\s*(me|us)\s*your\s*(password|pin|credentials))\b', re.I), 0.35, "pii_request"),

    # ── Lottery / prize scams ──
    (re.compile(r'\b(you\s*(have\s*)?(won|been\s*selected)|congratulations?\s*!?\s*(you|winner))\b', re.I), 0.30, "lottery_scam"),
    (re.compile(r'\b(claim\s*(your|the)\s*(prize|reward|winnings|gift))\b', re.I), 0.30, "lottery_scam"),
    (re.compile(r'\b(lottery|sweepstakes|raffle|jackpot|grand\s*prize)\b', re.I), 0.20, "lottery_scam"),
    (re.compile(r'\b(free\s*(gift|iphone|macbook|laptop|money|vacation))\b', re.I), 0.20, "lottery_scam"),

    # ── Advance-fee / Nigerian-prince style ──
    (re.compile(r'\b(processing\s*fee|handling\s*(fee|charge)|small\s*fee)\b', re.I), 0.25, "advance_fee"),
    (re.compile(r'\b(send\s*(money|funds|payment)\s*(to\s*receive|first|upfront))\b', re.I), 0.35, "advance_fee"),
    (re.compile(r'\b(inheritance|beneficiary|next\s*of\s*kin|unclaimed\s*(funds|money))\b', re.I), 0.30, "advance_fee"),
    (re.compile(r'\b(nigerian?\s*prince|foreign\s*(dignitary|official|minister))\b', re.I), 0.35, "advance_fee"),
    (re.compile(r'\b(million\s*dollars?|millions?\s*of\s*(dollars|usd|euros?))\b', re.I), 0.20, "advance_fee"),

    # ── Impersonation / authority fraud ──
    (re.compile(r'\b(irs|fbi|interpol|police|government)\s*(agent|official|department)\b', re.I), 0.20, "impersonation"),
    (re.compile(r'\b(legal\s*action|arrest\s*warrant|court\s*order|lawsuit)\b', re.I), 0.15, "impersonation"),
]

# Maximum possible raw score (sum of all weights)
_MAX_RAW_SCORE = sum(weight for _, weight, _ in _PATTERNS)


async def check_fraud(text: str) -> dict:
    """
    Scan *text* for fraud/phishing/scam patterns.

    Returns
    -------
    dict
        {
            "score": float,          # normalised risk score (0.0–1.0)
            "flagged": bool,         # True if any pattern matched
            "matched_categories": list[str],  # unique categories triggered
            "matched_patterns": int, # number of individual patterns matched
            "details": dict,         # per-category breakdown
            "error": None
        }
    """
    try:
        raw_score = 0.0
        matched_categories: set[str] = set()
        category_hits: dict[str, list[str]] = {}
        pattern_count = 0

        for pattern, weight, category in _PATTERNS:
            matches = pattern.findall(text)
            if matches:
                raw_score += weight
                matched_categories.add(category)
                pattern_count += 1

                if category not in category_hits:
                    category_hits[category] = []
                # Store the first match as evidence
                match_text = matches[0] if isinstance(matches[0], str) else matches[0][0]
                category_hits[category].append(match_text.strip())

        # Normalise to 0–1, capping at 1.0
        normalised_score = min(raw_score / (_MAX_RAW_SCORE * 0.15), 1.0)
        # Apply a floor: if 3+ categories matched, bump score to at least 0.5
        if len(matched_categories) >= 3:
            normalised_score = max(normalised_score, 0.5)

        return {
            "score": round(normalised_score, 4),
            "flagged": pattern_count > 0,
            "matched_categories": sorted(matched_categories),
            "matched_patterns": pattern_count,
            "details": category_hits,
            "error": None,
        }

    except Exception as exc:
        logger.error("Fraud detection failed: %s", exc)
        return {
            "score": 0.0,
            "flagged": False,
            "matched_categories": [],
            "matched_patterns": 0,
            "details": {"error": str(exc)},
            "error": str(exc),
        }
