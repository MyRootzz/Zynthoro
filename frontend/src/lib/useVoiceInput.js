import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Browser-native voice → text using the Web Speech API.
 *
 * Supported in Chrome, Edge and most Chromium-based browsers. Falls back
 * gracefully (`supported === false`) on Firefox / older Safari.
 *
 * Usage:
 *   const { supported, listening, interim, start, stop, error } = useVoiceInput({
 *     onFinal: (text) => sendMessage(text),
 *     lang: "en-US",
 *   });
 */
export function useVoiceInput({ onFinal, lang = "en-US" } = {}) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState(null);
  const recRef = useRef(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const SpeechRecognition =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);
  const supported = !!SpeechRecognition;

  useEffect(() => {
    return () => {
      try { recRef.current?.stop(); } catch { /* ignored */ }
      recRef.current = null;
    };
  }, []);

  const start = useCallback(() => {
    if (!supported) {
      setError("Voice input requires Chrome or Edge.");
      return;
    }
    if (listening) return;
    setError(null);
    setInterim("");
    try {
      const rec = new SpeechRecognition();
      rec.lang = lang;
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;

      rec.onresult = (event) => {
        let finalText = "";
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += transcript;
          else interimText += transcript;
        }
        if (interimText) setInterim(interimText);
        if (finalText) {
          setInterim("");
          onFinalRef.current?.(finalText.trim());
        }
      };
      rec.onerror = (e) => {
        setError(
          e?.error === "not-allowed"
            ? "Microphone permission denied. Allow access in your browser."
            : e?.error === "no-speech"
            ? "Didn't catch that — please try again."
            : `Voice error: ${e?.error || "unknown"}`
        );
        setListening(false);
        setInterim("");
      };
      rec.onend = () => {
        setListening(false);
        setInterim("");
      };

      recRef.current = rec;
      rec.start();
      setListening(true);
    } catch (err) {
      setError(err?.message || "Voice input failed to start.");
      setListening(false);
    }
  }, [supported, listening, lang, SpeechRecognition]);

  const stop = useCallback(() => {
    try { recRef.current?.stop(); } catch { /* ignored */ }
    setListening(false);
    setInterim("");
  }, []);

  const toggle = useCallback(() => (listening ? stop() : start()), [listening, start, stop]);

  return { supported, listening, interim, error, start, stop, toggle };
}
