import { useEffect, useState } from "react";
import axios from "axios";
import { ArrowRight, Clock, Users } from "lucide-react";
import { HOME } from "@/constants/testIds";
import { usePresaleDialog } from "@/components/sections/PresaleDialog";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Launch: 30 June 2026, 00:00 CET (UTC+1)
const LAUNCH_TS = Date.UTC(2026, 5, 29, 23, 0, 0); // 30 Jun 00:00 CET = 29 Jun 23:00 UTC

function useCountdown(target) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const diff = Math.max(0, target - now);
  const days = Math.floor(diff / 86_400_000);
  const hours = Math.floor((diff / 3_600_000) % 24);
  const minutes = Math.floor((diff / 60_000) % 60);
  const seconds = Math.floor((diff / 1000) % 60);
  return { days, hours, minutes, seconds, done: diff === 0 };
}

export default function PresaleCTA() {
  const { openDialog } = usePresaleDialog();
  const [count, setCount] = useState(null);
  const cd = useCountdown(LAUNCH_TS);

  useEffect(() => {
    let cancelled = false;
    const fetchCount = () => {
      axios
        .get(`${API}/presale/count`)
        .then((r) => {
          if (!cancelled) setCount(r.data?.count ?? 0);
        })
        .catch(() => {
          if (!cancelled) setCount(null);
        });
    };
    fetchCount();
    const onSignup = () => fetchCount();
    window.addEventListener("zy:presale-signup", onSignup);
    return () => {
      cancelled = true;
      window.removeEventListener("zy:presale-signup", onSignup);
    };
  }, []);

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
            Launching 30 June 2026
          </div>

          <h2 className="zy-h2 mt-6 zy-reveal" style={{ color: "#fff" }}>
            Zynthoro launches 30 June 2026.
          </h2>
          <p
            className="zy-body mt-5 max-w-2xl mx-auto zy-reveal"
            style={{ color: "rgba(255,255,255,0.88)", fontSize: "1.0625rem" }}
          >
            Claim your founding member spot today. Limited presale spots available.
          </p>

          {/* Countdown */}
          <div
            className="mt-9 inline-flex items-stretch gap-2 sm:gap-3 zy-reveal"
            data-testid="presale-countdown"
            aria-label="Time remaining until launch"
          >
            {[
              { label: "Days", value: cd.days },
              { label: "Hours", value: cd.hours },
              { label: "Minutes", value: cd.minutes },
              { label: "Seconds", value: cd.seconds },
            ].map((u) => (
              <div
                key={u.label}
                className="px-3 sm:px-4 py-2.5 rounded-lg min-w-[64px] sm:min-w-[78px]"
                style={{
                  background: "rgba(255,255,255,0.10)",
                  border: "1px solid rgba(255,255,255,0.18)",
                  backdropFilter: "blur(8px)",
                }}
              >
                <div className="text-[22px] sm:text-[26px] font-bold tracking-tight" style={{ color: "#fff", fontVariantNumeric: "tabular-nums" }}>
                  {String(u.value).padStart(2, "0")}
                </div>
                <div className="text-[10px] uppercase tracking-[0.16em] font-semibold" style={{ color: "rgba(255,255,255,0.65)" }}>
                  {u.label}
                </div>
              </div>
            ))}
          </div>

          <p
            className="mt-6 text-[13px] font-semibold tracking-wide zy-reveal"
            style={{ color: "var(--zy-gold)" }}
          >
            Presale closes at launch
          </p>

          <div
            data-testid="presale-counter"
            className="mt-6 inline-flex items-center gap-3 px-5 py-3 rounded-full zy-reveal"
            style={{
              background: "rgba(255,255,255,0.12)",
              border: "1px solid rgba(255,255,255,0.22)",
              backdropFilter: "blur(8px)",
            }}
          >
            <span
              className="inline-flex items-center justify-center rounded-full"
              style={{ width: 28, height: 28, background: "rgba(212,175,55,0.22)", color: "var(--zy-gold)" }}
            >
              <Users size={15} />
            </span>
            <span className="text-[14px] font-medium" style={{ color: "rgba(255,255,255,0.92)" }}>
              <span
                className="text-[18px] font-bold"
                style={{ color: "var(--zy-gold)" }}
                data-testid="presale-counter-value"
              >
                {count === null ? "—" : count.toLocaleString("en-US")}
              </span>
              {" founding members reserved "}
              <span className="inline-flex items-center gap-1.5 text-[12px]" style={{ color: "rgba(255,255,255,0.7)" }}>
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block"
                  style={{ background: "#4ade80", boxShadow: "0 0 0 4px rgba(74,222,128,0.18)" }}
                />
                live
              </span>
            </span>
          </div>

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
