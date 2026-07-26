/**
 * Meta OAuth callback landing page.
 *
 * Meta redirects the user's browser here after they authorize (or deny)
 * the Zynthoro app. We forward the `code` + `state` to the backend, then
 * bounce the user back to /dashboard/ai-studio with a status toast.
 *
 * Route is registered inside ProtectedRoute → DashboardLayout, so the
 * axios call inherits the JWT auth header automatically.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { API, formatApiError } from "@/contexts/AuthContext";

export default function MetaCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState({ phase: "processing", message: "Connecting Facebook & Instagram…" });
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;

    const code = params.get("code");
    const stateParam = params.get("state");
    const error = params.get("error");
    const errorDesc = params.get("error_description");

    if (error) {
      const msg = errorDesc || error || "Meta authorization was cancelled.";
      setState({ phase: "error", message: msg });
      toast.error(msg);
      setTimeout(() => navigate("/dashboard/ai-studio", { replace: true }), 2500);
      return;
    }
    if (!code || !stateParam) {
      setState({ phase: "error", message: "Missing OAuth parameters." });
      setTimeout(() => navigate("/dashboard/ai-studio", { replace: true }), 2000);
      return;
    }

    (async () => {
      try {
        const { data } = await axios.get(`${API}/oauth/meta/callback`, {
          params: { code, state: stateParam },
        });
        const pageCount = data.connected_pages || (data.pages || []).length;
        const successMsg = pageCount > 0
          ? `Connected ${pageCount} Page${pageCount === 1 ? "" : "s"}.`
          : "Meta connected (no Pages found — check your Facebook Business account).";
        setState({ phase: "success", message: successMsg });
        toast.success(successMsg);
        setTimeout(() => navigate("/dashboard/ai-studio", { replace: true }), 1500);
      } catch (e) {
        const msg = formatApiError(e?.response?.data?.detail) || "Meta connection failed.";
        setState({ phase: "error", message: msg });
        toast.error(msg);
        setTimeout(() => navigate("/dashboard/ai-studio", { replace: true }), 2500);
      }
    })();
  }, [params, navigate]);

  const Icon =
    state.phase === "success" ? CheckCircle2 :
    state.phase === "error"   ? AlertCircle    :
                                Loader2;

  const iconClass =
    state.phase === "success" ? "text-[#047857]" :
    state.phase === "error"   ? "text-[#B42318]" :
                                "text-[var(--zy-blue)] animate-spin";

  return (
    <div
      className="min-h-[60vh] flex items-center justify-center"
      data-testid="meta-callback-page"
    >
      <div className="max-w-md w-full rounded-2xl bg-white border border-[#0A162814] p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-[#F1F3F8] flex items-center justify-center">
          <Icon size={22} className={iconClass} />
        </div>
        <h1 className="text-lg font-semibold text-[#0A1628]" data-testid="meta-callback-title">
          {state.phase === "success" ? "Meta connected" :
           state.phase === "error"   ? "Connection failed" :
                                       "Connecting to Meta…"}
        </h1>
        <p className="text-[13.5px] text-[#0A1628]/65 mt-1.5" data-testid="meta-callback-message">
          {state.message}
        </p>
        <p className="text-[12px] text-[#0A1628]/45 mt-4">
          Redirecting you back to AI Studio…
        </p>
      </div>
    </div>
  );
}
