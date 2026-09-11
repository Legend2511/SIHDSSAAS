"""
WeatherGPT — Chat Router

POST /api/chat — the core demo endpoint.

Pipeline:
  1. Fetch WeatherSnapshot for the location
  2. Retrieve RAG context
  3. Call Groq LLM with role-aware system prompt
  4. Run guardrail (cross-check severity claims)
  5. Translate if needed
  6. Return ChatResponse
"""

from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ingestion import get_weather_for_location
from app.services.rag import retrieve
from app.services.llm import generate_response
from app.services.guardrail import apply_guardrail
from app.services.translate import translate

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Conversational weather endpoint.
    Accepts a natural-language question with role, location, and language,
    and returns a grounded, role-appropriate response.
    """
    try:
        # Step 1: Get weather data for the location
        weather_data = await get_weather_for_location(request.location)
        print(f"📊 Weather for {weather_data.location}: {weather_data.alert_level.value} alert, {weather_data.temp_c}°C")

        # Step 2: Retrieve relevant knowledge base context
        rag_context = retrieve(request.message, k=3)
        rag_sources = [ctx["source"] for ctx in rag_context]
        print(f"📚 RAG sources: {rag_sources}")

        # Step 3: Generate LLM response
        # For non-English, we still generate in English first then translate,
        # because the LLM is more reliable in English and the guardrail
        # needs to scan English text for severity keywords
        llm_reply = await generate_response(
            message=request.message,
            role=request.role,
            weather_data=weather_data,
            rag_context=rag_context,
            language="en",  # Always generate in English for guardrail
        )
        print(f"🤖 LLM response generated ({len(llm_reply)} chars)")

        # Step 4: Run guardrail
        final_reply, was_corrected = await apply_guardrail(
            llm_reply=llm_reply,
            weather_data=weather_data,
            rag_context=rag_context,
            role=request.role,
            language="en",
        )
        if was_corrected:
            print("🛡️  Guardrail applied correction")

        # Step 5: Translate if needed
        if request.language != "en":
            final_reply = await translate(final_reply, target_lang=request.language)

        # Step 6: Build response
        sources = [weather_data.source] + rag_sources
        return ChatResponse(
            reply=final_reply,
            alert_level=weather_data.alert_level.value,
            language=request.language,
            sources=sources,
            data_as_of=weather_data.timestamp.isoformat(),
        )

    except RuntimeError as e:
        # LLM key issues
        logger.warning("Chat provider unavailable: %s", e)
        raise HTTPException(status_code=503, detail="The weather assistant is temporarily unavailable.")
    except Exception as e:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail="Unable to process the weather request.")
