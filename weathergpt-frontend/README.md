# WeatherGPT Frontend

A React + Vite + Tailwind frontend for the SIH `WeatherGPT` FastAPI backend.
It talks to your real API — nothing here is mocked.

## What's wired up

- **Auth** — sign up / sign in / "Continue with Google" (demo) call the
  backend's `/api/auth/*` endpoints. A JWT is stored in `localStorage` and
  sent as `Authorization: Bearer <token>` on `/api/auth/me`.
- **Chat** — every message calls the real `POST /api/chat` with your
  `message`, `role`, `location`, and `language`, and renders the model's
  `reply`, `alert_level`, and `sources`.
- **Alert banner** — `GET /api/alerts?location=...` is polled whenever you
  change location, and renders as a colored banner (Red/Orange/Yellow/None).
- **Voice** — the backend has no WebRTC/voice endpoint, so the mic button
  uses the browser's built-in speech recognition to transcribe what you say,
  sends it through the same `/api/chat` call, and reads the reply back with
  speech synthesis. Works best in Chrome/Edge.
- **Chats & settings** — saved to `localStorage` per signed-in user (or as a
  guest), so refreshing the page keeps your history.

## Setup

```bash
npm install
cp .env.example .env
npm run dev
```

By default the app expects the backend at `http://127.0.0.1:8000` — edit
`VITE_API_BASE_URL` in `.env` if yours runs elsewhere.

Start the backend first (see its own README), then run this. Open the URL
Vite prints (usually `http://localhost:5173`).

## Notes / things to know

- **Google sign-in is a demo.** The backend's `/api/auth/google` trusts
  whatever name/email the frontend sends — there's no real Google token
  verification yet. Good enough for a hackathon demo; swap it for verified
  Google ID-token validation before shipping this for real.
- **CORS**: the backend already allows `http://localhost:5173` and
  `http://localhost:3000` by default (see its `app/main.py`). If you deploy
  the frontend elsewhere, add that origin to `FRONTEND_ORIGIN` in the
  backend's `.env`.
- **Chat requires `GROQ_API_KEY`** on the backend — without it, `/api/chat`
  returns a `503` and the UI will show that error inline in the chat.
