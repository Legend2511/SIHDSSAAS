"""
WeatherGPT — LLM Service (Groq)

Uses Groq's hosted API (OpenAI-compatible) with llama-3.3-70b-versatile.
Falls back to llama-3.1-8b-instant if the primary model is unavailable.

The system prompt is the single most critical piece of this entire backend:
it controls role-appropriate phrasing, grounding in data, and the instruction
to never overstate or understate alert severity.
"""

from groq import Groq

from app.core.config import settings
from app.schemas.weather import WeatherSnapshot


def _get_client() -> Groq:
    """Get a Groq client instance."""
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com"
        )
    return Groq(api_key=settings.groq_api_key)


# =============================================================================
# SYSTEM PROMPT — the core of the demo
# =============================================================================

SYSTEM_PROMPT_TEMPLATE = """You are WeatherGPT, an AI weather assistant for India built for disaster management and climate awareness. You provide weather information, alerts, and actionable advice.

## CURRENT WEATHER DATA (ground truth — do NOT contradict this):
{weather_data}

## RELEVANT KNOWLEDGE BASE CONTEXT:
{rag_context}

## YOUR ROLE-SPECIFIC INSTRUCTIONS:
You are speaking to a **{role}**. Adjust your language and focus accordingly:

- **farmer**: Focus on crop impact, soil conditions, irrigation timing, sowing/harvest advice, and livestock safety. Use practical agricultural language. Mention specific crops and farming actions.
- **fisherman**: Focus on sea state, wind speed and direction, wave height, visibility conditions, and fishing safety. Be direct about whether it's safe to go to sea. Include return-to-harbor advisories.
- **disaster_team**: Focus on operational details — affected areas, expected timeline, resource positioning, evacuation routes, shelter capacity. Use emergency management terminology. Be precise about severity scales and expected impacts.
- **citizen**: Focus on personal safety, what to do and what to avoid, when to stay indoors vs evacuate. Use simple, clear language. Avoid jargon. Include practical tips (store water, charge phones, etc.).

## CRITICAL RULES (violation of these is unacceptable):
1. **NEVER state a severity level not backed by the weather data above.** If the data shows alert_level "None", do NOT say "red alert", "severe", "extremely dangerous", or similar. If it shows "Yellow", do NOT say "red" or "orange". Match the data EXACTLY.
2. **ALWAYS ground your response in the provided data.** Cite specific numbers (temperature, rainfall, wind speed) from the weather data.
3. **Be action-oriented.** Tell people what to DO, not just what the weather is.
4. **Be concise.** Maximum 3-4 short paragraphs. No filler.
5. **If asked about a topic you have no data for, say so clearly** rather than making something up.
6. **Use the appropriate severity language:**
    - Alert Level "Red" → you may say "Red Alert" and describe immediate action
   - Alert Level "Orange" → "Orange Alert" — significant weather expected
   - Alert Level "Yellow" → "Yellow Alert" — stay alert and updated
   - Alert Level "None" → normal conditions, no warnings

## RESPONSE LANGUAGE:
Respond in **{language_name}**. If you cannot produce fluent output in this language, respond in English.
"""

# Map language codes to names for the prompt
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
}


def _build_system_prompt(
    weather_data: WeatherSnapshot,
    rag_context: list[dict],
    role: str,
    language: str,
) -> str:
    """Build the complete system prompt with all context injected."""
    # Format RAG context
    if rag_context:
        rag_text = "\n\n".join(
            f"[Source: {ctx['source']}/{ctx.get('section', 'general')}]\n{ctx['text']}"
            for ctx in rag_context
        )
    else:
        rag_text = "(No specific knowledge base context available for this query)"

    language_name = LANGUAGE_NAMES.get(language, "English")

    return SYSTEM_PROMPT_TEMPLATE.format(
        weather_data=weather_data.summary_for_llm(),
        rag_context=rag_text,
        role=role,
        language_name=language_name,
    )


async def generate_response(
    message: str,
    role: str,
    weather_data: WeatherSnapshot,
    rag_context: list[dict],
    language: str = "en",
) -> str:
    """
    Generate an LLM response using Groq.

    Args:
        message: User's question
        role: User's role (farmer/fisherman/disaster_team/citizen)
        weather_data: Current weather snapshot for the location
        rag_context: Retrieved knowledge base chunks
        language: Target language code

    Returns:
        LLM response text
    """
    client = _get_client()
    system_prompt = _build_system_prompt(weather_data, rag_context, role, language)

    # Try primary model, fall back to smaller one
    model = settings.groq_model
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.3,  # Low temperature for factual accuracy
            max_tokens=800,
            top_p=0.9,
        )
        return response.choices[0].message.content
    except Exception as e:
        if model != settings.groq_fallback_model:
            print(f"⚠️  Primary model {model} failed ({e}), falling back to {settings.groq_fallback_model}")
            try:
                response = client.chat.completions.create(
                    model=settings.groq_fallback_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                    top_p=0.9,
                )
                return response.choices[0].message.content
            except Exception as e2:
                raise RuntimeError(f"Both LLM models failed: {e} / {e2}")
        raise


async def correct_response(
    original_reply: str,
    actual_alert_level: str,
    weather_data: WeatherSnapshot,
    rag_context: list[dict],
    role: str,
    language: str = "en",
) -> str:
    """
    Re-prompt the LLM with a correction instruction when guardrail detects a mismatch.
    """
    client = _get_client()
    system_prompt = _build_system_prompt(weather_data, rag_context, role, language)

    correction_prompt = f"""Your previous response contained an alert severity that does not match the actual data.

The ACTUAL alert level from verified weather data is: **{actual_alert_level}**

Your previous response was:
---
{original_reply}
---

Please rewrite your response to ACCURATELY reflect the {actual_alert_level} alert level. Do not overstate or understate the severity. Keep the same helpful tone and role-appropriate language, but fix the severity language to match the data exactly."""

    model = settings.groq_model
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": correction_prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return response.choices[0].message.content
    except Exception:
        # If correction fails, fall back to original with a warning prepended
        return f"[Alert Level: {actual_alert_level}] {original_reply}"
