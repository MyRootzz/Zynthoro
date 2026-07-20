import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";
import { CheckCircle2, Loader2, ArrowRight } from "lucide-react";
import { API } from "@/contexts/AuthContext";
import { ZyLogo } from "@/components/ZyLogo";

export default function SubscribeReturn() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const tierKey = params.get("tier");
  const [status, setStatus] = useState("checking");
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    async function poll() {
      if (!sessionId) return;
      try {
        const { data } = await axios.get(`${API}/checkout/tier/status/${sessionId}`);
        if (cancelled) return;
        setData(data);
        // 100%-off coupons produce payment_status="no_payment_required".
        const paidLike = data.payment_status === "paid" || data.payment_status === "no_payment_required";
        if (paidLike && data.provisioned) {
          setStatus("done");
          return;
        }
        if (data.payment_status === "unpaid" && data.status === "expired") {
          setStatus("failed");
          return;
        }
        attempts += 1;
        if (attempts < 15) {
          setTimeout(poll, 1500);
        } else {
          // Fallback — payment might be paid but webhook still catching up.
          const paidLike = data.payment_status === "paid" || data.payment_status === "no_payment_required";
          setStatus(paidLike ? "done" : "slow");
        }
      } catch {
        setStatus("failed");
      }
    }
    poll();
    return () => { cancelled = true; };
  }, [sessionId]);

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <header className="px-6 sm:px-10 py-6 border-b border-[#eee] flex items-center">
        <Link to="/" className="inline-flex items-center" style={{ background: "#0A1628", padding: "8px 14px", borderRadius: 8 }}>
          <ZyLogo size={18} />
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[520px] text-center" data-testid={`subscribe-return-${status}`}>
          {(status === "checking" || status === "slow") && (
            <>
              <Loader2 size={40} className="mx-auto animate-spin" style={{ color: "#1A4FFF" }} />
              <h1 className="text-[24px] font-bold tracking-tight mt-6">
                {status === "slow" ? "Nog even geduld…" : "We bevestigen je betaling…"}
              </h1>
              <p className="text-[14px] text-[#555] mt-3">
                Dit duurt normaal 2–5 seconden. Sluit dit venster niet.
              </p>
            </>
          )}
          {status === "done" && (
            <>
              <div className="w-14 h-14 rounded-full mx-auto flex items-center justify-center" style={{ background: "#EAF0FF", color: "#1A4FFF" }}>
                <CheckCircle2 size={26} />
              </div>
              <h1 className="text-[28px] font-bold tracking-tight mt-5">
                Welkom bij {data?.plan_key || "Zynthoro"} 🎉
              </h1>
              <p className="text-[15px] text-[#555] mt-3 leading-relaxed">
                Je account is direct geactiveerd. Alle vrijgeschakelde modules staan klaar op je dashboard.
              </p>
              <Link
                to="/dashboard"
                data-testid="go-to-dashboard"
                className="zy-btn-primary mt-8 inline-flex"
              >
                Naar mijn dashboard <ArrowRight size={16} />
              </Link>
            </>
          )}
          {status === "failed" && (
            <>
              <h1 className="text-[24px] font-bold tracking-tight">De betaling is niet voltooid</h1>
              <p className="text-[14px] text-[#555] mt-3">
                Je bent nog niet gefactureerd. Je kunt het opnieuw proberen of een andere tier kiezen.
              </p>
              <Link to={`/subscribe/${tierKey || "kickstart_1"}`} className="zy-btn-primary mt-8 inline-flex">
                Opnieuw proberen <ArrowRight size={16} />
              </Link>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
