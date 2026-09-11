import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Browser-native voice support: SpeechRecognition (speech-to-text) +
// speechSynthesis (text-to-speech). No backend voice endpoint exists in the
// SIH backend, so this drives the *real* /api/chat text pipeline from voice
// input instead of faking a WebRTC call.
// ---------------------------------------------------------------------------

const SpeechRecognitionImpl =
  typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

export function useVoice({ onFinalTranscript, language = "en-US" }) {
  const [supported] = useState(!!SpeechRecognitionImpl);
  const [listening, setListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (!SpeechRecognitionImpl) return;
    const recognition = new SpeechRecognitionImpl();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = language;

    recognition.onresult = (event) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += transcript;
        else interim += transcript;
      }
      setInterimTranscript(interim);
      if (final.trim()) onFinalTranscript(final.trim());
    };

    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);

    recognitionRef.current = recognition;
    return () => recognition.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  const start = useCallback(() => {
    if (!recognitionRef.current) return;
    setInterimTranscript("");
    try {
      recognitionRef.current.start();
      setListening(true);
    } catch {
      // already started — ignore
    }
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  const speak = useCallback((text) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    window.speechSynthesis.speak(utterance);
  }, []);

  const cancelSpeech = useCallback(() => {
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
  }, []);

  return { supported, listening, interimTranscript, start, stop, speak, cancelSpeech };
}
