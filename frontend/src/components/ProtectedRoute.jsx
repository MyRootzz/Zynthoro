import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export default function ProtectedRoute({ children, founderOnly = false }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-[#666] text-[14px]">Loading…</div>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  // Presale users skip onboarding entirely — straight to dashboard.
  const isPresale = (user.subscription_plan || "").toLowerCase() === "presale";
  // Force onboarding only when not yet completed AND user is on a paid plan.
  if (!user.onboarding_completed && !isPresale && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }
  // Already onboarded? Don't show /onboarding again on direct navigation.
  if ((user.onboarding_completed || isPresale) && location.pathname === "/onboarding") {
    return <Navigate to="/dashboard" replace />;
  }
  if (founderOnly && !user.is_founder) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}
