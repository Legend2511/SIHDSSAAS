"""
WeatherGPT Backend — FastAPI Application Entry Point

Mounts all routers, configures CORS, and sets up application lifespan.
"""

import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything reads settings
load_dotenv()

from app.core.config import settings  # noqa: E402

# Uvicorn may inherit a legacy Windows console encoding. Keep startup and
# diagnostic messages from crashing application startup when they contain
# non-ASCII characters.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown logic."""
    # --- Startup ---
    print(f"🌦️  {settings.app_name} starting up...")

    # Initialize database (Phase 6)
    try:
        from app.services.database import init_db
        await init_db()
        print("   ✅ Database initialized")
    except ImportError:
        pass  # Database module not yet created

    # Initialize RAG (Phase 2)
    try:
        from app.services.rag import init_vector_db
        init_vector_db()
        print("   ✅ Vector DB initialized")
    except ImportError:
        pass  # RAG module not yet created

    yield

    # --- Shutdown ---
    print(f"🌦️  {settings.app_name} shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="Conversational AI for weather forecasting, alerts, and climate information — SIH 2026 MVP",
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount Routers ---
from app.routers.health import router as health_router  # noqa: E402

app.include_router(health_router)

# Conditionally mount routers as they are built
try:
    from app.routers.chat import router as chat_router
    app.include_router(chat_router, prefix="/api")
except ImportError:
    pass

try:
    from app.routers.alerts import router as alerts_router
    app.include_router(alerts_router, prefix="/api")
except ImportError:
    pass

try:
    from app.routers.whatsapp import router as whatsapp_router
    app.include_router(whatsapp_router)
except ImportError:
    pass

try:
    from app.routers.auth import router as auth_router
    app.include_router(auth_router, prefix="/api")
except ImportError:
    pass
