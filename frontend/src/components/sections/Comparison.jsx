import { Check, X, Minus } from "lucide-react";
import { HOME } from "@/constants/testIds";

const rows = [
  { feature: "All-in-one platform", zynthoro: "yes", erp: "no", crm: "no", design: "no" },
  { feature: "AI-native, built-in", zynthoro: "yes", erp: "no", crm: "partial", design: "no" },
  { feature: "Starts at (€/mo)", zynthoro: "€499", erp: "€5,000+", crm: "€800+", design: "€50+" },
  { feature: "SME-friendly setup", zynthoro: "yes", erp: "no", crm: "partial", design: "yes" },
  { feature: "ERP included", zynthoro: "yes", erp: "yes", crm: "no", design: "no" },
  { feature: "Marketing & content built-in", zynthoro: "yes", erp: "no", crm: "yes", design: "yes" },
  { feature: "Single source of truth", zynthoro: "yes", erp: "partial", crm: "no", design: "no" },
];

function Cell({ value }) {
  if (value === "yes")
    return <Check size={18} style={{ color: "var(--zy-blue)" }} aria-label="Yes" />;
  if (value === "no") return <X size={18} className="text-[#bbb]" aria-label="No" />;
  if (value === "partial")
    return <Minus size={18} style={{ color: "#9aa3b2" }} aria-label="Partial" />;
  return <span className="text-[14px] text-[#333] font-medium">{value}</span>;
}

export default function Comparison() {
  return (
    <section
      data-testid={HOME.comparison}
      className="zy-section"
      style={{ background: "var(--zy-grey-light)" }}
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-14 zy-reveal">
          <p className="zy-eyebrow mb-4">Comparison</p>
          <h2 className="zy-h2">Zynthoro vs. the old way</h2>
          <p className="zy-body mt-5">
            One platform replacing a patchwork of category-specific tools.
          </p>
        </div>

        <div className="overflow-x-auto zy-reveal">
          <table className="zy-table min-w-[760px]">
            <thead>
              <tr>
                <th className="w-[28%]">Feature</th>
                <th className="zy-col-zynthoro">Zynthoro</th>
                <th>Traditional ERP Systems</th>
                <th>CRM &amp; Marketing Platforms</th>
                <th>Design &amp; Video Tools</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.feature}>
                  <td className="font-medium text-[#000]">{r.feature}</td>
                  <td className="zy-col-zynthoro"><Cell value={r.zynthoro} /></td>
                  <td><Cell value={r.erp} /></td>
                  <td><Cell value={r.crm} /></td>
                  <td><Cell value={r.design} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-center text-[12px] text-[#777]">
          Comparison categories represent typical tools in each segment.
        </p>
      </div>
    </section>
  );
}
