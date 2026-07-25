import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ZyLogo } from "@/components/ZyLogo";
import {
  Home, CalendarClock, Timer, ShoppingCart, ReceiptEuro, Calculator,
  KanbanSquare, Users, Workflow, Megaphone, MessagesSquare, ShieldCheck,
  Settings, ToggleLeft, ToggleRight, Sparkles, BrainCircuit, TrendingUp, ChevronLeft, Lock, Wand2,
} from "lucide-react";

const MODULES = [
  { to: "/dashboard", label: "Dashboard", icon: Home, end: true, slug: null },
  { to: "/dashboard/planning", label: "Planning", icon: CalendarClock, slug: "planning" },
  { to: "/dashboard/time-tracking", label: "Time Tracking", icon: Timer, slug: "time_tracking" },
  { to: "/dashboard/sales", label: "Sales", icon: ShoppingCart, slug: "sales" },
  { to: "/dashboard/finance", label: "Finance & Invoicing", icon: ReceiptEuro, slug: "finance" },
  { to: "/dashboard/accounting", label: "Accounting", icon: Calculator, slug: "accounting" },
  { to: "/dashboard/projects", label: "Projects", icon: KanbanSquare, slug: "projects" },
  { to: "/dashboard/hr", label: "HR & Personnel", icon: Users, slug: "hr" },
  { to: "/dashboard/operations", label: "Operations", icon: Workflow, slug: "operations" },
  { to: "/dashboard/marketing", label: "Marketing & Content", icon: Megaphone, slug: "marketing" },
  { to: "/dashboard/ai-studio", label: "AI Studio", icon: Wand2, slug: "ai_studio" },
  { to: "/dashboard/communication", label: "Communication", icon: MessagesSquare, slug: "communication" },
  { to: "/dashboard/compliance", label: "Compliance", icon: ShieldCheck, slug: "compliance" },
];

const ASSISTANTS = [
  { to: "/dashboard/zyntha", label: "Zyntha — Content", icon: Sparkles, color: "#8B5CF6", slug: "zyntha" },
  { to: "/dashboard/thoro", label: "Thoro — Builder", icon: BrainCircuit, color: "#06B6D4", slug: "thoro" },
  { to: "/dashboard/zyona", label: "Zyona — Growth", icon: TrendingUp, color: "#D4AF37", slug: "zyona" },
];

export default function Sidebar({ user, mode, onToggleMode }) {
  const location = useLocation();
  const [open, setOpen] = useState(true);

  // Auto-collapse on small screens
  useEffect(() => {
    const fit = () => setOpen(window.innerWidth >= 1024);
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  // Founder / unlimited / billing-exempt / demo users must never see the
  // module lock icons even if the server's tier.modules list is stale.
  // Fix 2026-07-21.
  const isPrivileged = !!(
    user?.is_founder || user?.is_unlimited ||
    user?.billing_exempt || user?.is_demo
  );

  // Trial users see lock icons next to every non-AI module (mirrors the
  // backend gate in auth.py). Assistants + Settings stay unlocked.
  const isTrial = !!(user?.is_trial && user?.trial_expires_at
    && new Date(user.trial_expires_at).getTime() > Date.now());

  return (
    <>
      {/* Mobile open button */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="lg:hidden fixed top-4 left-4 z-40 p-2 rounded-md text-white"
        style={{ background: "#1A4FFF" }}
        aria-label="Toggle sidebar"
        data-testid="sidebar-toggle"
      >
        <ChevronLeft size={18} style={{ transform: open ? "rotate(0deg)" : "rotate(180deg)", transition: "transform 200ms" }} />
      </button>

      <aside
        data-testid="sidebar"
        className="fixed lg:sticky top-0 left-0 z-30 h-screen flex flex-col"
        style={{
          width: 248,
          background: "#1A4FFF",
          color: "#fff",
          transform: open ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 220ms ease",
        }}
      >
        <div className="px-5 py-5 flex items-center justify-between border-b border-white/10">
          <ZyLogo size={18} />
          {user?.is_founder && (
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded-full" style={{ background: "rgba(212,175,55,0.22)", color: "#FFD773" }}>
              Founder
            </span>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
          {MODULES.map((m) => (
            <SidebarItem
              key={m.to}
              {...m}
              allowedModules={user?.tier?.modules}
              isPrivileged={isPrivileged}
              isTrial={isTrial}
            />
          ))}

          <div className="pt-5 pb-2 px-2">
            <p className="text-[10.5px] uppercase tracking-[0.18em] text-white/55 font-semibold">AI Assistants</p>
          </div>
          {ASSISTANTS.map((a) => (
            <SidebarItem
              key={a.to}
              {...a}
              dotColor={a.color}
              allowedModules={user?.tier?.modules}
              isPrivileged={isPrivileged}
              isTrial={isTrial}
            />
          ))}

          <div className="pt-5">
            <SidebarItem to="/dashboard/team" label="Team" icon={Users} isTrial={isTrial} />
            <SidebarItem to="/dashboard/settings" label="Settings" icon={Settings} isTrial={isTrial} />
          </div>
        </nav>

        {user?.is_founder && (
          <button
            onClick={onToggleMode}
            data-testid="switch-mode"
            className="mx-3 mb-4 mt-2 px-3 py-2.5 rounded-md flex items-center gap-2 text-[13px] font-semibold border border-white/15 hover:bg-white/10"
          >
            {mode === "builder" ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
            Mode: {mode === "builder" ? "Builder" : "User"}
          </button>
        )}
      </aside>

      {open && (
        <button
          aria-label="Close sidebar"
          onClick={() => setOpen(false)}
          className="lg:hidden fixed inset-0 bg-black/40 z-20"
        />
      )}
    </>
  );
}

// AI assistants + Settings + Dashboard home are the only routes accessible
// to trial users (mirrors backend `_TRIAL_ACTIVE_EXTRA_PREFIXES` + allowed
// prefixes). Keep in sync with DashboardLayout's TRIAL_ALLOWED_ROUTES.
const TRIAL_UNLOCKED_ROUTES = new Set([
  "/dashboard",
  "/dashboard/zyntha",
  "/dashboard/thoro",
  "/dashboard/zyona",
  "/dashboard/assist",
  "/dashboard/settings",
]);

function SidebarItem({ to, label, icon: Icon, end, dotColor, slug, allowedModules, isPrivileged = false, isTrial = false }) {
  // Trial users: the sidebar lock is driven entirely by the trial
  // allowlist. We ignore the tier-based `allowedModules` check because
  // trial accounts sit on the Presale plan whose module list doesn't
  // reflect what the trial actually unlocks (AI + Settings).
  const isTrialLocked = isTrial && !TRIAL_UNLOCKED_ROUTES.has(to);
  const isTierLocked = !isTrial
    && !isPrivileged
    && slug
    && Array.isArray(allowedModules)
    && allowedModules.length > 0
    && !allowedModules.includes(slug);
  const isLocked = isTierLocked || isTrialLocked;
  return (
    <NavLink
      to={to}
      end={end}
      data-testid={`nav-${to.replace(/\//g, "-").replace(/^-/, "")}`}
      className={({ isActive }) =>
        `flex items-center gap-2.5 px-3 py-2 rounded-md text-[13.5px] font-medium transition-colors ${
          isActive ? "bg-white/15 text-white" : "text-white/85 hover:bg-white/10 hover:text-white"
        }`
      }
    >
      {dotColor ? (
        <span className="inline-flex items-center justify-center w-5 h-5 rounded" style={{ background: "rgba(255,255,255,0.12)" }}>
          <Icon size={13} style={{ color: dotColor }} />
        </span>
      ) : (
        <Icon size={16} />
      )}
      <span className="truncate flex-1">{label}</span>
      {isLocked && (
        <Lock size={11} className="shrink-0 opacity-70" data-testid={`sidebar-lock-${slug || to.replace(/\//g, "-").replace(/^-/, "")}`} />
      )}
    </NavLink>
  );
}
