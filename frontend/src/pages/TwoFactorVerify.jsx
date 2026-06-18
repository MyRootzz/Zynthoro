import { useState } from "react";
import axios from "axios";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { toast } from "sonner";
import AuthLayout from "@/components/auth/AuthLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";

export default function TwoFactorVerify() {
  const navigate = useNavigate();
  const location = useLocation();
  const { refresh } = useAuth();
  const pre_token = location.state?.pre_token;
  const primary = location.state?.primary_method || "totp";
  const [method, setMethod] = useState(primary);
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [emailMock, setEmailMock] = useState(null);

  if (!pre_token) return <Navigate to="/login" replace />;

  const requestEmailCode = async () => {
    try {
      const { data } = await axios.post(`${API}/auth/2fa/email/request`, { pre_token });
      setMethod("email");
      setEmailMock(data.dev_code || null);
      toast.success("Code sent.");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail));
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await axios.post(`${API}/auth/2fa/verify`, { pre_token, method, code });
      await refresh();
      navigate("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Code rejected.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Enter your security code" subtitle="Two-factor authentication keeps your workspace safe.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="c" className="text-[13px] font-medium">
            {method === "totp" ? "Authenticator code" : "Email code"}
          </Label>
          <Input
            id="c"
            data-testid="twofa-verify-code"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            placeholder="123456"
          />
          {emailMock && (
            <p className="text-[12px] text-[#1A4FFF]">
              (Email service not configured. Mock code: <b>{emailMock}</b>)
            </p>
          )}
        </div>
        <button type="submit" data-testid="twofa-verify-submit" disabled={submitting} className="zy-btn-primary w-full disabled:opacity-70">
          {submitting ? "Verifying…" : "Verify and continue"}
        </button>
        <div className="text-center text-[13px] text-[#555]">
          {method === "totp" ? (
            <button type="button" onClick={requestEmailCode} className="text-[#1A4FFF] font-semibold">
              Use email code instead
            </button>
          ) : (
            <button type="button" onClick={() => setMethod("totp")} className="text-[#1A4FFF] font-semibold">
              Use authenticator app instead
            </button>
          )}
        </div>
      </form>
    </AuthLayout>
  );
}
