import { ArrowRight, Clock } from "lucide-react";
import { HOME } from "@/constants/testIds";
import { usePresaleDialog } from "@/components/sections/PresaleDialog";

export default function PresaleCTA() {
  const { openDialog } = usePresaleDialog();

  return (
    <section
      id="presale"
      data-testid={HOME.presaleCta}
      className="zy-section relative overflow-hidden"
      style={{ background: "var(--zy-blue)", color: "#fff" }}
    >
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div
          className="absolute -top-32 -left-20 w-[420px] h-[420px] rounded-full"
          style={{
            background: "radial-gradient(circle, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0) 70%)",
          }}
        />
        <div
          className="absolute -bottom-32 -right-20 w-[420px] h-[420px] rounded-full"
          style={{
            background: "radial-gradient(circle, rgba(212,175,55,0.22) 0%, rgba(212,175,55,0) 70%)",
          }}
        />
      </div>

      <div className="zy-container relative">
        <div className="max-w-3xl mx-auto text-center">
          <div
            className="inline-flex items-center gap-2 text-[12px] font-semibold tracking-[0.18em] uppercase px-3 py-1.5 rounded-full zy-reveal"
            style={{ background: "rgba(255,255,255,0.12)", color: "rgba(255,255,255,0.9)" }}
          >
            <Clock size={13} />
            Launches June 22, 2026
          </div>

          <h2 className="zy-h2 mt-6 zy-reveal" style={{ color: "#fff" }}>
            Zynthoro launches June 22, 2026.
          </h2>
          <p
            className="zy-body mt-5 max-w-2xl mx-auto zy-reveal"
            style={{ color: "rgba(255,255,255,0.88)", fontSize: "1.0625rem" }}
          >
            Claim your founding member spot today. Limited presale spots available.
          </p>

          <p
            className="mt-4 text-[13px] font-semibold tracking-wide zy-reveal"
            style={{ color: "var(--zy-gold)" }}
          >
            Presale closes at launch
          </p>

          <div className="mt-9 zy-reveal">
            <button
              data-testid={HOME.presaleCtaButton}
              onClick={openDialog}
              className="zy-btn-gold"
            >
              Claim Your Presale Spot Now
              <ArrowRight size={18} />
            </button>
          </div>

          <p className="mt-6 text-[13px] zy-reveal" style={{ color: "rgba(255,255,255,0.75)" }}>
            No risk. Cancel anytime. Founding member pricing locked for life.
          </p>
        </div>
      </div>
    </section>
  );
}
