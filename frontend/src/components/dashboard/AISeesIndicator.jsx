import { Eye } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Subtle 12px line that reassures the user the AI already knows their
 * company context. Renders nothing when the profile has neither company
 * nor industry set.
 *
 * Use anywhere inside an assistant chat header.
 */
export default function AISeesIndicator({ className = "", testId = "ai-sees-indicator" }) {
  const { user } = useAuth();
  const company = (user?.company || "").trim();
  const industry = (user?.company_industry || user?.industry || "").trim();
  if (!company && !industry) return null;
  const parts = [company, industry].filter(Boolean).join(" · ");
  return (
    <p
      data-testid={testId}
      className={`text-[12px] text-[#888] flex items-center gap-1.5 ${className}`}
      title="The AI already knows your business — pulled from your profile."
    >
      <Eye size={11} className="text-[#bbb]" />
      <span>AI sees: <span className="text-[#555] font-medium">{parts}</span></span>
    </p>
  );
}
