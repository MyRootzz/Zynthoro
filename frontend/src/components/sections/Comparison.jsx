import { Check, X, Minus } from "lucide-react";
import { HOME } from "@/constants/testIds";

const rows = [
  { feature: "All-in-one platform",         zynthoro: "yes",  sap: "no",      oracle: "no",      afas: "partial", design: "no" },
  { feature: "AI-native, built-in",         zynthoro: "yes",  sap: "no",      oracle: "partial", afas: "no",      design: "no" },
  { feature: "Starts at (€/mo)",            zynthoro: "€499", sap: "€5,000+", oracle: "€4,500+", afas: "€450+",   design: "€50+" },
  { feature: "SME-friendly setup (days)",   zynthoro: "yes",  sap: "no",      oracle: "no",      afas: "partial", design: "yes" },
  { feature: "ERP + Production included",   zynthoro: "yes",  sap: "yes",     oracle: "yes",     afas: "yes",     design: "no" },
  { feature: "Recipes, BOM, traceability",  zynthoro: "yes",  sap: "yes",     oracle: "yes",     afas: "partial", design: "no" },
  { feature: "Marketing & content built-in",zynthoro: "yes",  sap: "no",      oracle: "no",      afas: "no",      design: "yes" },
  { feature: "Voice input on AI",           zynthoro: "yes",  sap: "no",      oracle: "no",      afas: "no",      design: "no" },
  { feature: "Single source of truth",      zynthoro: "yes",  sap: "partial", oracle: "partial", afas: "yes",     design: "no" },
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
          <h2 className="zy-h2">Zynthoro vs. SAP, Oracle, AFAS &amp; the rest</h2>
          <p className="zy-body mt-5">
            One platform replacing a patchwork of legacy ERPs, CRMs and design tools.
            Real production management for a fraction of the cost.
          </p>
        </div>

        <div className="overflow-x-auto zy-reveal">
          <table className="zy-table min-w-[880px]">
            <thead>
              <tr>
                <th className="w-[24%]">Feature</th>
                <th className="zy-col-zynthoro">Zynthoro</th>
                <th>SAP</th>
                <th>Oracle NetSuite</th>
                <th>AFAS</th>
                <th>Design &amp; Video Tools</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.feature}>
                  <td className="font-medium text-[#000]">{r.feature}</td>
                  <td className="zy-col-zynthoro"><Cell value={r.zynthoro} /></td>
                  <td><Cell value={r.sap} /></td>
                  <td><Cell value={r.oracle} /></td>
                  <td><Cell value={r.afas} /></td>
                  <td><Cell value={r.design} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-center text-[12px] text-[#777]">
          Indicative starting prices — see vendor sites for current quotes. Manufacturing companies typically save €40-120k/year vs. SAP/Oracle.
        </p>
      </div>
    </section>
  );
}
