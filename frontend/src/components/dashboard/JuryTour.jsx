import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { X, ArrowRight, ArrowLeft, Sparkles } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const STORAGE_KEY = "zynthoro_jury_tour_done";

const STEPS = [
  {
    title: "Welcome, XPRIZE Jury",
    body:
      "You're inside a fully-seeded Zynthoro workspace. Five quick stops will walk you through the parts the rest of the world doesn't see yet.",
    cta: "Start the tour",
    route: "/dashboard",
  },
  {
    title: "1 · Live dashboard",
    body:
      "All 12 business domains, real demo data, and three specialised AI assistants (Zyntha, Thoro, Zyona) — all in one workspace, no plugins required.",
    cta: "Show me Projects",
    route: "/dashboard/projects",
  },
  {
    title: "2 · Projects with real data",
    body:
      "Five seeded projects across product, marketing, compliance and sales. Status, progress and owners are pre-populated so you can probe workflows immediately.",
    cta: "Open Finance & Invoicing",
    route: "/dashboard/finance",
  },
  {
    title: "3 · Finance & invoicing",
    body:
      "EUR-denominated invoices, paid/outstanding splits and live cashflow figures — the same numbers our Stripe webhooks update in production.",
    cta: "Meet Zyntha (AI content)",
    route: "/dashboard/zyntha",
  },
  {
    title: "4 · Zyntha — AI content",
    body:
      "Streaming responses powered by multi-model routing (Claude / Gemini). Try a prompt — Zyntha will write captions, hashtags and ad copy on the fly.",
    cta: "Open the Social Studio",
    route: "/dashboard/marketing",
  },
  {
    title: "5 · Marketing & Social Studio",
    body:
      "Six platforms, AI photo & video suites, content calendar and analytics — the whole growth stack, unified. You've reached the end of the tour.",
    cta: "Finish & explore freely",
    route: "/dashboard",
  },
];

export default function JuryTour() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  // Open automatically on first dashboard visit for demo users
  useEffect(() => {
    if (!user?.is_demo) return;
    const done = (() => {
      try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch { return false; }
    })();
    if (!done && location.pathname.startsWith("/dashboard")) {
      setOpen(true);
    }
  }, [user, location.pathname]);

  if (!user?.is_demo) return null;

  const close = () => {
    setOpen(false);
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch { /* ignored */ }
  };

  const next = () => {
    const target = STEPS[step];
    if (target?.route) navigate(target.route);
    if (step >= STEPS.length - 1) {
      close();
    } else {
      setStep((s) => s + 1);
    }
  };

  const prev = () => setStep((s) => Math.max(0, s - 1));

  const reopen = () => {
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignored */ }
    setStep(0);
    setOpen(true);
  };

  // Persistent re-open button when tour is closed
  if (!open) {
    return (
      <button
        onClick={reopen}
        data-testid="jury-tour-reopen"
        className="fixed bottom-5 left-5 z-40 inline-flex items-center gap-2 px-3.5 py-2 rounded-full text-[12.5px] font-semibold text-white shadow-lg hover:shadow-xl transition-shadow"
        style={{ background: "#1A4FFF" }}
      >
        <Sparkles size={13} /> Jury tour
      </button>
    );
  }

  const current = STEPS[step];
  const isFirst = step === 0;
  const isLast = step === STEPS.length - 1;

  return (
    <div
      data-testid="jury-tour-overlay"
      className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center sm:justify-end p-3 sm:p-6"
      style={{ background: "rgba(10, 22, 40, 0.55)" }}
      onClick={(e) => { if (e.target === e.currentTarget) close(); }}
    >
      <div
        className="bg-white rounded-2xl w-full sm:w-[400px] shadow-2xl overflow-hidden"
        style={{ border: "1px solid #e6e6ea" }}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-5 pt-5">
          <span
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg"
            style={{ background: "rgba(212,175,55,0.18)" }}
          >
            <Sparkles size={15} style={{ color: "#8a6e1d" }} />
          </span>
          <p className="text-[11px] tracking-[0.18em] font-bold uppercase" style={{ color: "#8a6e1d" }}>
            XPRIZE Jury Tour
          </p>
          <button
            onClick={close}
            data-testid="jury-tour-close"
            className="ml-auto p-1 text-[#888] hover:text-black"
            aria-label="Close tour"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 pt-3 pb-5">
          <h3 className="text-[18px] font-bold tracking-tight text-black">{current.title}</h3>
          <p className="mt-2 text-[13.5px] text-[#555] leading-relaxed">{current.body}</p>

          {/* Progress dots */}
          <div className="flex items-center gap-1.5 mt-5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className="h-1.5 rounded-full transition-all"
                style={{
                  width: i === step ? 22 : 8,
                  background: i === step ? "#1A4FFF" : "#e2e6f0",
                }}
              />
            ))}
            <span className="ml-auto text-[11.5px] text-[#888] tabular-nums">
              {step + 1} / {STEPS.length}
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 mt-5">
            {!isFirst && (
              <button
                onClick={prev}
                data-testid="jury-tour-prev"
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-[13px] font-medium text-[#555] border border-[#eee] hover:border-[#1A4FFF] hover:text-[#1A4FFF]"
              >
                <ArrowLeft size={13} /> Back
              </button>
            )}
            <button
              onClick={close}
              data-testid="jury-tour-skip"
              className="px-3 py-2 rounded-md text-[13px] font-medium text-[#888] hover:text-black"
            >
              Skip
            </button>
            <button
              onClick={next}
              data-testid="jury-tour-next"
              className="ml-auto inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-[13px] font-semibold text-white"
              style={{ background: "#1A4FFF" }}
            >
              {isLast ? "Finish" : current.cta} <ArrowRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
