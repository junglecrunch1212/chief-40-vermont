"""Project signal detection: identifies when a user message implies a multi-step project."""

import re

# ─── Signal Patterns ───

SIGNAL_PATTERNS = {
    "involves_external_parties": re.compile(
        r"\b(?:hire|find|contractor|teacher|tutor|plumber|electrician|vendor|provider|"
        r"professional|architect|designer|coach|therapist|sitter|walker|cleaner|"
        r"landscaper|painter|handyman|inspector|appraiser|realtor|attorney|doctor)\b",
        re.IGNORECASE,
    ),
    "involves_research": re.compile(
        r"\b(?:research|compare|comparison|options|quotes?|reviews?|best|recommend|"
        r"find out|look into|investigate|explore|evaluate|assess|shop around|"
        r"what are the|who is the best|which one)\b",
        re.IGNORECASE,
    ),
    "involves_money": re.compile(
        r"\b(?:budget|cost|price|pay|spend|afford|deposit|fee|invoice|"
        r"estimate|quote|bid|financing|loan|insurance|premium|subscription)\b",
        re.IGNORECASE,
    ),
    "involves_timeline": re.compile(
        r"\b(?:deadline|by\s+(?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december|next\s+week|next\s+month|summer|fall|"
        r"spring|winter)|before\s+\w+|schedule|book|reserve|enroll|register|sign\s+up|"
        r"apply|application|due\s+date|starts?\s+(?:in|on)|opens?\s+(?:in|on))\b",
        re.IGNORECASE,
    ),
    "involves_physical_world": re.compile(
        r"\b(?:repair|build|install|renovate|renovation|construction|paint|fix|plumb|"
        r"roof|fence|deck|patio|garage|driveway|flooring|tile|cabinet|"
        r"ADU|addition|remodel|demolish|permit|zoning|inspection)\b",
        re.IGNORECASE,
    ),
    "multi_step_language": re.compile(
        r"(?:first.*then|step\s+by\s+step|plan\s+for|project|phases?|"
        r"help\s+me\s+figure\s+out|need\s+to\s+(?:find|get|arrange|organize|set\s+up)|"
        r"how\s+(?:do\s+(?:I|we)|should\s+(?:I|we))\s+(?:find|get|start|arrange|"
        r"organize|set\s+up|go\s+about))",
        re.IGNORECASE,
    ),
}

# ─── Template Keywords ───

_TEMPLATE_KEYWORDS = {
    "construction_project": re.compile(
        r"\b(?:build|construct|renovate|remodel|ADU|addition|deck|patio|"
        r"fence|roof|garage|permit|zoning|architect|contractor)\b",
        re.IGNORECASE,
    ),
    "book_travel": re.compile(
        r"\b(?:travel|trip|vacation|flight|hotel|resort|airbnb|cruise|"
        r"destination|itinerary|getaway|weekend\s+away)\b",
        re.IGNORECASE,
    ),
    "enrollment_deadline": re.compile(
        r"\b(?:enroll|register|sign\s+up|camp|school|class|lessons?|"
        r"program|application|admission|tryout|audition)\b",
        re.IGNORECASE,
    ),
    "emergency_repair": re.compile(
        r"\b(?:emergency|urgent|broken|leak|flood|no\s+(?:heat|AC|hot\s+water|power)|"
        r"pipe\s+burst|won't\s+start|stuck|dangerous)\b",
        re.IGNORECASE,
    ),
}


def detect_project(message: str) -> dict | None:
    """Detect whether a message implies a multi-step project.

    Returns {confidence, signals, suggested_template} if 2+ signals detected,
    else None.
    """
    if not message or len(message) < 10:
        return None

    signals = []
    for signal_name, pattern in SIGNAL_PATTERNS.items():
        if pattern.search(message):
            signals.append(signal_name)

    if len(signals) < 2:
        return None

    confidence = min(1.0, len(signals) * 0.2 + 0.1)
    template = _match_template(signals, message)

    return {
        "confidence": confidence,
        "signals": signals,
        "suggested_template": template,
    }


def _match_template(signals: list[str], message: str) -> str | None:
    """Map detected signals + message content to a template name."""
    # Check specific template keywords first (most specific wins)
    if _TEMPLATE_KEYWORDS["emergency_repair"].search(message):
        return "emergency_repair"
    if _TEMPLATE_KEYWORDS["construction_project"].search(message):
        return "construction_project"
    if _TEMPLATE_KEYWORDS["book_travel"].search(message):
        return "book_travel"
    if _TEMPLATE_KEYWORDS["enrollment_deadline"].search(message):
        return "enrollment_deadline"

    # Fall back to signal-based matching
    if "involves_external_parties" in signals and "involves_research" in signals:
        return "find_service_provider"

    # Default
    return "administrative_cleanup"
