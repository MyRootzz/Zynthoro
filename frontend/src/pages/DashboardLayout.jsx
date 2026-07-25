import { Outlet, useLocation } from "react-router-dom";
import { useMemo, useState } from "react";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import AssistFloating from "@/components/dashboard/AssistFloating";
import BuilderModePanel from "@/components/dashboard/BuilderModePanel";
import JuryTour from "@/components/dashboard/JuryTour";
import TrialBanner from "@/components/dashboard/TrialBanner";
import TrialExpiredGate from "@/components/dashboard/TrialExpiredGate";
import LockedModule from "@/components/dashboard/LockedModule";
import { useAuth } from "@/contexts/AuthContext";

// Routes accessible to trial users while their 24-hour trial is active.
// Everything else renders <LockedModule /> in place of the real page.
const TRIAL_ALLOWED_ROUTES = new Set([
  "/dashboard",
  "/dashboard/",
  "/dashboard/zyntha",
  "/dashboard/thoro",
  "/dashboard/zyona",
  "/dashboard/assist",
  "/dashboard/settings",
]);

// Pretty labels for the locked-module screen.
const MODULE_LABELS = {
  "/dashboard/hr": "HR",
  "/dashboard/accounting": "Accounting",
  "/dashboard/communication": "Communication",
  "/dashboard/compliance": "Compliance",
  "/dashboard/finance": "Finance & Invoicing",
  "/dashboard/sales": "Sales",
  "/dashboard/projects": "Projects",
  "/dashboard/planning": "Planning",
  "/dashboard/time-tracking": "Time Tracking",
  "/dashboard/operations": "Operations",
  "/dashboard/canva-studio": "Canva Studio",
  "/dashboard/marketing": "Marketing & Content",
  "/dashboard/team": "Team",
};

function trialState(user) {
  if (!user?.is_trial) return "not_trial";
  const exp = user.trial_expires_at;
  if (!exp) return "expired";
  const end = new Date(exp).getTime();
  if (Number.isNaN(end)) return "expired";
  return Date.now() < end ? "active" : "expired";
}

export default function DashboardLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const [mode, setMode] = useState("user");
  const builder = mode === "builder" && user?.is_founder;

  const tState = useMemo(() => trialState(user), [user]);

  // Hard-block: trial has run out. Replace the whole dashboard with the
  // expired gate — no sidebar, no topbar, no accidentally-lingering
  // module content.
  if (tState === "expired") {
    return <TrialExpiredGate />;
  }

  const isTrialActive = tState === "active";
  const pathname = location.pathname.replace(/\/+$/, "") || "/dashboard";
  const isAllowedForTrial = TRIAL_ALLOWED_ROUTES.has(pathname) || TRIAL_ALLOWED_ROUTES.has(pathname + "/");
  const showLockedModule = isTrialActive && !isAllowedForTrial;

  return (
    <div className="min-h-screen flex flex-col bg-[#FAFAFB]">
      {isTrialActive && <TrialBanner user={user} />}
      <div className="flex-1 flex min-h-0">
        <Sidebar
          user={user}
          mode={mode}
          onToggleMode={() => setMode((m) => (m === "user" ? "builder" : "user"))}
        />
        <div className="flex-1 min-w-0 flex flex-col">
          <TopBar />
          <main
            className="flex-1 px-3 sm:px-6 lg:px-8 py-6 sm:py-8"
            data-testid="dashboard-main"
          >
            {showLockedModule ? (
              <LockedModule moduleName={MODULE_LABELS[pathname]} />
            ) : (
              <Outlet context={{ mode }} />
            )}
            {builder && <BuilderModePanel />}
          </main>
        </div>
        <AssistFloating />
        <JuryTour />
      </div>
    </div>
  );
}
