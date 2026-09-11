"""Twilio WhatsApp Sandbox webhook."""

import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from app.core.config import settings
from app.schemas.chat import ChatRequest
from app.routers.chat import chat

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    body: str = Form(default=""),
    from_number: str = Form(default="", alias="From"),
):
    """Answer an inbound Sandbox message using the same chat pipeline as the API."""
    if settings.twilio_auth_token:
        signature = request.headers.get("X-Twilio-Signature", "")
        form_data = dict(await request.form())
        validator = RequestValidator(settings.twilio_auth_token)
        if not signature or not validator.validate(str(request.url), form_data, signature):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    incoming = body.strip()
    twiml = MessagingResponse()
    if not incoming:
        twiml.message("Please send a weather question, for example: weather in Shimla")
        return Response(content=str(twiml), media_type="application/xml")

    # Keep the Sandbox demo frictionless: users can optionally start with
    # "location: question"; otherwise the known default is used.
    location = "New Delhi"
    message = incoming
    if ":" in incoming:
        possible_location, possible_message = incoming.split(":", 1)
        if possible_location.strip() and possible_message.strip():
            location = possible_location.strip()
            message = possible_message.strip()

    try:
        result = await chat(ChatRequest(message=message, location=location, role="citizen", language="en"))
        twiml.message(result.reply)
    except Exception:
        logger.exception("WhatsApp webhook processing failed")
        twiml.message("I could not retrieve weather information right now. Please try again shortly.")

    return Response(content=str(twiml), media_type="application/xml")