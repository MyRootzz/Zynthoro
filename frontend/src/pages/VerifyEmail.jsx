import { useEffect, useState } from "react";
import axios from "axios";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import AuthLayout from "@/components/auth/AuthLayout";
import { API, formatApiError } from "@/contexts/AuthContext";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const returnTo = params.get("return") || "/login";
  const [state, setState] = useState("verifying"); // verifying | ok | error
  const [msg, setMsg] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("error");
      setMsg("Missing verification token.");
      return;
    }
    (async () => {
      try {
        const { data } = await axios.get(`${API}/auth/verify-email`, { params: { token } });
        setState("ok");
        setMsg(data.message);
      } catch (e) {
        setState("error");
        setMsg(formatApiError(e?.response?.data?.detail) || "Verification failed.");
      }
    })();
  }, [params]);

  return (
    <AuthLayout title={state === "ok" ? "Email verified" : "Verifying your email"} subtitle={msg}>
      <div className="flex flex-col items-center text-center gap-5 mt-2">
        {state === "verifying" && <Loader2 size={36} className="animate-spin" style={{ color: "#1A4FFF" }} />}
        {state === "ok" && (
          <>
            <CheckCircle2 size={48} style={{ color: "#16a34a" }} />
            <button onClick={() => navigate(returnTo)} className="zy-btn-primary" data-testid="goto-login">
              Continue
            </button>
          </>
        )}
        {state === "error" && (
          <>
            <XCircle size={48} style={{ color: "#dc2626" }} />
            <Link to="/signup" className="zy-link">Back to signup</Link>
          </>
        )}
      </div>
    </AuthLayout>
  );
}
