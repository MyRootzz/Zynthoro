import { Lock, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PLAN_BY_KEY } from "@/lib/planCatalog";

/**
 * Reusable upgrade-lock card / overlay.
 *
 * Usage:
 *   <UpgradeLock requiredPlan="Creator" feature="AI Video Suite" />
 *   <UpgradeLock requiredPlan="Business" feature="AI lead scoring" compact />
 *
 * It NEVER hard-blocks — it always renders a friendly message and an
 * "Upgrade to <plan>" button that links to /dashboard/settings (where
 * the Change Plan dialog lives) or the public pricing page.
 */
export default function UpgradeLock({
  requiredPlan = "Creator",
  feature = "this feature",
  compact = false,
  className = "",
}) {
  const navigate = useNavigate();
  const plan = PLAN_BY_KEY[requiredPlan] || PLAN_BY_KEY.Creator;

  const onUpgrade = () => {
    // Settings → Billing shows the Change Plan dialog.
    navigate("/dashboard/settings#billing");
  };

  if (compact) {
    return (
      <div
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-[12.5px] font-medium ${className}`}
        style={{ background: "#FFFCEC", color: "#8a6e1d", border: "1px solid #f1e4a8" }}
        data-testid="upgrade-lock-compact"
      >
        <Lock size={12} />
        <span>{plan.name}+ feature</span>
        <button
          onClick={onUpgrade}
          className="ml-1 text-[#1A4FFF] font-semibold hover:underline"
          data-testid={`upgrade-to-${plan.key.toLowerCase()}`}
        >
          Upgrade
        </button>
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl p-6 sm:p-8 text-center ${className}`}
      style={{
        background: "linear-gradient(180deg,#FFFCEC 0%, #ffffff 80%)",
        border: "2px dashed #D4AF37",
      }}
      data-testid="upgrade-lock"
    >
      <div
        className="w-12 h-12 mx-auto rounded-full flex items-center justify-center mb-4"
        style={{ background: "rgba(212,175,55,0.18)" }}
      >
        <Lock size={20} style={{ color: "#8a6e1d" }} />
      </div>
      <p
        className="text-[11px] tracking-[0.18em] font-bold mb-2"
        style={{ color: "#8a6e1d" }}
      >
        AVAILABLE FROM {plan.name.toUpperCase()}
      </p>
      <h3 className="text-[20px] sm:text-[22px] font-bold tracking-tight text-black">
        {feature}
      </h3>
      <p className="text-[14px] text-[#555] mt-2 max-w-md mx-auto">
        This feature is available from <b>{plan.name}</b> ({plan.priceLabel}).
        Upgrade to unlock it for your team.
      </p>
      <ul className="mt-5 space-y-1.5 max-w-sm mx-auto text-left">
        {plan.highlights.slice(0, 3).map((h, i) => (
          <li key={i} className="flex items-start gap-2 text-[13px] text-[#444]">
            <span
              className="mt-1 w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: "#1A4FFF" }}
            />
            {h}
          </li>
        ))}
      </ul>
      <button
        onClick={onUpgrade}
        data-testid={`upgrade-to-${plan.key.toLowerCase()}-cta`}
        className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 rounded-md font-semibold text-white"
        style={{ background: "#1A4FFF" }}
      >
        Upgrade to {plan.name}
        <ArrowRight size={16} />
      </button>
    </div>
  );
}
