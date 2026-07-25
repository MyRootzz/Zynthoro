import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Clock, ArrowRight, Sparkles } from "lucide-react";

// Sticky trial countdown strip shown at the top of the dashboard when the
// authenticated user is on the 24-hour free trial and it has not yet
// expired. Renders `null` for non-trial and expired-trial users (the
// TrialExpiredGate handles the expired case).
export default function TrialBanner({ user }) {
  const expiresAt = user?.trial_expires_at;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!expiresAt) return undefined;
    const t = setInterval(() => setNow(Date.now()), 60_000); // tick each minute
    return () => clearInterval(t);
  }, [expiresAt]);

  const remaining = useMemo(() => {
    if (!expiresAt) return null;
    const end = new Date(expiresAt).getTime();
    const diff = end - now;
    if (diff <= 0) return { expired: true };
    const hours = Math.floor(diff / (60 * 60 * 1000));
    const mins = Math.floor((diff % (60 * 60 * 1000)) / (60 * 1000));
    return { expired: false, hours, mins };
  }, [expiresAt, now]);

  if (!user?.is_trial || !remaining || remaining.expired) return null;

  const label =
    remaining.hours > 0
      ? `${remaining.hours}h ${remaining.mins}m left in your free trial`
      : `${remaining.mins}m left in your free trial`;

  return (
    <div
      data-testid="trial-banner"
      className="w-full text-white text-[13.5px]"
      style={{
        background: "linear-gradient(90deg, #1A4FFF 0%, #3E68FF 100%)",
      }}
    >
      <div className="px-4 sm:px-6 lg:px-8 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <Sparkles size={15} className="shrink-0" />
          <span className="font-semibold truncate">Free trial active</span>
          <span className="text-white/85 hidden sm:inline">·</span>
          <span className="inline-flex items-center gap-1.5 text-white/95">
            <Clock size={14} />
            {label}
          </span>
        </div>
        <Link
          to="/#kickstart"
          data-testid="trial-banner-upgrade"
          className="inline-flex items-center gap-1.5 rounded-full bg-white text-[var(--zy-blue)] px-3.5 py-1.5 text-[12.5px] font-semibold hover:bg-white/95 transition-colors"
        >
          Upgrade now <ArrowRight size={13} />
        </Link>
      </div>
    </div>
  );
}
