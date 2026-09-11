"""
WeatherGPT — Translation Service

Supports two backends behind one interface:
  1. Primary: Bhashini/ULCA (Indian government NLP platform)
  2. Fallback: deep-translator (wraps Google Translate, free, no key)

The backend auto-selects based on whether Bhashini credentials are configured.
No other code in the app needs to know which backend is active.
"""

from typing import Optional
import httpx

from app.core.config import settings


# =============================================================================
# Bhashini/ULCA backend
# =============================================================================

async def _translate_bhashini(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """
    Translate using Bhashini/ULCA pipeline.
    Returns None if credentials are missing or the call fails.
    """
    if not all([settings.bhashini_user_id, settings.bhashini_ulca_api_key, settings.bhashini_inference_key]):
        return None

    try:
        # Step 1: Discover translation pipeline
        pipeline_url = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
        pipeline_payload = {
            "pipelineTasks": [{"taskType": "translation", "config": {"language": {"sourceLanguage": source_lang, "targetLanguage": target_lang}}}],
            "pipelineRequestConfig": {"pipelineId": "64392f96daac500b55c543cd"},
        }
        headers = {
            "ulcaApiKey": settings.bhashini_ulca_api_key,
            "userID": settings.bhashini_user_id,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(pipeline_url, json=pipeline_payload, headers=headers)
            resp.raise_for_status()
            pipeline_data = resp.json()

        # Extract callback URL and service ID
        callback_url = pipeline_data["pipelineResponseConfig"][0]["config"][0]["serviceId"]
        inference_url = pipeline_data["pipelineInferenceAPIEndPoint"]["callbackUrl"]
        inference_key = pipeline_data["pipelineInferenceAPIEndPoint"]["inferenceApiKey"]["value"]

        # Step 2: Call the translation compute endpoint
        compute_payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {"sourceLanguage": source_lang, "targetLanguage": target_lang},
                        "serviceId": callback_url,
                    },
                }
            ],
            "inputData": {"input": [{"source": text}]},
        }
        compute_headers = {
            "Authorization": inference_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(inference_url, json=compute_payload, headers=compute_headers)
            resp.raise_for_status()
            result = resp.json()

        return result["pipelineResponse"][0]["output"][0]["target"]

    except Exception as e:
        print(f"⚠️  Bhashini translation failed: {e}")
        return None


# =============================================================================
# deep-translator fallback
# =============================================================================

# Language code mapping for deep-translator (uses Google Translate codes)
_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "bn": "bn",
    "ta": "ta",
    "te": "te",
    "mr": "mr",
    "gu": "gu",
    "kn": "kn",
    "ml": "ml",
    "pa": "pa",
    "ur": "ur",
    "or": "or",
    "as": "as",
}


def _translate_deep_translator(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Translate using deep-translator (Google Translate wrapper)."""
    try:
        from deep_translator import GoogleTranslator
        src = _LANG_MAP.get(source_lang, "en")
        tgt = _LANG_MAP.get(target_lang, "hi")
        translated = GoogleTranslator(source=src, target=tgt).translate(text)
        return translated
    except Exception as e:
        print(f"⚠️  deep-translator failed: {e}")
        return None


# =============================================================================
# Public interface
# =============================================================================

async def translate(text: str, target_lang: str, source_lang: str = "en") -> str:
    """
    Translate text to the target language.

    Tries Bhashini first (if credentials are configured), then falls back
    to deep-translator. Returns original text if both fail.

    Args:
        text: Text to translate
        target_lang: Target language ISO 639-1 code (e.g. 'hi', 'bn')
        source_lang: Source language code (default 'en')

    Returns:
        Translated text, or original text if translation fails
    """
    # No translation needed if target is same as source
    if target_lang == source_lang:
        return text

    # Try Bhashini first
    result = await _translate_bhashini(text, source_lang, target_lang)
    if result:
        print(f"   🌐 Translated via Bhashini ({source_lang} → {target_lang})")
        return result

    # Fallback to deep-translator
    result = _translate_deep_translator(text, source_lang, target_lang)
    if result:
        print(f"   🌐 Translated via deep-translator ({source_lang} → {target_lang})")
        return result

    # Both failed — return original
    print(f"   ⚠️  Translation failed, returning original text")
    return text
