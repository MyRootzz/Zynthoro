import { useState } from "react";
import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import AuthLayout from "@/components/auth/AuthLayout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [submitting, setSubmitting] = useState(false);
  const onChange = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const { data } = await axios.post(`${API}/auth/login`, form);
      if (data.stage === "2fa_setup_required") {
        navigate("/2fa/setup", { state: { pre_token: data.pre_token, email: form.email } });
      } else if (data.stage === "2fa_required") {
        navigate("/2fa/verify", {
          state: {
            pre_token: data.pre_token,
            email: form.email,
            available_methods: data.available_methods,
            primary_method: data.twofa_method,
          },
        });
      } else {
        await refresh();
        navigate("/dashboard");
      }
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Login failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to your Zynthoro workspace.">
      <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
        <div className="space-y-1.5">
          <Label htmlFor="em" className="text-[13px] font-medium">Email address</Label>
          <Input id="em" type="email" data-testid="login-email" value={form.email} onChange={onChange("email")} required />
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="pw" className="text-[13px] font-medium">Password</Label>
            <Link to="/forgot-password" className="text-[12.5px] text-[#1A4FFF] font-medium">Forgot password?</Link>
          </div>
          <Input id="pw" type="password" data-testid="login-password" value={form.password} onChange={onChange("password")} required />
        </div>

        <button type="submit" data-testid="login-submit" disabled={submitting} className="zy-btn-primary w-full disabled:opacity-70">
          {submitting ? "Logging in…" : "Log In"}
        </button>

        <p className="text-[13px] text-center text-[#555]">
          Don&apos;t have an account?{" "}
          <Link to="/signup" className="text-[#1A4FFF] font-semibold">Sign up</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
