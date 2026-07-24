import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import { CookieSettingsProvider } from "@/components/CookieSettings";
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
import SubscribeBeta from "@/pages/SubscribeBeta";
import SubscribeTier from "@/pages/SubscribeTier";
import SubscribeReturn from "@/pages/SubscribeReturn";
import DashboardLayout from "@/pages/DashboardLayout";
import DashboardHome from "@/pages/dashboard/DashboardHome";
import ModulePlaceholder from "@/pages/dashboard/ModulePlaceholder";
import HRModule from "@/pages/dashboard/HRModule";
import AccountingModule from "@/pages/dashboard/AccountingModule";
import CommunicationModule from "@/pages/dashboard/CommunicationModule";
import ComplianceModule from "@/pages/dashboard/ComplianceModule";
import FinanceModule from "@/pages/dashboard/FinanceModule";
import SalesModule from "@/pages/dashboard/SalesModule";
import ProjectsModule from "@/pages/dashboard/ProjectsModule";
import PlanningModule from "@/pages/dashboard/PlanningModule";
import TimeTrackingModule from "@/pages/dashboard/TimeTrackingModule";
import TeamPage from "@/pages/dashboard/Team";
import Settings from "@/pages/dashboard/Settings";
import AssistantPage from "@/pages/dashboard/AssistantPage";
import MarketingContent from "@/pages/dashboard/MarketingContent";
import PrivacyPolicy from "@/pages/legal/PrivacyPolicy";
import TermsOfService from "@/pages/legal/TermsOfService";
import CookiePolicy from "@/pages/legal/CookiePolicy";
import DPA from "@/pages/legal/DPA";
import SLA from "@/pages/legal/SLA";
import BlogIndex from "@/pages/blog/BlogIndex";
import BlogPost from "@/pages/blog/BlogPost";

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <CookieSettingsProvider>
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
            <Route path="/subscribe/beta" element={<SubscribeBeta />} />
            <Route path="/subscribe/return" element={<SubscribeReturn />} />
            <Route path="/subscribe/:tierKey" element={<SubscribeTier />} />
            <Route path="/legal/privacy-policy" element={<PrivacyPolicy />} />
            <Route path="/legal/terms-of-service" element={<TermsOfService />} />
            <Route path="/legal/cookie-policy" element={<CookiePolicy />} />
            <Route path="/legal/dpa" element={<DPA />} />
            <Route path="/legal/sla" element={<SLA />} />
            {/* Backwards-compatible redirects for the earlier short URLs */}
            <Route path="/legal/privacy" element={<Navigate to="/legal/privacy-policy" replace />} />
            <Route path="/legal/terms" element={<Navigate to="/legal/terms-of-service" replace />} />
            <Route path="/legal/cookies" element={<Navigate to="/legal/cookie-policy" replace />} />

            {/* Blog (public — articles ingested from Outrank webhook) */}
            <Route path="/blog" element={<BlogIndex />} />
            <Route path="/blog/:slug" element={<BlogPost />} />
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
              <Route path="marketing" element={<MarketingContent />} />
              <Route path="hr" element={<HRModule />} />
              <Route path="accounting" element={<AccountingModule />} />
              <Route path="communication" element={<CommunicationModule />} />
              <Route path="compliance" element={<ComplianceModule />} />
              <Route path="finance" element={<FinanceModule />} />
              <Route path="sales" element={<SalesModule />} />
              <Route path="projects" element={<ProjectsModule />} />
              <Route path="planning" element={<PlanningModule />} />
              <Route path="time-tracking" element={<TimeTrackingModule />} />
              <Route path=":slug" element={<ModulePlaceholder />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-center" />
        </CookieSettingsProvider>
      </AuthProvider>
    </div>
  );
}

export default App;
