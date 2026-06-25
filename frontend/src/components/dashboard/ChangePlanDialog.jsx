import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { PLANS } from "@/lib/planCatalog";
import { Check, Crown, ArrowRight } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Change Plan dialog (Fix 8).
 *
 * Stripe price IDs for Creator/Business/Agency/Enterprise are not wired yet,
 * so non-Starter upgrades render a "Coming soon" badge per user instruction.
 * Starter still works via the existing /subscribe/starter flow.
 */
export default function ChangePlanDialog({ open, onOpenChange }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const currentPlan = user?.subscription_plan?.startsWith("Enterprise")
    ? "Enterprise"
    : user?.subscription_plan || "Presale";

  const onSelect = (plan) => {
    if (plan.key === currentPlan) return;
    if (plan.comingSoon) {
      toast.message(`${plan.name} self-service checkout opens at launch (30 June 2026).`);
      return;
    }
    setBusy(true);
    window.location.href = plan.upgradePath;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[860px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Change your plan</DialogTitle>
          <DialogDescription>
            You&apos;re currently on <b>{currentPlan}</b>. Pick a plan that fits where you&apos;re going.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
          {PLANS.map((plan) => {
            const isCurrent = plan.key === currentPlan;
            const isEnterprise = plan.key === "Enterprise";
            return (
              <div
                key={plan.key}
                data-testid={`changeplan-${plan.key.toLowerCase()}`}
                className={`rounded-xl border-2 p-4 flex flex-col ${
                  isCurrent
                    ? "border-[#1A4FFF] bg-[#EAF0FF]"
                    : isEnterprise
                      ? "border-[#D4AF37] bg-[#FFFCEC]"
                      : "border-[#eee] bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <h3 className="text-[15px] font-bold tracking-tight flex items-center gap-1.5">
                    {isEnterprise && <Crown size={14} style={{ color: "#8a6e1d" }} />}
                    {plan.name}
                  </h3>
                  {isCurrent && (
                    <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-[#1A4FFF] text-white">
                      Current
                    </span>
                  )}
                  {plan.badge && !isCurrent && (
                    <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-[#1A4FFF] text-white">
                      {plan.badge}
                    </span>
                  )}
                </div>
                <p className="text-[18px] font-bold tracking-tight">{plan.priceLabel}</p>
                <p className="text-[12px] text-[#666] mt-1">{plan.tagline}</p>
                <ul className="mt-3 space-y-1.5 flex-1">
                  {plan.highlights.slice(0, 3).map((h, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[12.5px] text-[#444]">
                      <Check size={12} className="mt-1 shrink-0" style={{ color: "#1A4FFF" }} />
                      {h}
                    </li>
                  ))}
                </ul>
                <button
                  disabled={isCurrent || busy}
                  onClick={() => onSelect(plan)}
                  data-testid={`changeplan-${plan.key.toLowerCase()}-select`}
                  className={`mt-4 px-3 py-2 rounded-md text-[13px] font-semibold inline-flex items-center justify-center gap-1.5 transition-colors ${
                    isCurrent
                      ? "bg-[#eee] text-[#888] cursor-default"
                      : isEnterprise
                        ? "bg-[#D4AF37] text-white hover:opacity-90"
                        : "bg-[#1A4FFF] text-white hover:opacity-90"
                  }`}
                >
                  {isCurrent ? "Your plan" : (
                    <>
                      {plan.comingSoon ? "Coming soon" : "Upgrade"}
                      {!plan.comingSoon && <ArrowRight size={13} />}
                    </>
                  )}
                </button>
                {plan.comingSoon && !isCurrent && (
                  <p className="text-[10.5px] text-[#888] mt-2 text-center">
                    Self-service checkout opens 30 June 2026
                  </p>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-[11.5px] text-[#777] mt-4">
          Downgrades take effect at the end of your current billing period.
          Upgrades are prorated and active immediately.
        </p>
      </DialogContent>
    </Dialog>
  );
}
