import { useParams } from "react-router-dom";
import { Construction } from "lucide-react";

const TITLES = {
  planning: "Planning & Organisation",
  "time-tracking": "Time Tracking",
  sales: "Sales",
  finance: "Finance & Invoicing",
  accounting: "Accounting",
  projects: "Projects",
  hr: "HR & Personnel",
  operations: "Operations",
  marketing: "Marketing & Content",
  communication: "Communication & Collaboration",
  compliance: "Compliance & Security",
  settings: "Settings",
};

export default function ModulePlaceholder() {
  const { slug } = useParams();
  const title = TITLES[slug] || "Module";

  return (
    <div className="max-w-2xl">
      <p className="zy-eyebrow mb-3">Module</p>
      <h1 className="text-[28px] font-bold tracking-tight">{title}</h1>
      <div className="mt-8 bg-white border border-[#eee] rounded-xl p-8 text-center">
        <span className="zy-domain-icon mx-auto" style={{ width: 48, height: 48 }}>
          <Construction size={20} />
        </span>
        <h2 className="text-[16px] font-semibold mt-4">Coming in Phase 3</h2>
        <p className="text-[13.5px] text-[#666] mt-2 max-w-md mx-auto">
          The full {title} workspace is being built. In the meantime ask Zynthoro Assist (bottom right)
          any question about this module — it will help you get started.
        </p>
      </div>
    </div>
  );
}
