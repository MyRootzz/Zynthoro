import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Mic, Hand, Smartphone, Factory, MicOff, ArrowRight, Check, Loader2 } from "lucide-react";
import { HOME } from "@/constants/testIds";
import { useVoiceInput } from "@/lib/useVoiceInput";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function VoiceAISection() {
  return (
    <section
      id="voice-ai"
      data-testid={HOME.voiceAI || "home-voice-ai"}
      className="zy-section"
      style={{ background: "#0A1628" }}
    >
      <div className="zy-container">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          {/* Left — copy */}
          <div className="zy-reveal text-white">
            <p
              className="text-[11px] tracking-[0.22em] font-bold uppercase mb-4"
              style={{ color: "#D4AF37" }}
            >
              Talk to your AI
            </p>
            <h2 className="text-[34px] sm:text-[42px] lg:text-[48px] font-bold tracking-tight leading-[1.05]">
              Speak your mind.<br />
              <span style={{ color: "#D4AF37" }}>Zynthoro listens.</span>
            </h2>
            <p className="mt-5 text-[15.5px] text-white/75 leading-relaxed max-w-xl">
              Hands-free voice input on every assistant — Zyntha, Thoro, Zyona and Zynthoro Assist. Built right into the chat. No accounts, no extra cost.
            </p>

            <div className="mt-7 space-y-3">
              <Feature icon={Factory} title="Perfect for production environments" desc="Flour on your hands? Just speak. Voice notes become structured work orders." />
              <Feature icon={Smartphone} title="On the go, on mobile" desc="Drive between locations? Capture decisions and tasks without lifting a finger." />
              <Feature icon={Hand} title="Truly hands-free" desc="Live transcription, automatic send on pause — no extra clicks." />
            </div>
          </div>

          {/* Right — interactive try-the-mic */}
          <div className="zy-reveal flex justify-center">
            <VoiceTryout />
          </div>
        </div>
      </div>
    </section>
  );
}

function VoiceTryout() {
  const [transcript, setTranscript] = useState("");
  const [leadId, setLeadId] = useState(null);
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [emailSent, setEmailSent] = useState(false);
  const reportedRef = useRef(false);

  const { supported, listening, interim, error, toggle } = useVoiceInput({
    onFinal: (text) => setTranscript((prev) => (prev ? prev + " " : "") + text),
  });

  // Fire-and-forget anonymous lead capture on first real transcript.
  useEffect(() => {
    if (!transcript || reportedRef.current) return;
    reportedRef.current = true;
    (async () => {
      try {
        const { data } = await axios.post(`${API}/voice-tryout`, {
          transcript,
          language: typeof navigator !== "undefined" ? navigator.language : null,
        });
        if (data?.id) setLeadId(data.id);
      } catch {
        // Silently ignore — anonymous logging is best-effort.
      }
    })();
  }, [transcript]);

  const live = interim || transcript;

  const submitEmail = async (e) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      toast.error("Please enter a valid email.");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/voice-tryout`, {
        transcript,
        email: trimmed,
        language: typeof navigator !== "undefined" ? navigator.language : null,
      });
      setEmailSent(true);
      toast.success("Thanks — we'll be in touch for your demo.");
    } catch {
      toast.error("Couldn't send that. Try again in a moment.");
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setTranscript("");
    setLeadId(null);
    setEmail("");
    setEmailSent(false);
    reportedRef.current = false;
  };

  return (
    <div
      className="relative rounded-3xl p-8 sm:p-10 w-full max-w-[460px]"
      style={{
        background: "linear-gradient(140deg, rgba(212,175,55,0.18) 0%, rgba(26,79,255,0.12) 100%)",
        border: "1px solid rgba(212,175,55,0.32)",
      }}
      data-testid="home-voice-tryout"
    >
      <button
        type="button"
        onClick={toggle}
        disabled={!supported}
        aria-pressed={listening}
        aria-label={listening ? "Stop voice tour" : "Start voice tour"}
        data-testid="home-voice-mic-btn"
        className="group relative mx-auto w-32 h-32 sm:w-40 sm:h-40 rounded-full flex items-center justify-center transition-transform hover:scale-[1.03] disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: "linear-gradient(135deg,#1A4FFF 0%,#0A1628 100%)",
          boxShadow: listening
            ? "0 0 90px rgba(220,38,38,0.55), 0 0 50px rgba(212,175,55,0.4)"
            : "0 0 80px rgba(212,175,55,0.35)",
        }}
      >
        {supported ? (
          <Mic size={56} style={{ color: "#D4AF37" }} />
        ) : (
          <MicOff size={56} style={{ color: "#8a7732" }} />
        )}
        {listening && (
          <span
            className="absolute top-2 right-2 w-3.5 h-3.5 rounded-full bg-red-500 animate-pulse"
            aria-hidden="true"
          />
        )}
      </button>

      <p
        className="text-center mt-6 text-[12.5px] tracking-[0.18em] uppercase font-bold"
        style={{ color: "#D4AF37" }}
      >
        {!supported
          ? "Voice requires Chrome or Edge"
          : listening
          ? "Listening… speak now"
          : "Tap to try — no signup"}
      </p>

      <div
        className="mt-4 min-h-[64px] rounded-xl p-3 text-[13.5px] text-white/85 leading-relaxed"
        style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)" }}
        data-testid="home-voice-transcript"
        aria-live="polite"
      >
        {error ? (
          <span className="text-red-300">{error}</span>
        ) : live ? (
          <>
            {transcript && <span>{transcript}</span>}
            {interim && <span className="text-white/55"> {interim}</span>}
          </>
        ) : (
          <span className="text-white/45">
            Try saying: <em>&ldquo;Add a new production order for 500 cookies.&rdquo;</em>
          </span>
        )}
      </div>

      {/* Email capture appears after a successful transcript */}
      {transcript && !emailSent && (
        <form
          onSubmit={submitEmail}
          className="mt-4 rounded-xl p-3"
          style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,55,0.22)" }}
          data-testid="home-voice-lead-form"
        >
          <p className="text-[12.5px] text-white/80">
            <span className="font-semibold" style={{ color: "#D4AF37" }}>Liked that?</span>{" "}
            Drop your email — we&apos;ll show you what Zynthoro can do with your business in 15&nbsp;minutes.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              data-testid="home-voice-lead-email"
              className="flex-1 text-[13px] px-3 py-2 rounded-md outline-none text-white placeholder-white/40"
              style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)" }}
            />
            <button
              type="submit"
              disabled={submitting}
              data-testid="home-voice-lead-submit"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-[13px] font-semibold text-[#0A1628] disabled:opacity-60"
              style={{ background: "#D4AF37" }}
            >
              {submitting ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
              {submitting ? "Sending…" : "Get demo"}
            </button>
          </div>
        </form>
      )}

      {emailSent && (
        <div
          className="mt-4 rounded-xl p-3 flex items-start gap-2"
          style={{ background: "rgba(34,197,94,0.10)", border: "1px solid rgba(34,197,94,0.32)" }}
          data-testid="home-voice-lead-success"
        >
          <Check size={16} className="mt-0.5 text-green-400 shrink-0" />
          <p className="text-[12.5px] text-white/85">
            We received your request. Expect a calendar link from our team within 24&nbsp;hours.
          </p>
        </div>
      )}

      {transcript && !listening && (
        <button
          type="button"
          onClick={reset}
          data-testid="home-voice-reset"
          className="mt-3 mx-auto block text-[11.5px] text-white/55 hover:text-white"
        >
          Clear transcript &amp; try again
        </button>
      )}

      <p className="text-center mt-3 text-[11.5px] text-white/45">
        {leadId
          ? "Captured — anonymous unless you share your email."
          : "Works in Chrome, Edge and most Chromium browsers — desktop & mobile."}
      </p>
    </div>
  );
}

function Feature({ icon: Icon, title, desc }) {
  return (
    <div className="flex items-start gap-3">
      <span
        className="inline-flex items-center justify-center w-9 h-9 rounded-lg shrink-0"
        style={{ background: "rgba(212,175,55,0.16)" }}
      >
        <Icon size={16} style={{ color: "#D4AF37" }} />
      </span>
      <div>
        <p className="text-[14.5px] font-semibold text-white">{title}</p>
        <p className="text-[13px] text-white/65 mt-0.5 max-w-sm">{desc}</p>
      </div>
    </div>
  );
}
