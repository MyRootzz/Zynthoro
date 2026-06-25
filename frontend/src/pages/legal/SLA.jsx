import LegalLayout from "@/components/legal/LegalLayout";
import { LegalSection, LegalList } from "@/components/legal/LegalSection";

const SLA_TIERS = [
  { plan: "Starter", uptime: "99.5%", support: "Email, 24h response", credits: "Up to 10%" },
  { plan: "Growth", uptime: "99.9%", support: "Email + chat, 8h response", credits: "Up to 25%" },
  { plan: "Scale", uptime: "99.95%", support: "Priority chat, 4h response", credits: "Up to 50%" },
  { plan: "Enterprise", uptime: "99.99%", support: "Dedicated CSM, 1h response, 24/7 phone", credits: "Up to 100%" },
];

export default function SLA() {
  return (
    <LegalLayout
      title="Service Level Agreement"
      lastUpdated="February 5, 2026"
      current="sla"
    >
      <p className="text-[16px] text-black/80 mb-10 leading-[1.8]">
        This Service Level Agreement ("SLA") describes the uptime, support and
        service-credit commitments Zynthoro makes for paying customers. It is
        incorporated into the Zynthoro Terms of Service.
      </p>

      <LegalSection id="commitment" number="1" title="Uptime commitment by plan">
        <div className="overflow-hidden border border-black/10 rounded-md mt-2">
          <table className="w-full text-[14px]">
            <thead className="bg-[#0A1628] text-white">
              <tr>
                <th className="text-left p-3 font-semibold">Plan</th>
                <th className="text-left p-3 font-semibold">Monthly Uptime</th>
                <th className="text-left p-3 font-semibold">Support</th>
                <th className="text-left p-3 font-semibold">Max Credits</th>
              </tr>
            </thead>
            <tbody>
              {SLA_TIERS.map((t, i) => (
                <tr
                  key={t.plan}
                  className={i % 2 === 0 ? "bg-white" : "bg-black/[0.02]"}
                >
                  <td className="p-3 font-semibold text-[var(--zy-blue)]">{t.plan}</td>
                  <td className="p-3">{t.uptime}</td>
                  <td className="p-3">{t.support}</td>
                  <td className="p-3">{t.credits}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </LegalSection>

      <LegalSection id="definition" number="2" title="How we measure uptime">
        <p>
          "Monthly Uptime Percentage" = (Total minutes in month − Downtime
          minutes) / Total minutes in month. Downtime is measured by Zynthoro's
          external monitoring (Pingdom / UptimeRobot) across the EU and US
          regions and excludes Scheduled Maintenance and Excluded Events.
        </p>
      </LegalSection>

      <LegalSection id="excluded" number="3" title="Excluded events">
        <p>The following are not counted as downtime:</p>
        <LegalList
          items={[
            "Scheduled maintenance announced at least 72 hours in advance (max 4 hours per month, between 22:00–04:00 CET on Sundays).",
            "Force majeure (war, natural disaster, large-scale internet outages).",
            "Misuse, abuse, prohibited content or DDoS originating from Customer's network.",
            "Issues caused by Customer-owned integrations, browser extensions or VPNs.",
            "Sub-processor outages outside Zynthoro's reasonable control (Stripe, Anthropic, Google, AWS) — subject to good-faith mitigation by Zynthoro.",
          ]}
        />
      </LegalSection>

      <LegalSection id="credits" number="4" title="Service credits">
        <p>
          If Zynthoro fails to meet the monthly uptime commitment for your
          plan, you may request a service credit applied to a future invoice:
        </p>
        <LegalList
          items={[
            "Below committed uptime but ≥ 99.0% → 10% credit of monthly fee.",
            "Below 99.0% but ≥ 95.0% → 25% credit.",
            "Below 95.0% but ≥ 90.0% → 50% credit.",
            "Below 90.0% → 100% credit (Enterprise) / 50% credit (other plans).",
          ]}
        />
        <p className="mt-4">
          Credits are the Customer's sole and exclusive remedy for any SLA
          breach. To claim, email{" "}
          <a className="text-[var(--zy-blue)] font-semibold" href="mailto:info@zynthoro.ai">
            info@zynthoro.ai
          </a>{" "}
          within 30 days of the affected month with the affected dates and
          times.
        </p>
      </LegalSection>

      <LegalSection id="support" number="5" title="Support response times">
        <p>Response times count business hours unless otherwise noted:</p>
        <LegalList
          items={[
            "Critical (Severity 1, full outage): 1h on Enterprise, 4h on Scale, 8h on Growth, 24h on Starter.",
            "High (Severity 2, major feature broken): 4h / 8h / 1bd / 2bd.",
            "Normal (Severity 3, minor bug or question): 1bd / 2bd / 3bd / 5bd.",
            "Low (Severity 4, cosmetic / how-to): 3bd / 5bd / 5bd / best-effort.",
          ]}
        />
      </LegalSection>

      <LegalSection id="status" number="6" title="Status page & comms">
        <p>
          Real-time platform status is published at{" "}
          <span className="font-semibold">status.zynthoro.ai</span>. For
          incidents above Severity 2 we post an initial update within 15
          minutes and a written post-mortem within 5 business days.
        </p>
      </LegalSection>

      <LegalSection id="contact" number="7" title="Contact">
        <p>
          Casa Haya International BV (KvK 99196581) — Operational incidents and
          Enterprise escalations:{" "}
          <a className="text-[var(--zy-blue)] font-semibold" href="mailto:info@zynthoro.ai">
            info@zynthoro.ai
          </a>
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
