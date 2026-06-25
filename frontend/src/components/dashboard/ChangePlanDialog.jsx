import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { PLANS } from "@/lib/planCatalog";
import { Check, Crown, ArrowRight, Loader2 } from "lucide-react";
import { useAuth, API, formatApiError } from "@/contexts/AuthContext";

/**
 * Change Plan dialog (Fix 8) — wired to real Stripe Subscription Checkout.
 *
 * Calls POST /api/checkout/subscription/session with {plan_key}, then redirects
 * the browser to the returned Stripe-hosted checkout URL. Stripe handles all
 * card capture / SCA / 3DS; on success it redirects back to
 * /dashboard/settings?checkout=success&session_id=… where the webhook will
 * already have flipped subscription_plan in MongoDB.
 */
export default function ChangePlanDialog({ open, onOpenChange }) {
  const { user } = useAuth();
  const [busyKey, setBusyKey] = useState(null);
  const currentPlan = user?.subscription_plan || "Presale";

  const onSelect = async (plan) => {
    if (plan.key === currentPlan) return;
    setBusyKey(plan.key);
    try {
      const { data } = await axios.post(`${API}/checkout/subscription/session`, {
        plan_key: plan.key,
      });
      if (data?.url) {
        window.location.href = data.url;
        return;
      }
      toast.error("Checkout could not be opened — please try again.");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Stripe checkout error.");
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[1024px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Change your plan</DialogTitle>
          <DialogDescription>
            You&apos;re currently on <b>{currentPlan}</b>. Pick the plan that fits where you&apos;re going — checkout is secure via Stripe.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 mt-3">
          {PLANS.map((plan) => {
            const isCurrent = plan.key === currentPlan;
            const isEnt = plan.isEnterprise;
            const isBusy = busyKey === plan.key;
            return (
              <div
                key={plan.key}
                data-testid={`changeplan-${plan.key.toLowerCase().replace(/\s+/g, "-")}`}
                className={`rounded-xl border-2 p-4 flex flex-col ${
                  isCurrent
                    ? "border-[#1A4FFF] bg-[#EAF0FF]"
                    : isEnt
                      ? "border-[#D4AF37] bg-[#FFFCEC]"
                      : "border-[#eee] bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-2">
                  <h3 className="text-[14.5px] font-bold tracking-tight flex items-center gap-1.5 leading-tight">
                    {isEnt && <Crown size={13} style={{ color: "#8a6e1d" }} />}
                    {plan.name}
                  </h3>
                  {isCurrent && (
                    <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-[#1A4FFF] text-white shrink-0">
                      Current
                    </span>
                  )}
                  {plan.badge && !isCurrent && (
                    <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-[#1A4FFF] text-white shrink-0">
                      {plan.badge}
                    </span>
                  )}
                </div>
                <p className="text-[18px] font-bold tracking-tight">{plan.priceLabel}</p>
                <p className="text-[11.5px] text-[#666] mt-1 leading-tight">{plan.tagline}</p>
                <ul className="mt-3 space-y-1.5 flex-1">
                  {plan.highlights.slice(0, 3).map((h, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-[12px] text-[#444]">
                      <Check size={11} className="mt-1 shrink-0" style={{ color: "#1A4FFF" }} />
                      {h}
                    </li>
                  ))}
                </ul>
                <button
                  disabled={isCurrent || isBusy || !!busyKey}
                  onClick={() => onSelect(plan)}
                  data-testid={`changeplan-${plan.key.toLowerCase().replace(/\s+/g, "-")}-select`}
                  className={`mt-4 px-3 py-2 rounded-md text-[12.5px] font-semibold inline-flex items-center justify-center gap-1.5 transition-colors ${
                    isCurrent
                      ? "bg-[#eee] text-[#888] cursor-default"
                      : isEnt
                        ? "bg-[#D4AF37] text-white hover:opacity-90"
                        : "bg-[#1A4FFF] text-white hover:opacity-90"
                  } disabled:opacity-60`}
                >
                  {isBusy ? (
                    <>
                      <Loader2 size={13} className="animate-spin" /> Opening…
                    </>
                  ) : isCurrent ? (
                    "Your plan"
                  ) : (
                    <>
                      Upgrade <ArrowRight size={13} />
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        <p className="text-[11.5px] text-[#777] mt-4">
          Secure checkout via Stripe. Downgrades take effect at the end of your
          current billing period. Upgrades are prorated and active immediately.
        </p>
      </DialogContent>
    </Dialog>
  );
}
