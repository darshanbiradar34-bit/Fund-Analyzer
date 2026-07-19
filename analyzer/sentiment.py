"""
sentiment.py
-------------
Simple keyword-based sentiment scoring for news headlines. This is NOT
a trained NLP model or a paid sentiment API - it's a transparent
positive/negative word-count heuristic. Deliberately simple and
inspectable rather than a black-box "AI sentiment" claim: every label
can be traced back to which words matched.

Good enough to color-code headlines as a rough at-a-glance signal;
not good enough to weight into the actual scoring engine (it isn't
used there) - treat it as informational, not a scoring input.
"""

POSITIVE_WORDS = {
    "beat", "beats", "surge", "surges", "rally", "rallies", "jump", "jumps",
    "growth", "profit", "profits", "gain", "gains", "upgrade", "upgraded",
    "outperform", "record", "strong", "robust", "expansion", "wins", "win",
    "positive", "bullish", "boost", "boosts", "rebound", "recovery",
    "improve", "improves", "improved", "high", "higher", "up", "rise", "rises",
    "buyback", "dividend", "raised", "raises", "expands", "success",
}

NEGATIVE_WORDS = {
    "miss", "misses", "plunge", "plunges", "fall", "falls", "decline", "declines",
    "loss", "losses", "downgrade", "downgraded", "underperform", "weak",
    "slump", "slumps", "cut", "cuts", "negative", "bearish", "drop", "drops",
    "concern", "concerns", "probe", "investigation", "lawsuit", "fraud",
    "resign", "resigns", "scandal", "layoff", "layoffs", "recall", "warns",
    "warning", "risk", "risks", "low", "lower", "down", "delay", "delayed",
    "penalty", "fine", "default",
}


def score_headline(text: str) -> dict:
    if not text:
        return {"label": "Neutral", "score": 0}

    words = set(w.strip(".,!?():;\"'").lower() for w in text.split())
    pos_hits = words & POSITIVE_WORDS
    neg_hits = words & NEGATIVE_WORDS

    score = len(pos_hits) - len(neg_hits)
    if score > 0:
        label = "Positive"
    elif score < 0:
        label = "Negative"
    else:
        label = "Neutral"

    return {"label": label, "score": score, "matched_positive": sorted(pos_hits), "matched_negative": sorted(neg_hits)}
