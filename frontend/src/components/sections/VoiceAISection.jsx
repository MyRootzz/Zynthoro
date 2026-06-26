import { Mic, Hand, Smartphone, Factory } from "lucide-react";
import { HOME } from "@/constants/testIds";

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

          {/* Right — visual */}
          <div className="zy-reveal flex justify-center">
            <div
              className="relative rounded-3xl p-10 sm:p-14"
              style={{
                background: "linear-gradient(140deg, rgba(212,175,55,0.18) 0%, rgba(26,79,255,0.12) 100%)",
                border: "1px solid rgba(212,175,55,0.32)",
              }}
            >
              <div
                className="w-32 h-32 sm:w-44 sm:h-44 rounded-full flex items-center justify-center mx-auto"
                style={{
                  background: "linear-gradient(135deg,#1A4FFF 0%,#0A1628 100%)",
                  boxShadow: "0 0 80px rgba(212,175,55,0.35)",
                }}
              >
                <Mic size={56} style={{ color: "#D4AF37" }} />
              </div>
              <div className="absolute -inset-1 rounded-3xl pointer-events-none">
                <span className="absolute top-6 left-6 w-3 h-3 rounded-full bg-red-500 animate-pulse" aria-hidden="true" />
              </div>
              <p className="text-center mt-6 text-[13px] tracking-[0.18em] uppercase font-bold" style={{ color: "#D4AF37" }}>
                Press · Speak · Done
              </p>
              <p className="text-center mt-2 text-[12.5px] text-white/55">
                Works in Chrome, Edge and most Chromium browsers — desktop & mobile.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
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
