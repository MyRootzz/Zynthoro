import { Outlet, useLocation } from "react-router-dom";
import { useState } from "react";
import Sidebar from "@/components/dashboard/Sidebar";
import TopBar from "@/components/dashboard/TopBar";
import AssistFloating from "@/components/dashboard/AssistFloating";
import BuilderModePanel from "@/components/dashboard/BuilderModePanel";
import { useAuth } from "@/contexts/AuthContext";

export default function DashboardLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const [mode, setMode] = useState("user");
  const builder = mode === "builder" && user?.is_founder;

  return (
    <div className="min-h-screen flex bg-[#FAFAFB]">
      <Sidebar
        user={user}
        mode={mode}
        onToggleMode={() => setMode((m) => (m === "user" ? "builder" : "user"))}
      />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar />
        <main className="flex-1 px-3 sm:px-6 lg:px-8 py-6 sm:py-8" data-testid="dashboard-main">
          <Outlet context={{ mode }} />
          {builder && <BuilderModePanel />}
        </main>
      </div>
      <AssistFloating />
    </div>
  );
}
