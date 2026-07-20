import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Play, X } from "lucide-react";
import { HOME } from "@/constants/testIds";

const DEMO_VIDEO_URL = process.env.REACT_APP_DEMO_VIDEO_URL || "";

export default function Hero() {
  const [demoOpen, setDemoOpen] = useState(false);

  return (
    <section
      id="top"
      data-testid={HOME.hero}
      className="relative overflow-hidden"
      style={{ paddingTop: 140, paddingBottom: 140 }}
    >
      <div className="zy-hero-bg" aria-hidden="true">
        <div className="zy-hero-grid" />
        <div className="zy-hero-orb zy-hero-orb-a" />
        <div className="zy-hero-orb zy-hero-orb-b" />
      </div>

      <div className="zy-container relative">
        <div className="max-w-4xl mx-auto text-center">
          <div className="zy-badge zy-reveal" style={{ transitionDelay: "0ms" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-[#1A4FFF]" />
            Powered by Anthropic Claude AI
          </div>

          <h1
            data-testid={HOME.heroHeadline}
            className="zy-h1 mt-6 zy-reveal"
            style={{ transitionDelay: "80ms" }}
          >
            The Next-Gen <span style={{ color: "var(--zy-blue)" }}>AI ERP</span> Ecosystem
          </h1>

          <p
            data-testid={HOME.heroSubheadline}
            className="zy-body mt-7 max-w-2xl mx-auto zy-reveal"
            style={{ transitionDelay: "160ms" }}
          >
            One platform. One AI. One truth. Replace 15+ tools with Zynthoro.
          </p>

          <div
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 zy-reveal"
            style={{ transitionDelay: "240ms" }}
          >
            <Link
              to="/signup"
              data-testid={HOME.heroPrimaryCta}
              className="zy-btn-primary"
            >
              Get started
              <ArrowRight size={18} />
            </Link>
            <button
              data-testid={HOME.heroSecondaryCta}
              onClick={() => setDemoOpen(true)}
              className="zy-btn-outline"
            >
              <Play size={16} />
              Watch Demo
            </button>
          </div>

          <p className="mt-7 text-sm text-[#666] zy-reveal" style={{ transitionDelay: "320ms" }}>
            Starting at €499/month · No risk · Cancel anytime
          </p>
        </div>
      </div>

      {demoOpen && (
        <div
          data-testid="hero-demo-modal"
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-8"
          style={{ background: "rgba(10,22,40,0.72)", backdropFilter: "blur(6px)" }}
          onClick={() => setDemoOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Zynthoro product demo"
        >
          <div
            className="relative w-full max-w-4xl bg-white rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setDemoOpen(false)}
              data-testid="hero-demo-modal-close"
              aria-label="Close demo"
              className="absolute top-3 right-3 z-10 w-9 h-9 rounded-full flex items-center justify-center bg-white/95 hover:bg-white border border-[#eee] shadow-sm"
            >
              <X size={16} />
            </button>

            {DEMO_VIDEO_URL ? (
              <div className="relative w-full" style={{ aspectRatio: "16 / 9" }}>
                <iframe
                  src={DEMO_VIDEO_URL}
                  title="Zynthoro product demo"
                  className="absolute inset-0 w-full h-full"
                  frameBorder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                />
              </div>
            ) : (
              <div className="p-10 sm:p-14 text-center">
                <div
                  className="w-14 h-14 rounded-full mx-auto flex items-center justify-center mb-5"
                  style={{ background: "#EAF0FF", color: "#1A4FFF" }}
                >
                  <Play size={22} />
                </div>
                <h3 className="text-[22px] font-bold tracking-tight">Live demo coming soon</h3>
                <p className="text-[14.5px] text-[#555] mt-3 max-w-md mx-auto leading-relaxed">
                  Our full product walkthrough is being recorded. In the meantime, book a free 30-minute call
                  with the founder — you&apos;ll see Zynthoro in action, live.
                </p>
                <a
                  href="https://calendly.com/zynthoro/30min"
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid="hero-demo-book-call"
                  className="zy-btn-primary mt-7 inline-flex"
                >
                  Book a free 30-min call
                  <ArrowRight size={16} />
                </a>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
