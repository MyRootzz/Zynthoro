/**
 * Two side-by-side comparison tables (Fix 12):
 *   Table 1 — Tool replacement per category vs. Zynthoro plan
 *   Table 2 — Plan vs. market savings
 *
 * White background, blue (#1A4FFF) headers, gold (#D4AF37) Enterprise row.
 * Mobile responsive (stacked cards on small screens, true tables on lg+).
 */

const REPLACEMENT_ROWS = [
  { category: "Design & Photo Tools", market: "€15-50/month", from: "Creator" },
  { category: "Video Editing Tools", market: "€20-50/month", from: "Creator" },
  { category: "Social Media Scheduler", market: "€50-200/month", from: "Starter (basic) / Creator (full)" },
  { category: "Email Marketing Platform", market: "€30-300/month", from: "Business" },
  { category: "CRM & Lead Scoring", market: "€50-800/month", from: "Business" },
  { category: "Project Management", market: "€10-50/month", from: "Agency" },
  { category: "Accounting & Invoicing", market: "€30-150/month", from: "Business" },
  { category: "HR & Payroll Platform", market: "€50-200/month", from: "Enterprise" },
  { category: "Team Communication", market: "€8-15/user/month", from: "All plans" },
  { category: "Document Management", market: "€10-30/month", from: "All plans" },
  { category: "Workflow Automation", market: "€20-100/month", from: "Business" },
  { category: "Marketing Funnels", market: "€50-300/month", from: "Creator" },
  { category: "Mobile App / Cross-device", market: "€0-15/month extra", from: "All plans" },
];

const SAVINGS_ROWS = [
  { plan: "Starter",    market: "€100 - €200/month",     zynthoro: "€499/month",        save: "Growing investment — foundation for scale" },
  { plan: "Creator",    market: "€300 - €600/month",     zynthoro: "€699/month",        save: "Up to €-300/month" },
  { plan: "Business",   market: "€600 - €1.500/month",   zynthoro: "€899/month",        save: "Up to €600/month" },
  { plan: "Agency",     market: "€1.500 - €3.000/month", zynthoro: "€1.199/month",      save: "Up to €1.800/month" },
  { plan: "Enterprise", market: "€10.000 - €35.000/mo",  zynthoro: "from €2,499/month", save: "Up to €32.500/month" },
];

function tierAccent(name) {
  if (name === "Enterprise" || name?.startsWith("Enterprise")) return { row: "rgba(212,175,55,0.10)", chip: "#D4AF37", chipFg: "#5a4a0e" };
  if (name === "Creator") return { row: "transparent", chip: "#1A4FFF", chipFg: "#fff" };
  if (name === "Business") return { row: "transparent", chip: "#1A4FFF", chipFg: "#fff" };
  if (name === "Agency") return { row: "transparent", chip: "#1A4FFF", chipFg: "#fff" };
  return { row: "transparent", chip: "#EAF0FF", chipFg: "#1A4FFF" };
}

export default function PricingComparisonTables() {
  return (
    <section
      data-testid="pricing-comparison-tables"
      className="zy-section"
      style={{ background: "#ffffff" }}
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-12">
          <p className="zy-eyebrow mb-3">The math is unmissable</p>
          <h2 className="zy-h2">What Zynthoro replaces — and what you save</h2>
          <p className="zy-body mt-4">
            Two simple tables. One shows the tools we replace. The other shows what your
            current stack costs vs. what Zynthoro costs.
          </p>
        </div>

        {/* TABLE 1 — Tool replacement */}
        <div className="mb-16">
          <h3 className="text-[14px] font-bold tracking-[0.18em] uppercase text-[#1A4FFF] mb-4">
            01 · Tool replacement
          </h3>

          {/* Desktop table */}
          <div className="hidden md:block bg-white border border-[#eee] rounded-2xl overflow-hidden">
            <table className="w-full" data-testid="pricing-table-replacement">
              <thead>
                <tr style={{ background: "#1A4FFF", color: "#fff" }}>
                  <th className="text-left px-5 py-3.5 text-[12.5px] font-semibold tracking-wide uppercase">What you replace</th>
                  <th className="text-left px-5 py-3.5 text-[12.5px] font-semibold tracking-wide uppercase">Cost without Zynthoro</th>
                  <th className="text-left px-5 py-3.5 text-[12.5px] font-semibold tracking-wide uppercase">Included from</th>
                </tr>
              </thead>
              <tbody>
                {REPLACEMENT_ROWS.map((r, i) => (
                  <tr key={r.category} className={i % 2 ? "bg-[#FAFAFB]" : "bg-white"}>
                    <td className="px-5 py-3 text-[14px] font-medium text-black">{r.category}</td>
                    <td className="px-5 py-3 text-[14px] text-[#444]">{r.market}</td>
                    <td className="px-5 py-3 text-[13.5px] font-semibold" style={{ color: "#1A4FFF" }}>{r.from}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {REPLACEMENT_ROWS.map((r) => (
              <div key={r.category} className="bg-white border border-[#eee] rounded-xl p-4">
                <p className="text-[14px] font-semibold text-black">{r.category}</p>
                <div className="flex justify-between items-end mt-2 gap-3">
                  <p className="text-[12.5px] text-[#666]">{r.market}</p>
                  <p className="text-[12px] font-bold uppercase tracking-wider text-[#1A4FFF] text-right">{r.from}</p>
                </div>
              </div>
            ))}
          </div>

          <p className="mt-3 text-[11.5px] text-[#888]">
            Generic category names — no brand mentions. Market prices are typical SaaS ranges in 2026.
          </p>
        </div>

        {/* TABLE 2 — Plan vs market savings */}
        <div>
          <h3 className="text-[14px] font-bold tracking-[0.18em] uppercase text-[#1A4FFF] mb-4">
            02 · Plan vs. market
          </h3>

          {/* Desktop table */}
          <div className="hidden md:block bg-white border border-[#eee] rounded-2xl overflow-hidden">
            <table className="w-full" data-testid="pricing-table-savings">
              <thead>
                <tr style={{ background: "#1A4FFF", color: "#fff" }}>
                  <th className="text-left px-5 py-3.5 text-[12.5px] font-semibold tracking-wide uppercase">Plan</th>
                  <th className="text-left px-5 py-3.5 text-[12.5px] font-semibold tracking-wide uppercase">Pay separately</th>
                  <th className="text-left px-5 py-3.5 text-[12.5px] font-semibold tracking-wide uppercase">Zynthoro price</th>
                  <th className="text-left px-5 py-3.5 text-[12.5px] font-semibold tracking-wide uppercase">You save</th>
                </tr>
              </thead>
              <tbody>
                {SAVINGS_ROWS.map((r, i) => {
                  const acc = tierAccent(r.plan);
                  return (
                    <tr
                      key={r.plan}
                      style={{ background: acc.row || (i % 2 ? "#FAFAFB" : "#fff") }}
                    >
                      <td className="px-5 py-3">
                        <span
                          className="inline-flex items-center text-[12px] font-bold uppercase tracking-wider px-2 py-1 rounded-full"
                          style={{ background: acc.chip, color: acc.chipFg }}
                        >
                          {r.plan}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-[14px] text-[#444]">{r.market}</td>
                      <td className="px-5 py-3 text-[14px] font-semibold text-black">{r.zynthoro}</td>
                      <td className="px-5 py-3 text-[13.5px] font-semibold text-[#1A4FFF]">{r.save}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {SAVINGS_ROWS.map((r) => {
              const acc = tierAccent(r.plan);
              return (
                <div
                  key={r.plan}
                  className="border border-[#eee] rounded-xl p-4"
                  style={{ background: acc.row || "#fff" }}
                >
                  <span
                    className="inline-flex items-center text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full"
                    style={{ background: acc.chip, color: acc.chipFg }}
                  >
                    {r.plan}
                  </span>
                  <div className="grid grid-cols-2 gap-2 mt-3 text-[13px]">
                    <div>
                      <p className="text-[10.5px] uppercase text-[#888] tracking-wider">Pay separately</p>
                      <p className="text-[#444]">{r.market}</p>
                    </div>
                    <div>
                      <p className="text-[10.5px] uppercase text-[#888] tracking-wider">Zynthoro</p>
                      <p className="font-semibold text-black">{r.zynthoro}</p>
                    </div>
                  </div>
                  <p className="mt-3 text-[12.5px] font-semibold text-[#1A4FFF]">{r.save}</p>
                </div>
              );
            })}
          </div>

          <p className="mt-3 text-[12.5px] text-[#555] italic">
            * <b>Starter is your foundation</b> — start lean, scale smart. The real savings begin at Creator.
          </p>
        </div>
      </div>
    </section>
  );
}
