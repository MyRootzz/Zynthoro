import { Check, X, Minus } from "lucide-react";
import { HOME } from "@/constants/testIds";

const rows = [
  { feature: "All-in-one", zynthoro: "yes", sap: "no", hubspot: "no", canva: "no" },
  { feature: "AI-native", zynthoro: "yes", sap: "no", hubspot: "partial", canva: "no" },
  { feature: "Price / month", zynthoro: "€499+", sap: "€5,000+", hubspot: "€800+", canva: "€50+" },
  { feature: "SME-friendly", zynthoro: "yes", sap: "no", hubspot: "partial", canva: "yes" },
  { feature: "ERP included", zynthoro: "yes", sap: "yes", hubspot: "no", canva: "no" },
];

function Cell({ value }) {
  if (value === "yes")
    return <Check size={18} style={{ color: "var(--zy-blue)" }} />;
  if (value === "no") return <X size={18} className="text-[#bbb]" />;
  if (value === "partial")
    return <Minus size={18} style={{ color: "#9aa3b2" }} />;
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
        </div>

        <div className="overflow-x-auto zy-reveal">
          <table className="zy-table min-w-[720px]">
            <thead>
              <tr>
                <th className="w-[28%]">Feature</th>
                <th className="zy-col-zynthoro">Zynthoro</th>
                <th>SAP / Oracle</th>
                <th>HubSpot</th>
                <th>Canva + CapCut</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.feature}>
                  <td className="font-medium text-[#000]">{r.feature}</td>
                  <td className="zy-col-zynthoro"><Cell value={r.zynthoro} /></td>
                  <td><Cell value={r.sap} /></td>
                  <td><Cell value={r.hubspot} /></td>
                  <td><Cell value={r.canva} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
