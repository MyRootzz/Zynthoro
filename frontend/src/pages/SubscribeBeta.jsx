import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Sparkles, Lock, Check, Loader2, ArrowRight, AlertCircle } from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { PresaleDialogProvider } from "@/components/sections/PresaleDialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PERKS = [
  "Full Starter plan access — every feature included",
  "Price locked for life at €4.99/month",
  "Founding Member badge on your profile",
  "Priority access to every new module before public release",
  "Direct line to the founder for feedback & feature requests",
];

export default function SubscribeBeta() {
  const [status, setStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [email, setEmail] = useState("");
  const [checkingOut, setCheckingOut] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    document.title = "Beta Founding Member · Zynthoro";
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/beta/status`);
        if (!active) return;
        setStatus(data);
        if (data?.capped) {
          // Auto-redirect to Starter pricing if the cap has been reached.
          toast.info("All 100 beta spots are taken — sending you to standard pricing.");
          setTimeout(() => navigate("/#pricing", { replace: true }), 2400);
        }
      } catch (e) {
        toast.error(e?.response?.data?.detail || "Couldn't load beta status.");
      } finally {
        if (active) setLoadingStatus(false);
      }
    })();
    return () => { active = false; };
  }, [navigate]);

  // Detect Stripe return
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const result = params.get("checkout");
    if (result === "success") {
      toast.success("Welcome aboard, Founding Member! Check your email for next steps.");
    } else if (result === "cancelled") {
      toast.info("Checkout cancelled — your spot is still open.");
    }
  }, [location.search]);

  const checkout = async () => {
    setCheckingOut(true);
    try {
      const { data } = await axios.post(`${API}/beta/checkout`, {
        origin_url: window.location.origin,
        email: email.trim() || null,
      });
      window.location.href = data.url;
    } catch (e) {
      if (e?.response?.status === 410) {
        toast.error("All 100 spots have just been claimed. Redirecting to standard pricing.");
        setTimeout(() => navigate("/#pricing", { replace: true }), 2000);
      } else {
        toast.error(e?.response?.data?.detail || "Couldn't start checkout. Please try again.");
      }
    } finally {
      setCheckingOut(false);
    }
  };

  const remaining = status?.spots_remaining ?? 100;
  const total = status?.spots_total ?? 100;
  const filled = total - remaining;
  const pct = Math.min(100, Math.max(0, (filled / total) * 100));

  return (
    <PresaleDialogProvider>
      <div className="min-h-screen flex flex-col bg-white">
        <Navbar />

        <main className="flex-1">
          <section className="zy-section" style={{ background: "#0A1628" }}>
            <div className="zy-container">
              <div className="max-w-3xl mx-auto text-center">
                <p
                  className="text-[11px] tracking-[0.22em] font-bold uppercase mb-4"
                  style={{ color: "#D4AF37" }}
                  data-testid="beta-eyebrow"
                >
                  Founding Member · Beta
                </p>
                <h1
                  className="text-[40px] sm:text-[54px] lg:text-[64px] font-bold tracking-tight text-white leading-[1.02]"
                  data-testid="beta-h1"
                >
                  €4.99/mo. <span style={{ color: "#D4AF37" }}>Locked for life.</span>
                </h1>
                <p className="mt-5 text-[16px] sm:text-[17px] text-white/75 max-w-xl mx-auto leading-relaxed">
                  Be one of the first 100 founders. Full Starter plan access at a price the rest of the world will never see again.
                </p>

                {/* Counter */}
                <div
                  className="mt-10 max-w-md mx-auto p-6 rounded-2xl"
                  style={{
                    background: "linear-gradient(140deg, rgba(212,175,55,0.16) 0%, rgba(26,79,255,0.10) 100%)",
                    border: "1px solid rgba(212,175,55,0.28)",
                  }}
                  data-testid="beta-counter"
                >
                  {loadingStatus ? (
                    <p className="text-white/70 text-[14px]"><Loader2 size={14} className="inline animate-spin mr-2" /> Checking availability…</p>
                  ) : status?.capped ? (
                    <div className="flex flex-col items-center gap-2 text-white">
                      <AlertCircle size={22} className="text-red-400" />
                      <p className="font-semibold">All 100 spots are taken.</p>
                      <p className="text-[13px] text-white/60">Redirecting to standard pricing…</p>
                    </div>
                  ) : (
                    <>
                      <p
                        className="text-[28px] sm:text-[32px] font-bold text-white"
                        data-testid="beta-spots-remaining"
                      >
                        <span style={{ color: "#D4AF37" }}>{remaining}</span> of {total} spots remaining
                      </p>
                      <div className="mt-4 h-2 w-full rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.10)" }}>
                        <div
                          className="h-full transition-all duration-700"
                          style={{ width: `${pct}%`, background: "#D4AF37" }}
                        />
                      </div>
                      <p className="mt-3 text-[12px] text-white/55">{filled} founder{filled === 1 ? "" : "s"} already on board.</p>
                    </>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Perks + CTA */}
          {!status?.capped && (
            <section className="zy-section" style={{ background: "#fff" }}>
              <div className="zy-container max-w-3xl">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
                  <div>
                    <p className="zy-eyebrow mb-3" style={{ color: "#1A4FFF" }}>What&rsquo;s included</p>
                    <h2 className="text-[28px] sm:text-[32px] font-bold tracking-tight">
                      Everything in Starter. <span style={{ color: "#1A4FFF" }}>Forever cheaper.</span>
                    </h2>
                    <ul className="mt-6 space-y-3">
                      {PERKS.map((p) => (
                        <li key={p} className="flex items-start gap-2.5 text-[14.5px] text-[#333]">
                          <Check size={18} className="mt-0.5 shrink-0" style={{ color: "#1A4FFF" }} />
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div
                    className="rounded-2xl p-6 sm:p-7"
                    style={{ background: "#FAFAFB", border: "1px solid #eee" }}
                  >
                    <div className="flex items-baseline gap-2">
                      <p className="text-[48px] font-bold tracking-tight" style={{ color: "#0A1628" }}>€4.99</p>
                      <p className="text-[14px] text-[#666]">/month · forever</p>
                    </div>
                    <p className="text-[12.5px] text-[#888] mt-1 flex items-center gap-1.5">
                      <Lock size={11} /> Price locked. No annual increases. Ever.
                    </p>

                    <label className="block mt-6 text-[12px] font-semibold text-[#555] uppercase tracking-wider">
                      Your email (optional)
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@company.com"
                      data-testid="beta-email"
                      className="mt-1.5 w-full text-[14px] px-3.5 py-2.5 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]"
                    />

                    <button
                      onClick={checkout}
                      disabled={checkingOut || loadingStatus || status?.capped}
                      data-testid="beta-checkout-btn"
                      className="mt-4 w-full inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-md text-[14.5px] font-bold text-white disabled:opacity-60 transition-transform hover:scale-[1.02]"
                      style={{ background: "#1A4FFF" }}
                    >
                      {checkingOut ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                      {checkingOut ? "Redirecting to Stripe…" : "Claim my Founding Member spot"}
                      {!checkingOut && <ArrowRight size={15} />}
                    </button>

                    <p className="text-[11.5px] text-[#888] mt-3 text-center">
                      Secured by Stripe · 14-day money-back guarantee · Cancel anytime
                    </p>
                  </div>
                </div>
              </div>
            </section>
          )}
        </main>

        <Footer />
      </div>
    </PresaleDialogProvider>
  );
}
