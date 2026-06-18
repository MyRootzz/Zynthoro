import { useEffect, useState } from "react";
import axios from "axios";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { toast } from "sonner";
import AuthLayout from "@/components/auth/AuthLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { Smartphone, Mail, MessageSquare, ShieldCheck, Loader2 } from "lucide-react";

export default function TwoFactorSetup() {
  const navigate = useNavigate();
  const location = useLocation();
  const { refresh } = useAuth();
  const pre_token = location.state?.pre_token;
  const [method, setMethod] = useState(null); // 'totp' | 'email'
  const [qr, setQr] = useState(null);
  const [secret, setSecret] = useState(null);
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [emailMockCode, setEmailMockCode] = useState(null);

  if (!pre_token) return <Navigate to="/login" replace />;

  const startTotp = async () => {
    setMethod("totp");
    try {
      const { data } = await axios.post(`${API}/auth/2fa/totp/setup`, { pre_token });
      setQr(data.qr_data_url);
      setSecret(data.secret);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not start TOTP setup.");
    }
  };

  const startEmail = async () => {
    setMethod("email");
    try {
      const { data } = await axios.post(`${API}/auth/2fa/email/request`, { pre_token });
      setEmailMockCode(data.dev_code || null);
      toast.success("Code sent.");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not send code.");
    }
  };

  const confirm = async (e) => {
    e?.preventDefault();
    if (code.length < 6) {
      toast.error("Enter the 6-digit code.");
      return;
    }
    setSubmitting(true);
    try {
      const endpoint = method === "totp" ? "/auth/2fa/totp/confirm" : "/auth/2fa/verify";
      await axios.post(`${API}${endpoint}`, { pre_token, method, code });
      await refresh();
      toast.success("Two-factor authentication enabled.");
      navigate("/onboarding");
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Verification failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      eyebrow="Two-factor authentication"
      title="Secure your account"
      subtitle="Choose how you'd like to receive your login codes from now on."
    >
      {!method && (
        <div className="space-y-3" data-testid="twofa-method-picker">
          <MethodCard
            icon={Smartphone}
            title="Authenticator app"
            desc="Recommended — Google Authenticator, 1Password or Authy."
            badge="Recommended"
            onClick={startTotp}
            testid="twofa-pick-totp"
          />
          <MethodCard
            icon={Mail}
            title="Email code"
            desc="We email you a 6-digit code each time you log in."
            onClick={startEmail}
            testid="twofa-pick-email"
          />
          <MethodCard
            icon={MessageSquare}
            title="SMS code"
            desc="Receive codes by text message."
            badge="Coming soon"
            disabled
            testid="twofa-pick-sms"
          />
        </div>
      )}

      {method === "totp" && (
        <div className="space-y-5">
          {!qr ? (
            <div className="flex items-center gap-2 text-[#555] text-[14px]">
              <Loader2 className="animate-spin" size={16} /> Generating QR code…
            </div>
          ) : (
            <>
              <div className="flex items-center gap-4">
                <img src={qr} alt="2FA QR" className="w-[160px] h-[160px] rounded-lg border border-[#eee]" data-testid="twofa-qr" />
                <div className="text-[13px] text-[#555] leading-relaxed">
                  <p>1. Open your authenticator app.</p>
                  <p>2. Scan this QR code.</p>
                  <p>3. Enter the 6-digit code below.</p>
                  {secret && (
                    <p className="mt-2 text-[11px] text-[#777]">
                      Or enter manually: <code className="bg-[#F4F6FB] px-1.5 py-0.5 rounded">{secret}</code>
                    </p>
                  )}
                </div>
              </div>
              <form onSubmit={confirm} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="c" className="text-[13px] font-medium">6-digit code</Label>
                  <Input
                    id="c"
                    data-testid="twofa-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    inputMode="numeric"
                    placeholder="123456"
                  />
                </div>
                <button type="submit" data-testid="twofa-confirm" disabled={submitting} className="zy-btn-primary w-full disabled:opacity-70">
                  {submitting ? "Verifying…" : "Confirm & enable 2FA"}
                </button>
              </form>
            </>
          )}
        </div>
      )}

      {method === "email" && (
        <form onSubmit={confirm} className="space-y-4">
          <div className="rounded-lg border border-[#eee] bg-[#F8F8F8] p-4 flex items-start gap-3 text-[13px] text-[#555]">
            <ShieldCheck size={16} className="mt-0.5 shrink-0" style={{ color: "#1A4FFF" }} />
            <span>
              We sent a 6-digit code to your email.
              {emailMockCode && (
                <span className="block mt-1.5 text-[12px] text-[#1A4FFF]">
                  (Email service not configured. Mock code: <b data-testid="twofa-mock-code">{emailMockCode}</b>)
                </span>
              )}
            </span>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="c" className="text-[13px] font-medium">6-digit code</Label>
            <Input
              id="c"
              data-testid="twofa-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              placeholder="123456"
            />
          </div>
          <button type="submit" data-testid="twofa-confirm" disabled={submitting} className="zy-btn-primary w-full disabled:opacity-70">
            {submitting ? "Verifying…" : "Confirm & enable 2FA"}
          </button>
        </form>
      )}
    </AuthLayout>
  );
}

function MethodCard({ icon: Icon, title, desc, badge, onClick, disabled, testid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid={testid}
      className={`w-full text-left p-4 rounded-lg border transition-all ${
        disabled
          ? "border-[#eee] opacity-60 cursor-not-allowed"
          : "border-[#eee] hover:border-[#1A4FFF] hover:shadow-[0_8px_28px_-18px_rgba(26,79,255,0.35)]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="zy-domain-icon shrink-0" style={{ width: 38, height: 38, marginBottom: 0 }}>
          <Icon size={18} />
        </span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-[14.5px] font-semibold">{title}</h3>
            {badge && (
              <span className="text-[10.5px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-full" style={{ background: "#EAF0FF", color: "#1A4FFF" }}>
                {badge}
              </span>
            )}
          </div>
          <p className="text-[13px] text-[#555] mt-1">{desc}</p>
        </div>
      </div>
    </button>
  );
}
