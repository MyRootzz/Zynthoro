import { Link } from "react-router-dom";
import { Lock, ArrowRight, Sparkles } from "lucide-react";

// Replacement UI shown when a trial user navigates to a locked (non-AI)
// module. Renders inside the dashboard main area, so the sidebar / trial
// banner stay in place — user can still click over to an AI assistant.
export default function LockedModule({ moduleName }) {
  return (
    <div
      data-testid="locked-module"
      className="max-w-2xl mx-auto text-center py-14 sm:py-20"
    >
      <div
        className="inline-flex items-center justify-center rounded-2xl mb-6"
        style={{ width: 72, height: 72, background: "#1A4FFF14" }}
      >
        <Lock size={28} style={{ color: "var(--zy-blue)" }} />
      </div>

      <p
        className="uppercase tracking-[0.18em] text-[12px] mb-3"
        style={{ color: "var(--zy-blue)" }}
      >
        Locked during your free trial
      </p>

      <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#0A1628] leading-[1.15]">
        {moduleName ? `${moduleName} is available on paid tiers.` : "This module is available on paid tiers."}
      </h2>

      <p className="mt-5 text-[15px] text-black/60 leading-relaxed max-w-lg mx-auto">
        Your 24-hour free trial gives you full access to the four AI assistants — Zyntha, Thoro, Zyona, and Zynthoro Assist. Upgrade to a Kickstart tier to unlock every module.
      </p>

      <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
        <Link
          to="/#kickstart"
          data-testid="locked-module-upgrade"
          className="inline-flex items-center gap-1.5 rounded-full px-5 py-2.5 text-[14px] font-semibold text-white transition-opacity hover:opacity-90"
          style={{ background: "var(--zy-blue)" }}
        >
          Upgrade to unlock <ArrowRight size={15} />
        </Link>
        <Link
          to="/dashboard/zyntha"
          data-testid="locked-module-ai"
          className="inline-flex items-center gap-1.5 rounded-full px-5 py-2.5 text-[14px] font-semibold text-[var(--zy-blue)] border border-[var(--zy-blue)]/25 hover:bg-[var(--zy-blue)]/[0.05] transition-colors"
        >
          <Sparkles size={14} /> Chat with an AI assistant
        </Link>
      </div>
    </div>
  );
}
