import { Check, Sparkles } from "lucide-react";
import { HOME } from "@/constants/testIds";

const features = [
  "Guides you to the right feature instantly",
  "Checks your subscription and suggests upgrades",
  "Helps complete tasks step by step",
  "Works for every subscription level",
];

export default function Assist() {
  return (
    <section
      data-testid={HOME.assist}
      className="zy-section"
      style={{ background: "var(--zy-blue)", color: "#fff" }}
    >
      <div className="zy-container">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-14 items-center">
          <div className="zy-reveal">
            <p
              className="text-[12px] font-semibold tracking-[0.18em] uppercase"
              style={{ color: "rgba(255,255,255,0.7)" }}
            >
              Zynthoro Assist
            </p>
            <h2 className="zy-h2 mt-4" style={{ color: "#fff" }}>
              Meet Zynthoro Assist — your AI guide, always there.
            </h2>
            <p className="mt-6 text-[17px] leading-relaxed" style={{ color: "rgba(255,255,255,0.85)" }}>
              Available 24/7 in the bottom right corner of your dashboard. Zynthoro Assist helps you navigate, complete tasks, and grow your business — step by step.
            </p>

            <ul className="mt-8 space-y-4">
              {features.map((f) => (
                <li key={f} className="flex items-start gap-3 text-[15.5px]" style={{ color: "rgba(255,255,255,0.95)" }}>
                  <span
                    className="mt-0.5 shrink-0 inline-flex items-center justify-center rounded-full"
                    style={{ width: 22, height: 22, background: "rgba(255,255,255,0.15)" }}
                  >
                    <Check size={14} />
                  </span>
                  {f}
                </li>
              ))}
            </ul>
          </div>

          {/* Mock chat panel */}
          <div className="zy-reveal" style={{ transitionDelay: "120ms" }}>
            <div
              className="rounded-2xl p-5 sm:p-6 shadow-2xl"
              style={{
                background: "#fff",
                color: "#000",
                border: "1px solid rgba(255,255,255,0.2)",
              }}
            >
              <div className="flex items-center gap-3 pb-4 border-b border-[#eee]">
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center"
                  style={{ background: "#EAF0FF", color: "var(--zy-blue)" }}
                >
                  <Sparkles size={18} />
                </div>
                <div>
                  <p className="text-[14px] font-semibold">Zynthoro Assist</p>
                  <p className="text-[12px] text-[#666]">Online · Claude AI</p>
                </div>
                <span className="ml-auto text-[11px] font-medium text-[#1A4FFF]">● Active</span>
              </div>

              <div className="space-y-3 mt-5">
                <div className="text-[13.5px] bg-[#F4F6FB] rounded-lg rounded-tl-sm px-4 py-3 max-w-[85%]">
                  Hi Ramona — want me to draft this month&apos;s VAT report and pull in the unpaid invoices?
                </div>
                <div
                  className="text-[13.5px] rounded-lg rounded-tr-sm px-4 py-3 max-w-[85%] ml-auto text-white"
                  style={{ background: "var(--zy-blue)" }}
                >
                  Yes, and remind the 3 clients past 14 days.
                </div>
                <div className="text-[13.5px] bg-[#F4F6FB] rounded-lg rounded-tl-sm px-4 py-3 max-w-[90%]">
                  Done. Report drafted in <b>Accounting</b>, reminders scheduled in <b>Invoicing</b>. Anything else?
                </div>
              </div>

              <div className="mt-5 flex items-center gap-2 rounded-lg border border-[#eee] px-3 py-2.5">
                <Sparkles size={14} style={{ color: "var(--zy-blue)" }} />
                <input
                  className="flex-1 text-[13.5px] outline-none bg-transparent"
                  placeholder="Ask Zynthoro anything…"
                  readOnly
                />
                <kbd className="text-[11px] px-1.5 py-0.5 rounded bg-[#F4F6FB] text-[#666]">⏎</kbd>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
