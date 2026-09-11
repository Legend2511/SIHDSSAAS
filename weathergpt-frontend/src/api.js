// ---------------------------------------------------------------------------
// WeatherGPT API client — talks to the FastAPI backend in SIH-backend-main.
// ---------------------------------------------------------------------------

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, token, headers } = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError(
      `Could not reach the WeatherGPT backend at ${BASE_URL}. Is it running (uvicorn app.main:app --reload)?`,
      0
    );
  }

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status);
  }

  return data;
}

// --- Health -----------------------------------------------------------------

export function getHealth() {
  return request("/health");
}

// --- Auth ---------------------------------------------------------------------

export function signup({ name, email, password, role = "citizen" }) {
  return request("/api/auth/signup", { method: "POST", body: { name, email, password, role } });
}

export function login({ email, password }) {
  return request("/api/auth/login", { method: "POST", body: { email, password } });
}

export function googleAuth({ name, email }) {
  return request("/api/auth/google", { method: "POST", body: { name, email } });
}

export function getMe(token) {
  return request("/api/auth/me", { token });
}

// --- Chat -----------------------------------------------------------------

export function sendChat({ message, role = "citizen", location, language = "en" }) {
  return request("/api/chat", { method: "POST", body: { message, role, location, language } });
}

// --- Alerts -----------------------------------------------------------------

export function getAlert(location) {
  return request(`/api/alerts?location=${encodeURIComponent(location)}`);
}

export function subscribe({ contact, channel = "whatsapp", location, role = "citizen" }) {
  return request("/api/subscribe", { method: "POST", body: { contact, channel, location, role } });
}

export { ApiError, BASE_URL };
