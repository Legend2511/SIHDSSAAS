"""
WeatherGPT — Alert Severity Guardrail

Cross-checks LLM output against the deterministic alert_level from WeatherSnapshot.
This directly addresses the "hallucination in alerts" risk from the pitch deck.

The guardrail scans the LLM's reply for severity language and compares it against
the actual alert level. On mismatch, it triggers a correction re-prompt rather
than silently returning incorrect severity claims.
"""

import re
from app.schemas.weather import AlertLevel


# =============================================================================
# Severity keyword mapping
# =============================================================================

# Keywords that imply a specific alert level
_RED_KEYWORDS = [
    r"\bred\s*alert\b",
    r"\bextremely\s*severe\b",
    r"\bvery\s*dangerous\b",
    r"\bcatastrophic\b",
    r"\blife[\s-]*threatening\b",
    r"\bemergency\s*evacuat",
    r"\bextreme\s*danger\b",
    r"\bsuper\s*cyclone\b",
    r"\bextremely\s*heavy\s*rain",
]

_ORANGE_KEYWORDS = [
    r"\borange\s*alert\b",
    r"\bsevere\s*weather\b",
    r"\bsignificant\s*threat\b",
    r"\bvery\s*heavy\s*rain",
    r"\bdangerous\s*conditions\b",
    r"\bserious\s*disrupt",
    r"\bsevere\s*cyclone\b",
]

_YELLOW_KEYWORDS = [
    r"\byellow\s*alert\b",
    r"\bmoderate\s*caution\b",
    r"\bstay\s*alert\b",
    r"\badverse\s*weather\b",
    r"\bheavy\s*rain(?!fall\s*of\s*\d)",  # "heavy rain" but not "heavy rainfall of 5mm"
]

_GREEN_KEYWORDS = [
    r"\bno\s*(?:significant\s*)?alert\b",
    r"\bno\s*(?:significant\s*)?warning\b",
    r"\bnormal\s*conditions\b",
    r"\bpleasant\s*weather\b",
    r"\bclear\s*(?:sky|skies|weather)\b",
]


def _find_severity_claims(text: str) -> set[str]:
    """
    Scan text for severity keywords and return the set of implied alert levels.
    Returns a set like {"Red", "Orange"} based on what severity language was found.
    """
    text_lower = text.lower()
    found = set()

    for pattern in _RED_KEYWORDS:
        if re.search(pattern, text_lower):
            found.add("Red")
            break

    for pattern in _ORANGE_KEYWORDS:
        if re.search(pattern, text_lower):
            found.add("Orange")
            break

    for pattern in _YELLOW_KEYWORDS:
        if re.search(pattern, text_lower):
            found.add("Yellow")
            break

    for pattern in _GREEN_KEYWORDS:
        if re.search(pattern, text_lower):
            found.add("None")
            break

    return found


# Alert level hierarchy for comparison
_LEVEL_ORDER = {"None": 0, "Yellow": 1, "Orange": 2, "Red": 3}


def check_alert_consistency(
    llm_reply: str,
    actual_alert_level: AlertLevel,
) -> tuple[bool, list[str]]:
    """
    Check if the LLM's reply is consistent with the actual alert level.

    Returns:
        (is_consistent, list_of_mismatched_terms)

    A reply is inconsistent if it claims a severity different from the data.
    Both overstatements and understatements are flagged so the API contract stays exact.
    """
    actual_str = actual_alert_level.value  # "Red", "Orange", "Yellow", "None"
    claimed_levels = _find_severity_claims(llm_reply)

    if not claimed_levels:
        # LLM didn't use explicit severity language — acceptable
        return True, []

    mismatches = []
    actual_order = _LEVEL_ORDER.get(actual_str, 0)

    for claimed in claimed_levels:
        claimed_order = _LEVEL_ORDER.get(claimed, 0)
        if claimed_order != actual_order:
            direction = "OVERSTATED" if claimed_order > actual_order else "UNDERSTATED"
            mismatches.append(f"Claimed '{claimed}' but actual is '{actual_str}' ({direction})")

    is_consistent = len(mismatches) == 0
    return is_consistent, mismatches


async def apply_guardrail(
    llm_reply: str,
    weather_data,  # WeatherSnapshot
    rag_context: list[dict],
    role: str,
    language: str = "en",
) -> tuple[str, bool]:
    """
    Apply the guardrail to an LLM reply. If inconsistent, re-prompt for correction.

    Returns:
        (final_reply, was_corrected)
    """
    is_consistent, mismatches = check_alert_consistency(llm_reply, weather_data.alert_level)

    if is_consistent:
        return llm_reply, False

    # Log the mismatch
    print(f"🛡️  Guardrail triggered! Mismatches: {mismatches}")
    print(f"    Actual alert level: {weather_data.alert_level.value}")

    # Re-prompt for correction
    from app.services.llm import correct_response
    corrected = await correct_response(
        original_reply=llm_reply,
        actual_alert_level=weather_data.alert_level.value,
        weather_data=weather_data,
        rag_context=rag_context,
        role=role,
        language=language,
    )

    # Verify the correction (but don't loop forever — max one correction)
    is_now_consistent, _ = check_alert_consistency(corrected, weather_data.alert_level)
    if not is_now_consistent:
        print("🛡️  Correction still inconsistent — prepending factual alert level")
        alert_prefix = f"**Current Alert Level: {weather_data.alert_level.value}**\n\n"
        corrected = alert_prefix + corrected

    return corrected, True
