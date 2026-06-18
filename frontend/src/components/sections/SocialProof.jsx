import { Award, Sparkles, ShieldCheck } from "lucide-react";
import { HOME } from "@/constants/testIds";

export default function SocialProof() {
  return (
    <section
      data-testid={HOME.socialProof}
      style={{ background: "var(--zy-grey-light)" }}
      className="py-16"
    >
      <div className="zy-container">
        <div className="flex flex-col items-center text-center gap-6">
          <p className="text-[13px] tracking-[0.18em] uppercase font-semibold text-[#666]">
            Trusted by ambitious founders and SMEs across Europe
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3 md:gap-4">
            <div className="zy-badge">
              <Sparkles size={14} />
              Selected for Anthropic Claude for Startups
            </div>
            <div className="zy-badge zy-badge-gold">
              <Award size={14} />
              XPRIZE Nominee 2026
            </div>
            <div className="zy-badge">
              <ShieldCheck size={14} />
              GDPR-Ready · EU-Hosted
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
