import { useState } from "react";
import axios from "axios";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowRight, ArrowLeft, Loader2, ShieldCheck } from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { ZyLogo } from "@/components/ZyLogo";

export default function SubscribeStarter() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [submittingCheckout, setSubmittingCheckout] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="animate-spin" style={{ color: "#1A4FFF" }} />
      </div>
    );
  }
  if (!user) {
    return <Navigate to={`/signup?return=${encodeURIComponent("/subscribe/starter")}`} replace />;
  }

  const startCheckout = async () => {
    setSubmittingCheckout(true);
    try {
      const { data } = await axios.post(`${API}/checkout/starter/session`, {
        package_id: "starter_standard",
        origin_url: window.location.origin,
        verification_id: null,
      });
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not start checkout.");
      setSubmittingCheckout(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <header className="px-6 sm:px-10 py-6 border-b border-[#eee] flex items-center justify-between">
        <Link to="/" className="inline-flex items-center" style={{ background: "#0A1628", padding: "8px 14px", borderRadius: 8 }}>
          <ZyLogo size={18} />
        </Link>
        <Link to="/" className="text-[13px] text-[#666] hover:text-[#1A4FFF] inline-flex items-center gap-1.5">
          <ArrowLeft size={14} /> Back to home
        </Link>
      </header>

      <main className="flex-1 flex items-start justify-center px-6 py-12 sm:py-16">
        <div className="w-full max-w-[600px]" data-testid="subscribe-starter-offer">
          <p className="zy-eyebrow mb-3">Subscribe · Starter</p>

          <h1 className="text-[30px] sm:text-[34px] font-bold tracking-tight leading-tight">
            Start with Zynthoro Starter
          </h1>
          <p className="text-[16px] text-[#555] mt-3 leading-relaxed">
            The AI business platform for solo founders and freelancers — basic planning,
            content and communication modules. Cancel anytime.
          </p>

          <div className="mt-8 p-6 rounded-2xl border border-[#eee] bg-white">
            <div className="flex items-baseline gap-2">
              <span className="text-[36px] font-bold tracking-tight">€499</span>
              <span className="text-[15px] text-[#666]">/month</span>
            </div>
            <p className="text-[13.5px] text-[#666] mt-1.5">Billed monthly · VAT excluded · cancel anytime</p>

            <button
              onClick={startCheckout}
              disabled={submittingCheckout}
              data-testid="start-starter-checkout"
              className="zy-btn-primary mt-6 w-full disabled:opacity-70"
            >
              {submittingCheckout ? (
                <><Loader2 size={15} className="animate-spin" /> Redirecting to Stripe…</>
              ) : (
                <>Continue to secure checkout <ArrowRight size={15} /></>
              )}
            </button>
          </div>

          <p className="text-[12px] text-[#888] mt-6 leading-relaxed">
            <ShieldCheck size={11} className="inline mr-1 -mt-0.5" />
            Payment is handled securely by Stripe. Your card details never touch our servers.
          </p>
        </div>
      </main>
    </div>
  );
}
