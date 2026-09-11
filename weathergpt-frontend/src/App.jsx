import React, { useEffect, useRef, useState } from "react";
import {
  Plus,
  Send,
  Mic,
  MicOff,
  PhoneOff,
  Sparkles,
  LogOut,
  User,
  X,
  Loader2,
  ChevronUp,
  Trash2,
  CloudSun,
  AlertTriangle,
  MapPin,
  Settings2,
} from "lucide-react";
import * as api from "./api.js";
import { useVoice } from "./useVoice.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROLES = [
  { value: "citizen", label: "Citizen" },
  { value: "farmer", label: "Farmer" },
  { value: "fisherman", label: "Fisherman" },
  { value: "disaster_team", label: "Disaster response team" },
];

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "bn", label: "Bengali" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
  { value: "mr", label: "Marathi" },
  { value: "gu", label: "Gujarati" },
  { value: "kn", label: "Kannada" },
  { value: "ml", label: "Malayalam" },
  { value: "pa", label: "Punjabi" },
  { value: "ur", label: "Urdu" },
  { value: "or", label: "Odia" },
  { value: "as", label: "Assamese" },
];

const QUICK_PROMPTS = [
  "Weather now",
  "Weather tomorrow",
  "Will it rain?",
  "7-day forecast",
  "Wind speed today",
  "Is it going to snow?",
];

const ALERT_STYLES = {
  Red: "bg-red-500/15 border-red-500/40 text-red-300",
  Orange: "bg-orange-500/15 border-orange-500/40 text-orange-300",
  Yellow: "bg-yellow-500/15 border-yellow-500/40 text-yellow-300",
  None: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
};

const uid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

function chatsStorageKey(user) {
  return `weathergpt_chats_${user ? user.email : "guest"}`;
}

function loadChats(user) {
  try {
    const raw = localStorage.getItem(chatsStorageKey(user));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveChats(user, chats) {
  try {
    localStorage.setItem(chatsStorageKey(user), JSON.stringify(chats));
  } catch {
    // storage full or unavailable — non-fatal
  }
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------

export default function App() {
  // --- auth state (backed by the real /api/auth endpoints) ---
  const [token, setToken] = useState(() => localStorage.getItem("weathergpt_token") || null);
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const raw = localStorage.getItem("weathergpt_user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [authModal, setAuthModal] = useState(null); // 'signin' | 'signup' | null
  const [authForm, setAuthForm] = useState({ name: "", email: "", password: "" });
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  // --- settings: location / role / language (required by /api/chat) ---
  const [settings, setSettings] = useState(() => {
    try {
      const raw = localStorage.getItem("weathergpt_settings");
      return raw ? JSON.parse(raw) : { location: "New Delhi", role: "citizen", language: "en" };
    } catch {
      return { location: "New Delhi", role: "citizen", language: "en" };
    }
  });
  const [settingsOpen, setSettingsOpen] = useState(false);

  // --- alert banner ---
  const [alert, setAlert] = useState(null);
  const [alertLoading, setAlertLoading] = useState(false);

  // --- chat state ---
  const [chats, setChats] = useState(() => loadChats(currentUser));
  const [activeChatId, setActiveChatId] = useState(null);
  const [input, setInput] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState("");

  // --- voice call state ---
  const [callOpen, setCallOpen] = useState(false);
  const [callStatus, setCallStatus] = useState("listening"); // listening | thinking | speaking
  const [muted, setMuted] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const activeChat = chats.find((c) => c.id === activeChatId) || null;
  const messages = activeChat ? activeChat.messages : [];

  // persist chats per-user
  useEffect(() => {
    saveChats(currentUser, chats);
  }, [chats, currentUser]);

  // reload chats when the signed-in user changes
  useEffect(() => {
    setChats(loadChats(currentUser));
    setActiveChatId(null);
  }, [currentUser?.email]);

  // persist settings
  useEffect(() => {
    localStorage.setItem("weathergpt_settings", JSON.stringify(settings));
  }, [settings]);

  // fetch the alert banner whenever location changes
  useEffect(() => {
    let cancelled = false;
    if (!settings.location.trim()) return;
    setAlertLoading(true);
    api
      .getAlert(settings.location)
      .then((data) => {
        if (!cancelled) setAlert(data);
      })
      .catch(() => {
        if (!cancelled) setAlert(null);
      })
      .finally(() => {
        if (!cancelled) setAlertLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [settings.location]);

  // scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  // ---------------------------------------------------------------------
  // Chat actions — talk to the real POST /api/chat endpoint
  // ---------------------------------------------------------------------

  async function sendMessage(rawText, { viaVoice = false } = {}) {
    const text = rawText.trim();
    if (!text || sending) return;
    setChatError("");

    let chatId = activeChatId;
    const isNew = !chatId;
    if (isNew) chatId = uid();

    const userMsg = { id: uid(), role: "user", content: text };
    setChats((prev) => {
      if (isNew) {
        return [{ id: chatId, title: text.slice(0, 32), messages: [userMsg] }, ...prev];
      }
      return prev.map((c) =>
        c.id === chatId
          ? { ...c, title: c.messages.length === 0 ? text.slice(0, 32) : c.title, messages: [...c.messages, userMsg] }
          : c
      );
    });
    if (isNew) setActiveChatId(chatId);
    setInput("");
    setSending(true);
    if (viaVoice) setCallStatus("thinking");

    try {
      const res = await api.sendChat({
        message: text,
        role: settings.role,
        location: settings.location,
        language: settings.language,
      });

      const assistantMsg = {
        id: uid(),
        role: "assistant",
        content: res.reply,
        alertLevel: res.alert_level,
        sources: res.sources,
      };
      setChats((prev) =>
        prev.map((c) => (c.id === chatId ? { ...c, messages: [...c.messages, assistantMsg] } : c))
      );
      setAlert((prev) => (prev ? { ...prev, alert_level: res.alert_level } : prev));

      if (viaVoice) {
        setCallStatus("speaking");
        voice.speak(res.reply);
      }
    } catch (err) {
      const message = err.message || "Something went wrong talking to the WeatherGPT backend.";
      setChatError(message);
      setChats((prev) =>
        prev.map((c) =>
          c.id === chatId
            ? { ...c, messages: [...c.messages, { id: uid(), role: "assistant", content: message, isError: true }] }
            : c
        )
      );
      if (viaVoice) {
        setCallStatus("speaking");
        voice.speak("Sorry, I could not reach the weather backend.");
      }
    } finally {
      setSending(false);
      if (viaVoice) setTimeout(() => setCallStatus("listening"), 300);
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const createNewChat = () => {
    setActiveChatId(null);
    setInput("");
    setMobileSidebarOpen(false);
    inputRef.current?.focus();
  };

  const selectChat = (id) => {
    setActiveChatId(id);
    setMobileSidebarOpen(false);
  };

  const deleteChat = (id, e) => {
    e.stopPropagation();
    setChats((prev) => prev.filter((c) => c.id !== id));
    if (activeChatId === id) setActiveChatId(null);
  };

  // ---------------------------------------------------------------------
  // Voice — real speech-to-text driving the same /api/chat pipeline,
  // plus text-to-speech for the reply. (The backend has no WebRTC voice
  // endpoint, so this uses the browser's native speech APIs instead.)
  // ---------------------------------------------------------------------

  const voice = useVoice({
    language: settings.language === "hi" ? "hi-IN" : "en-IN",
    onFinalTranscript: (transcript) => {
      sendMessage(transcript, { viaVoice: true });
    },
  });

  const startCall = () => {
    if (!voice.supported) {
      setChatError("Voice input isn't supported in this browser. Try Chrome or Edge.");
      return;
    }
    setCallOpen(true);
    setMuted(false);
    setCallStatus("listening");
    voice.start();
  };

  const endCall = () => {
    voice.stop();
    voice.cancelSpeech();
    setCallOpen(false);
  };

  const toggleMute = () => {
    if (muted) {
      voice.start();
    } else {
      voice.stop();
    }
    setMuted((m) => !m);
  };

  // ---------------------------------------------------------------------
  // Auth actions — talk to the real /api/auth endpoints
  // ---------------------------------------------------------------------

  const openAuth = (mode) => {
    setAuthForm({ name: "", email: "", password: "" });
    setAuthError("");
    setAuthModal(mode);
    setAccountMenuOpen(false);
    setMobileSidebarOpen(false);
  };

  const closeAuth = () => {
    setAuthModal(null);
    setAuthError("");
    setAuthLoading(false);
  };

  function applySession(data) {
    setToken(data.access_token);
    setCurrentUser(data.user);
    localStorage.setItem("weathergpt_token", data.access_token);
    localStorage.setItem("weathergpt_user", JSON.stringify(data.user));
    setAuthModal(null);
  }

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");
    const { name, email, password } = authForm;

    if (authModal === "signup") {
      if (!name.trim()) return setAuthError("Enter your name.");
      if (!isValidEmail(email)) return setAuthError("Enter a valid email address.");
      if (password.length < 6) return setAuthError("Password must be at least 6 characters.");
    } else {
      if (!isValidEmail(email)) return setAuthError("Enter a valid email address.");
      if (!password) return setAuthError("Enter your password.");
    }

    setAuthLoading(true);
    try {
      const data =
        authModal === "signup"
          ? await api.signup({ name: name.trim(), email, password })
          : await api.login({ email, password });
      applySession(data);
    } catch (err) {
      setAuthError(err.message || "Something went wrong.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleGoogleAuth = async () => {
    // The backend's /api/auth/google is a demo endpoint (no real Google
    // token verification yet — see app/routers/auth.py). We collect the
    // name/email the same way a Google button would hand them back.
    const name = window.prompt("Demo Google sign-in — enter a name:", currentUser?.name || "");
    if (!name) return;
    const email = window.prompt("Enter an email:", "");
    if (!email || !isValidEmail(email)) {
      setAuthError("Enter a valid email address.");
      return;
    }
    setAuthError("");
    setAuthLoading(true);
    try {
      const data = await api.googleAuth({ name: name.trim(), email: email.trim() });
      applySession(data);
    } catch (err) {
      setAuthError(err.message || "Google sign-in failed.");
    } finally {
      setAuthLoading(false);
    }
  };

  const signOut = () => {
    setToken(null);
    setCurrentUser(null);
    localStorage.removeItem("weathergpt_token");
    localStorage.removeItem("weathergpt_user");
    setAccountMenuOpen(false);
  };

  // ---------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------

  return (
    <div className="h-screen w-full flex bg-[#0a0a0b] text-neutral-100 font-sans overflow-hidden relative">
      {mobileSidebarOpen && (
        <div className="fixed inset-0 bg-black/60 z-30 md:hidden" onClick={() => setMobileSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed md:static z-40 md:z-auto top-0 left-0 h-full w-[260px] shrink-0 bg-[#0d0d0e] border-r border-white/10 flex flex-col transition-transform duration-200 ${
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="p-3">
          <button
            onClick={createNewChat}
            className="w-full flex items-center gap-2 justify-center rounded-lg border border-white/15 hover:border-white/30 hover:bg-white/5 transition-colors py-2 text-sm font-medium"
          >
            <Plus size={16} />
            New chat
          </button>
        </div>

        <div className="px-4 pt-2 pb-1 text-[11px] tracking-wide text-neutral-500">CHATS</div>

        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {chats.length === 0 && <div className="px-2 py-2 text-sm text-neutral-600">No chats yet.</div>}
          {chats.map((c) => (
            <button
              key={c.id}
              onClick={() => selectChat(c.id)}
              className={`group w-full flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm text-left transition-colors ${
                c.id === activeChatId ? "bg-white/10 text-white" : "text-neutral-400 hover:bg-white/5 hover:text-neutral-200"
              }`}
            >
              <span className="truncate">{c.title || "New chat"}</span>
              <span
                onClick={(e) => deleteChat(c.id, e)}
                className="opacity-0 group-hover:opacity-100 text-neutral-500 hover:text-red-400 transition-opacity shrink-0"
              >
                <Trash2 size={13} />
              </span>
            </button>
          ))}
        </div>

        {/* Account panel */}
        <div className="relative p-3 border-t border-white/10">
          {accountMenuOpen && (
            <div className="absolute bottom-full left-3 right-3 mb-2 rounded-lg border border-white/10 bg-[#141415] shadow-xl overflow-hidden">
              {currentUser ? (
                <button onClick={signOut} className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-neutral-200 hover:bg-white/5">
                  <LogOut size={15} /> Sign out
                </button>
              ) : (
                <>
                  <button
                    onClick={() => openAuth("signin")}
                    className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-neutral-200 hover:bg-white/5 border-b border-white/5"
                  >
                    <User size={15} /> Sign in
                  </button>
                  <button onClick={() => openAuth("signup")} className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-emerald-400 hover:bg-white/5">
                    <Sparkles size={15} /> Create an account
                  </button>
                </>
              )}
            </div>
          )}

          <button onClick={() => setAccountMenuOpen((v) => !v)} className="w-full flex items-center gap-2.5 rounded-lg px-1.5 py-1.5 hover:bg-white/5 transition-colors">
            <div
              className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
                currentUser ? "bg-emerald-500 text-black" : "bg-neutral-700 text-neutral-300"
              }`}
            >
              {currentUser ? currentUser.name.trim()[0]?.toUpperCase() : <User size={14} />}
            </div>
            <div className="flex-1 text-left min-w-0">
              <div className="text-sm font-medium truncate">{currentUser ? currentUser.name : "Guest"}</div>
              <div className="flex items-center gap-1 text-[11px] text-emerald-500/80">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />
                Voice + chat enabled
              </div>
            </div>
            <ChevronUp size={14} className={`text-neutral-500 transition-transform ${accountMenuOpen ? "" : "rotate-180"}`} />
          </button>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Header */}
        <header className="shrink-0 border-b border-white/10 bg-[#0a0a0b]/80 backdrop-blur">
          <div className="h-14 flex items-center justify-between px-4">
            <div className="flex items-center gap-3 min-w-0">
              <button className="md:hidden text-neutral-400 hover:text-white" onClick={() => setMobileSidebarOpen(true)}>
                <ChevronUp size={18} className="rotate-90" />
              </button>
              <span className="h-2 w-2 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-sm font-medium truncate">WeatherGPT Assistant</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setSettingsOpen((v) => !v)}
                className="h-8 px-2.5 rounded-full flex items-center gap-1.5 text-xs text-neutral-300 hover:bg-white/5 border border-white/10"
                title="Location, role & language"
              >
                <MapPin size={13} />
                <span className="max-w-[110px] truncate">{settings.location || "Set location"}</span>
                <Settings2 size={12} className="text-neutral-500" />
              </button>
              <button
                onClick={() => (currentUser ? setAccountMenuOpen((v) => !v) : openAuth("signin"))}
                className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
                  currentUser ? "bg-emerald-500 text-black" : "bg-neutral-700 text-neutral-300"
                }`}
                title={currentUser ? currentUser.name : "Sign in"}
              >
                {currentUser ? currentUser.name.trim()[0]?.toUpperCase() : <User size={14} />}
              </button>
            </div>
          </div>

          {/* Settings panel */}
          {settingsOpen && (
            <div className="px-4 pb-3 flex flex-wrap gap-2 border-t border-white/5 pt-3">
              <input
                value={settings.location}
                onChange={(e) => setSettings((s) => ({ ...s, location: e.target.value }))}
                placeholder="Location, e.g. Shimla, Himachal Pradesh"
                className="flex-1 min-w-[180px] rounded-lg bg-neutral-900 border border-white/10 focus:border-emerald-500/50 outline-none px-3 py-1.5 text-sm placeholder:text-neutral-500"
              />
              <select
                value={settings.role}
                onChange={(e) => setSettings((s) => ({ ...s, role: e.target.value }))}
                className="rounded-lg bg-neutral-900 border border-white/10 focus:border-emerald-500/50 outline-none px-3 py-1.5 text-sm"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <select
                value={settings.language}
                onChange={(e) => setSettings((s) => ({ ...s, language: e.target.value }))}
                className="rounded-lg bg-neutral-900 border border-white/10 focus:border-emerald-500/50 outline-none px-3 py-1.5 text-sm"
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Alert banner */}
          {settings.location && (
            <div className={`px-4 py-2 text-xs border-t flex items-center gap-2 ${ALERT_STYLES[alert?.alert_level] || ALERT_STYLES.None}`}>
              <AlertTriangle size={13} className="shrink-0" />
              {alertLoading ? (
                <span>Checking alerts for {settings.location}…</span>
              ) : alert ? (
                <span className="truncate">
                  <strong>{alert.alert_level === "None" ? "No alert" : `${alert.alert_level} alert`}</strong> — {alert.headline} · {alert.location}
                </span>
              ) : (
                <span>Alert status unavailable for {settings.location}.</span>
              )}
            </div>
          )}
        </header>

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center px-6 text-center">
              <div className="h-12 w-12 rounded-xl bg-emerald-500 flex items-center justify-center mb-5 shadow-[0_0_40px_-8px_rgba(16,185,129,0.6)]">
                <Sparkles size={22} className="text-black" />
              </div>
              <h1 className="text-xl font-semibold mb-2">How can I help you today?</h1>
              <p className="text-sm text-neutral-500 mb-8 max-w-sm">
                Ask anything in text, tap the mic to talk, or pick a weather question below. Answers come from the
                live WeatherGPT API for <strong className="text-neutral-300">{settings.location || "your location"}</strong>.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md">
                {QUICK_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => sendMessage(p)}
                    className="rounded-lg border border-white/10 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-colors text-sm px-4 py-2.5 text-left text-neutral-300"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">
              {messages.map((m) => (
                <div key={m.id} className={`flex items-start gap-2.5 ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  {m.role === "assistant" && (
                    <div className="h-7 w-7 rounded-full bg-emerald-500 flex items-center justify-center shrink-0 mt-0.5">
                      <Sparkles size={13} className="text-black" />
                    </div>
                  )}
                  <div
                    className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed max-w-[80%] whitespace-pre-wrap ${
                      m.role === "user"
                        ? "bg-emerald-600 text-white rounded-br-sm"
                        : m.isError
                        ? "bg-red-500/10 border border-red-500/30 text-red-300 rounded-bl-sm"
                        : "bg-neutral-800/80 text-neutral-100 rounded-bl-sm border border-white/5"
                    }`}
                  >
                    {m.content}
                    {m.role === "assistant" && !m.isError && m.alertLevel && (
                      <div className="mt-2 pt-2 border-t border-white/10 text-[11px] text-neutral-500">
                        Alert level: {m.alertLevel === "None" ? "None" : m.alertLevel}
                        {m.sources?.length ? ` · Sources: ${m.sources.join(", ")}` : ""}
                      </div>
                    )}
                  </div>
                  {m.role === "user" && (
                    <div
                      className={`h-7 w-7 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0 mt-0.5 ${
                        currentUser ? "bg-emerald-500 text-black" : "bg-neutral-700 text-neutral-300"
                      }`}
                    >
                      {currentUser ? currentUser.name.trim()[0]?.toUpperCase() : "U"}
                    </div>
                  )}
                </div>
              ))}
              {sending && (
                <div className="flex items-center gap-2.5">
                  <div className="h-7 w-7 rounded-full bg-emerald-500 flex items-center justify-center shrink-0">
                    <Sparkles size={13} className="text-black" />
                  </div>
                  <div className="rounded-2xl rounded-bl-sm px-4 py-2.5 bg-neutral-800/80 border border-white/5 flex items-center gap-1.5">
                    <Loader2 size={13} className="animate-spin text-neutral-400" />
                    <span className="text-xs text-neutral-500">Thinking…</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <form onSubmit={handleSubmit} className="shrink-0 px-4 pb-3 pt-2">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center gap-2 bg-neutral-900 border border-white/10 focus-within:border-emerald-500/50 rounded-full px-2 py-1.5 transition-colors">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Message the assistant"
                className="flex-1 bg-transparent outline-none text-sm px-3 py-1.5 placeholder:text-neutral-500"
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                className="h-8 w-8 rounded-full bg-neutral-700 disabled:opacity-40 hover:bg-emerald-500 hover:text-black flex items-center justify-center transition-colors shrink-0"
              >
                <Send size={14} />
              </button>
              <button
                type="button"
                onClick={startCall}
                className="h-8 w-8 rounded-full bg-neutral-700 hover:bg-emerald-500 hover:text-black flex items-center justify-center transition-colors shrink-0"
                title={voice.supported ? "Start voice chat" : "Voice not supported in this browser"}
              >
                <Mic size={14} />
              </button>
            </div>
            {chatError && <p className="text-center text-[11px] text-red-400 mt-2">{chatError}</p>}
            <p className="text-center text-[11px] text-neutral-600 mt-2">
              Text uses live POST /api/chat · Voice uses browser speech-to-text
            </p>
          </div>
        </form>

        {/* Voice call overlay */}
        {callOpen && (
          <div className="absolute inset-0 bg-[#0a0a0b]/97 backdrop-blur-sm flex flex-col items-center justify-center z-20">
            <div className="relative h-24 w-24 rounded-full bg-emerald-500/10 flex items-center justify-center mb-6">
              {callStatus === "listening" && <span className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" />}
              <div className="h-16 w-16 rounded-full bg-emerald-500 flex items-center justify-center relative">
                {callStatus === "thinking" ? <Loader2 size={24} className="text-black animate-spin" /> : <Sparkles size={24} className="text-black" />}
              </div>
            </div>

            <h2 className="text-lg font-semibold mb-1">WeatherGPT voice chat</h2>
            <p className="text-sm text-neutral-500 mb-2 max-w-xs text-center">
              {callStatus === "listening" && (muted ? "Microphone muted" : "Listening — speak your question")}
              {callStatus === "thinking" && "Asking the WeatherGPT API…"}
              {callStatus === "speaking" && "Speaking the answer…"}
            </p>
            {voice.interimTranscript && <p className="text-xs text-neutral-600 italic mb-6 max-w-xs text-center">"{voice.interimTranscript}"</p>}

            {callStatus === "listening" && !voice.interimTranscript && (
              <div className="flex items-end gap-1 h-8 mb-10">
                {[6, 14, 22, 12, 18, 8, 16].map((h, idx) => (
                  <span key={idx} className="w-1 bg-emerald-500 rounded-full animate-pulse" style={{ height: `${h}px`, animationDelay: `${idx * 90}ms` }} />
                ))}
              </div>
            )}

            <div className="flex items-center gap-4 mt-6">
              <button
                onClick={toggleMute}
                className={`h-12 w-12 rounded-full flex items-center justify-center transition-colors ${
                  muted ? "bg-white text-black" : "bg-neutral-800 text-white hover:bg-neutral-700"
                }`}
              >
                {muted ? <MicOff size={18} /> : <Mic size={18} />}
              </button>
              <button onClick={endCall} className="h-12 w-12 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors">
                <PhoneOff size={18} />
              </button>
            </div>
          </div>
        )}

        {/* Auth modal */}
        {authModal && (
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-30 p-4">
            <div className="relative w-full max-w-sm bg-[#141415] border border-white/10 rounded-2xl p-6 shadow-2xl">
              <button onClick={closeAuth} className="absolute top-4 right-4 text-neutral-500 hover:text-white">
                <X size={16} />
              </button>

              <div className="flex flex-col items-center text-center mb-5">
                <div className="h-10 w-10 rounded-xl bg-emerald-500 flex items-center justify-center mb-3">
                  <CloudSun size={20} className="text-black" />
                </div>
                <h2 className="text-lg font-semibold">{authModal === "signup" ? "Create your account" : "Welcome back"}</h2>
                <p className="text-sm text-neutral-500 mt-1">
                  {authModal === "signup" ? "Create an account to save your conversations." : "Sign in to sync your chats with WeatherGPT."}
                </p>
              </div>

              <button
                onClick={handleGoogleAuth}
                disabled={authLoading}
                className="w-full flex items-center justify-center gap-2 rounded-lg border border-white/15 hover:bg-white/5 transition-colors py-2.5 text-sm font-medium mb-4 disabled:opacity-50"
              >
                <GoogleIcon />
                Continue with Google
              </button>

              <div className="flex items-center gap-3 mb-4">
                <div className="h-px flex-1 bg-white/10" />
                <span className="text-[11px] text-neutral-500">OR</span>
                <div className="h-px flex-1 bg-white/10" />
              </div>

              <form onSubmit={handleAuthSubmit} className="space-y-3">
                {authModal === "signup" && (
                  <input
                    type="text"
                    placeholder="Full name"
                    value={authForm.name}
                    onChange={(e) => setAuthForm((f) => ({ ...f, name: e.target.value }))}
                    className="w-full rounded-lg bg-neutral-900 border border-white/10 focus:border-emerald-500/50 outline-none px-3.5 py-2.5 text-sm placeholder:text-neutral-500"
                  />
                )}
                <input
                  type="email"
                  placeholder="Email address"
                  value={authForm.email}
                  onChange={(e) => setAuthForm((f) => ({ ...f, email: e.target.value }))}
                  className="w-full rounded-lg bg-neutral-900 border border-white/10 focus:border-emerald-500/50 outline-none px-3.5 py-2.5 text-sm placeholder:text-neutral-500"
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={authForm.password}
                  onChange={(e) => setAuthForm((f) => ({ ...f, password: e.target.value }))}
                  className="w-full rounded-lg bg-neutral-900 border border-white/10 focus:border-emerald-500/50 outline-none px-3.5 py-2.5 text-sm placeholder:text-neutral-500"
                />

                {authError && <p className="text-xs text-red-400 leading-relaxed">{authError}</p>}

                <button
                  type="submit"
                  disabled={authLoading}
                  className="w-full rounded-lg bg-white text-black font-medium py-2.5 text-sm hover:bg-neutral-200 transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
                >
                  {authLoading && <Loader2 size={14} className="animate-spin" />}
                  {authModal === "signup" ? "Create account" : "Sign in"}
                </button>
              </form>

              <p className="text-center text-xs text-neutral-500 mt-4">
                {authModal === "signup" ? (
                  <>
                    Already have an account?{" "}
                    <button onClick={() => openAuth("signin")} className="text-emerald-400 hover:underline">
                      Sign in instead
                    </button>
                  </>
                ) : (
                  <>
                    New here?{" "}
                    <button onClick={() => openAuth("signup")} className="text-emerald-400 hover:underline">
                      Create an account
                    </button>
                  </>
                )}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.9 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.1 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.9 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.1 29.6 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.5 0 10.4-1.9 14.3-5.1l-6.6-5.4C29.6 35.4 26.9 36.3 24 36.3c-5.3 0-9.7-3.1-11.3-7.5l-6.6 5.1C9.6 39.7 16.3 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.9 2.5-2.5 4.5-4.6 5.9l6.6 5.4C40.8 36.1 44 30.6 44 24c0-1.3-.1-2.7-.4-3.5z" />
    </svg>
  );
}
