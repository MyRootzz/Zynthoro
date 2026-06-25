import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import Home from "@/pages/Home";
import Signup from "@/pages/Signup";
import Login from "@/pages/Login";
import VerifyEmail from "@/pages/VerifyEmail";
import TwoFactorSetup from "@/pages/TwoFactorSetup";
import TwoFactorVerify from "@/pages/TwoFactorVerify";
import Onboarding from "@/pages/Onboarding";
import SubscribeStarter from "@/pages/SubscribeStarter";
import SubscribeStarterReturn from "@/pages/SubscribeStarterReturn";
import DashboardLayout from "@/pages/DashboardLayout";
import DashboardHome from "@/pages/dashboard/DashboardHome";
import ModulePlaceholder from "@/pages/dashboard/ModulePlaceholder";
import TeamPage from "@/pages/dashboard/Team";
import Settings from "@/pages/dashboard/Settings";
import AssistantPage from "@/pages/dashboard/AssistantPage";

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/login" element={<Login />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/2fa/setup" element={<TwoFactorSetup />} />
            <Route path="/2fa/verify" element={<TwoFactorVerify />} />
            <Route path="/subscribe/starter" element={<SubscribeStarter />} />
            <Route path="/subscribe/starter/return" element={<SubscribeStarterReturn />} />
            <Route
              path="/onboarding"
              element={
                <ProtectedRoute>
                  <Onboarding />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<DashboardHome />} />
              <Route path="team" element={<TeamPage />} />
              <Route path="settings" element={<Settings />} />
              <Route path="zyntha" element={<AssistantPage assistantKey="zyntha" />} />
              <Route path="thoro" element={<AssistantPage assistantKey="thoro" />} />
              <Route path="zyona" element={<AssistantPage assistantKey="zyona" />} />
              <Route path=":slug" element={<ModulePlaceholder />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </div>
  );
}

export default App;
