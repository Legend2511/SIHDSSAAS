# SIH Backend

WeatherGPT backend for the SIH project. This is a FastAPI application that
provides weather chat, alert, subscription, and WhatsApp webhook endpoints.

## Current demo behavior

The project works without provider credentials:

- Weather falls back to deterministic mock IMD data.
- RAG starts with an empty local vector store until the seed script is run.
- Chat requires `GROQ_API_KEY`; without it, `/api/chat` returns a clear `503`.
- OpenWeather, Bhashini, and Twilio integrations are optional.

Do not commit `.env`, API keys, database files, or the local virtual
environment.

## Setup

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`. Interactive
documentation is available at `/docs`.

## Optional configuration

Edit `.env` to add provider credentials. `ADMIN_API_KEY` protects the local
subscription inspection endpoint. Twilio webhook signatures are validated
automatically when `TWILIO_AUTH_TOKEN` is configured.

## Auth (Phase 7)

Added on top of the original API — accounts are stored in the same SQLite
database used for subscriptions/alerts.

- `POST /api/auth/signup` — `{name, email, password, role?}` → `{access_token, user}`
- `POST /api/auth/login` — `{email, password}` → `{access_token, user}`
- `POST /api/auth/google` — `{name, email}` → `{access_token, user}` (demo only —
  trusts the caller instead of verifying a real Google ID token; replace
  before any real deployment)
- `GET /api/auth/me` — requires `Authorization: Bearer <token>` → `{user}`

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib `hashlib`, no extra
compiled dependency). Sessions are stateless JWTs signed with `SECRET_KEY`
from `.env` — set a strong random value before deploying anywhere real:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`/api/chat`, `/api/alerts`, and `/api/subscribe` do not require a token —
signed-in state is purely for saving/syncing chats on the frontend.

## Security note

`.env.example` previously had real `OPENWEATHER_API_KEY` / `GROQ_API_KEY`
values committed. Those have been scrubbed from this copy — **rotate both
keys** if this repo (or its git history) was ever pushed anywhere public,
then put your live keys only in your local `.env` (already git-ignored).
