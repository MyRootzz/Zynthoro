import { useEffect, useState } from "react";
import axios from "axios";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle, ArrowRight } from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { ZyLogo } from "@/components/ZyLogo";

export default function SubscribeStarterReturn() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const sessionId = params.get("session_id");
  const [state, setState] = useState("polling"); // polling | paid | failed | expired
  const [info, setInfo] = useState(null);
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    if (!sessionId) {
      setState("failed");
      return;
    }
    let alive = true;
    let tries = 0;
    const MAX = 8;
    const INTERVAL = 2200;

    const poll = async () => {
      tries += 1;
      setAttempts(tries);
      try {
        const { data } = await axios.get(`${API}/checkout/starter/status/${sessionId}`);
        if (!alive) return;
        setInfo(data);
        if (data.payment_status === "paid") {
          setState("paid");
          await refresh();
          return;
        }
        if (data.status === "expired") {
          setState("expired");
          return;
        }
        if (tries >= MAX) {
          setState("failed");
          return;
        }
        setTimeout(poll, INTERVAL);
      } catch (e) {
        if (!alive) return;
        if (tries >= MAX) {
          setState("failed");
        } else {
          setTimeout(poll, INTERVAL);
        }
      }
    };
    poll();
    return () => { alive = false; };
    // eslint-disable-next-line
  }, [sessionId]);

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <header className="px-6 sm:px-10 py-6 border-b border-[#eee] flex items-center justify-between">
        <Link to="/" className="inline-flex items-center" style={{ background: "#0A1628", padding: "8px 14px", borderRadius: 8 }}>
          <ZyLogo size={18} />
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[480px] text-center">
          {state === "polling" && (
            <>
              <Loader2 size={40} className="animate-spin mx-auto" style={{ color: "#1A4FFF" }} />
              <h1 className="text-[24px] font-bold tracking-tight mt-5">Confirming your payment…</h1>
              <p className="text-[14px] text-[#555] mt-2">Attempt {attempts}. This usually takes a few seconds.</p>
            </>
          )}
          {state === "paid" && (
            <>
              <CheckCircle2 size={56} className="mx-auto" style={{ color: "#16a34a" }} />
              <h1 className="text-[26px] font-bold tracking-tight mt-5">Welcome to Zynthoro Starter!</h1>
              <p className="text-[14.5px] text-[#555] mt-3">
                {info?.package_id === "starter_founder"
                  ? "Founder pricing locked: €99/month for your first 3 months, then €499/month."
                  : "Your Starter plan is active at €499/month."}
              </p>
              <button onClick={() => navigate("/dashboard")} className="zy-btn-primary mt-7" data-testid="paid-go-dashboard">
                Open my dashboard <ArrowRight size={15} />
              </button>
            </>
          )}
          {state === "expired" && (
            <>
              <XCircle size={48} className="mx-auto text-[#dc2626]" />
              <h1 className="text-[22px] font-bold tracking-tight mt-5">Checkout session expired</h1>
              <p className="text-[14px] text-[#555] mt-2">Please start over and complete the payment in time.</p>
              <button onClick={() => navigate("/subscribe/starter")} className="zy-btn-primary mt-6">
                Try again
              </button>
            </>
          )}
          {state === "failed" && (
            <>
              <XCircle size={48} className="mx-auto text-[#dc2626]" />
              <h1 className="text-[22px] font-bold tracking-tight mt-5">Payment status unknown</h1>
              <p className="text-[14px] text-[#555] mt-2">If you completed the payment, check your email for confirmation. Otherwise please try again.</p>
              <button onClick={() => navigate("/subscribe/starter")} className="zy-btn-primary mt-6">
                Back to start
              </button>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
