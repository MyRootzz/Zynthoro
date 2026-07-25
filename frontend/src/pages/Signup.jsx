import { useMemo, useState } from "react";
import axios from "axios";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import AuthLayout from "@/components/auth/AuthLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API, formatApiError } from "@/contexts/AuthContext";
import { Eye, EyeOff } from "lucide-react";

function strengthOf(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[A-Z]/.test(pw)) s++;
  if (/[0-9]/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(s, 4);
}

export default function Signup() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("return") || "";
  const isTrial = searchParams.get("trial") === "1";
  const [form, setForm] = useState({
    first_name: "", last_name: "", email: "", password: "", company: "",
  });
  const [agreeLegal, setAgreeLegal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const strength = useMemo(() => strengthOf(form.password), [form.password]);
  const strengthLabel = ["Very weak", "Weak", "Fair", "Strong", "Excellent"][strength];
  const strengthColor = ["#dc2626", "#dc2626", "#f59e0b", "#1A4FFF", "#16a34a"][strength];

  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    if (form.password.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    if (!agreeLegal) {
      toast.error("Please accept the Terms of Service and Privacy Policy to continue.");
      return;
    }
    setSubmitting(true);
    try {
      const payload = isTrial ? { ...form, is_trial: true } : form;
      const { data } = await axios.post(`${API}/auth/signup`, payload);
      toast.success(
        isTrial
          ? "Trial account created! Check your inbox to verify your email and start the 24-hour clock."
          : "Account created. Check your inbox to verify your email."
      );
      // No email service: pass the dev token so user can verify instantly.
      const retParam = returnTo ? `&return=${encodeURIComponent(returnTo)}` : "";
      const trialParam = isTrial ? "&trial=1" : "";
      navigate(`/verify-email?token=${encodeURIComponent(data.dev_verification_token || "")}&email=${encodeURIComponent(form.email)}${retParam}${trialParam}`);
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Signup failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      eyebrow={isTrial ? "24-hour free trial" : "Create your workspace"}
      title={isTrial ? "Start your 24-hour free trial" : "Start your Zynthoro account"}
      subtitle={
        isTrial
          ? "Full AI-assistant access for 24 hours. No credit card. Cancel anytime."
          : "One platform. One AI. One truth. Founding member pricing locked for life."
      }
    >
      {isTrial && (
        <div
          data-testid="signup-trial-banner"
          className="mb-5 rounded-lg border border-[#1A4FFF]/25 bg-[#1A4FFF]/[0.06] px-4 py-3 text-[13px] text-[#0A1628] leading-relaxed"
        >
          <span className="font-semibold text-[var(--zy-blue)]">You're starting a 24h free trial.</span>{" "}
          Access all 4 AI assistants (Zyntha, Thoro, Zyona, Zynthoro Assist) — up to 10 messages per assistant per day. After 24 hours, pick a Kickstart tier to unlock the full platform.
        </div>
      )}
      <form onSubmit={onSubmit} className="space-y-4" data-testid="signup-form">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="fn" className="text-[13px] font-medium">First name</Label>
            <Input id="fn" data-testid="signup-firstname" value={form.first_name} onChange={onChange("first_name")} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ln" className="text-[13px] font-medium">Last name</Label>
            <Input id="ln" data-testid="signup-lastname" value={form.last_name} onChange={onChange("last_name")} required />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="em" className="text-[13px] font-medium">Email address</Label>
          <Input id="em" type="email" data-testid="signup-email" value={form.email} onChange={onChange("email")} required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pw" className="text-[13px] font-medium">Password</Label>
          <div className="relative">
            <Input
              id="pw"
              type={showPw ? "text" : "password"}
              data-testid="signup-password"
              value={form.password}
              onChange={onChange("password")}
              required
              minLength={8}
            />
            <button type="button" onClick={() => setShowPw((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#666]">
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {form.password && (
            <div className="mt-1.5">
              <div className="h-1.5 bg-[#eee] rounded-full overflow-hidden">
                <div
                  className="h-full transition-all"
                  style={{ width: `${(strength / 4) * 100}%`, background: strengthColor }}
                />
              </div>
              <p className="mt-1 text-[12px]" style={{ color: strengthColor }}>{strengthLabel}</p>
            </div>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="co" className="text-[13px] font-medium">Company name</Label>
          <Input id="co" data-testid="signup-company" value={form.company} onChange={onChange("company")} required />
        </div>

        <label className="flex items-start gap-2.5 cursor-pointer select-none pt-1">
          <input
            type="checkbox"
            checked={agreeLegal}
            onChange={(e) => setAgreeLegal(e.target.checked)}
            data-testid="signup-agree-legal"
            className="mt-1 w-4 h-4 rounded border-[#ccc] accent-[#1A4FFF] cursor-pointer"
            required
          />
          <span className="text-[12.5px] leading-relaxed text-[#555]">
            I agree to Zynthoro&apos;s{" "}
            <Link to="/legal/terms-of-service" target="_blank" className="text-[#1A4FFF] font-semibold underline-offset-2 hover:underline">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link to="/legal/privacy-policy" target="_blank" className="text-[#1A4FFF] font-semibold underline-offset-2 hover:underline">
              Privacy Policy
            </Link>
            .
          </span>
        </label>

        <button
          type="submit"
          data-testid="signup-submit"
          disabled={submitting || !agreeLegal}
          className="zy-btn-primary w-full mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? "Creating account…" : "Create Account"}
        </button>
        <p className="text-[13px] text-center text-[#555]">
          Already have an account?{" "}
          <Link to="/login" className="text-[#1A4FFF] font-semibold">Log in</Link>
        </p>
        <p className="text-[12px] text-center text-[#888] mt-1">
          Need help? <a href="mailto:support@zynthoro.ai" className="text-[#1A4FFF] font-medium">support@zynthoro.ai</a>
        </p>
      </form>
    </AuthLayout>
  );
}
