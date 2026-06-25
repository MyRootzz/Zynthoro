import LegalLayout from "@/components/legal/LegalLayout";
import { LegalSection, LegalList } from "@/components/legal/LegalSection";

export default function DPA() {
  return (
    <LegalLayout
      title="Data Processing Agreement"
      lastUpdated="February 5, 2026"
      current="dpa"
    >
      <p className="text-[16px] text-black/80 mb-10 leading-[1.8]">
        This Data Processing Agreement ("DPA") forms part of the Zynthoro Terms
        of Service between you ("Controller") and{" "}
        <strong>Casa Haya International BV</strong> ("Processor", "Zynthoro").
        It reflects the parties' obligations under Article 28 GDPR.
      </p>

      <LegalSection id="subject" number="1" title="Subject matter & duration">
        <p>
          Zynthoro processes personal data on behalf of the Controller solely
          to provide the Zynthoro platform and the four AI Assistants. The DPA
          remains in force for as long as Zynthoro processes such data.
        </p>
      </LegalSection>

      <LegalSection id="nature" number="2" title="Nature & purpose of processing">
        <LegalList
          items={[
            "Hosting Controller's workspace data (HR records, customers, invoices, inventory, etc.).",
            "Running AI Assistants on Controller's prompts and data.",
            "Sending transactional emails on behalf of Controller (e.g. team invites).",
            "Generating analytics and dashboards visible only to Controller.",
          ]}
        />
      </LegalSection>

      <LegalSection id="categories" number="3" title="Categories of data subjects & data">
        <LegalList
          items={[
            "Data subjects: Controller's employees, customers, suppliers, leads, end-users.",
            "Categories: identifiers, contact info, employment data, financial data, communications, AI prompt content.",
            "Special categories (Art. 9): Controller decides whether to upload such data. Where uploaded (e.g. HR sick-leave notes), Zynthoro applies the same security controls.",
          ]}
        />
      </LegalSection>

      <LegalSection id="instructions" number="4" title="Processor obligations">
        <LegalList
          items={[
            "Process personal data only on documented instructions from the Controller.",
            "Ensure persons authorised to process data are bound by confidentiality.",
            "Implement appropriate technical and organisational measures (Annex A).",
            "Engage sub-processors only under written contracts with equivalent obligations.",
            "Assist the Controller in responding to data-subject requests within statutory deadlines.",
            "Notify the Controller of any personal data breach without undue delay and at the latest within 72 hours.",
            "On termination, delete or return all personal data within 90 days, unless EU/NL law requires retention.",
          ]}
        />
      </LegalSection>

      <LegalSection id="subprocessors" number="5" title="Sub-processors">
        <p>Zynthoro uses the following sub-processors (versioned list available on request):</p>
        <LegalList
          items={[
            "Stripe Payments Europe Ltd. (Ireland) — payments.",
            "Anthropic PBC (USA, SCCs) — Claude AI inference.",
            "Google LLC (USA, SCCs) — Gemini AI inference.",
            "Resend Inc. (USA, SCCs) — transactional email.",
            "MongoDB Atlas (EU-West) — primary database.",
            "Cloudflare Inc. (USA, SCCs) — DNS / CDN / WAF.",
            "Amazon Web Services EMEA (Ireland) — file/object storage.",
          ]}
        />
        <p>
          Zynthoro will notify Controller at least 30 days before adding or
          replacing a sub-processor; Controller may object on reasonable grounds.
        </p>
      </LegalSection>

      <LegalSection id="security" number="6" title="Annex A — Security measures">
        <LegalList
          items={[
            "TLS 1.3 in transit, AES-256 at rest.",
            "Bcrypt password hashing (cost 12) and optional 2FA (TOTP).",
            "Role-based access control with least-privilege defaults.",
            "Quarterly third-party penetration tests; annual code audit.",
            "Centralised logging with 30-day immutable retention.",
            "Encrypted, geo-redundant backups (RPO 24h, RTO 4h).",
            "Documented incident-response runbook and 24/7 on-call.",
            "Background checks for all engineers with production access.",
          ]}
        />
      </LegalSection>

      <LegalSection id="transfers" number="7" title="International transfers">
        <p>
          Where personal data is transferred outside the EEA (e.g. to Anthropic
          or Google in the US), Zynthoro relies on the European Commission's
          Standard Contractual Clauses (Module 3, 2021) and applies
          supplementary measures including end-to-end encryption and
          zero-retention AI inference contracts.
        </p>
      </LegalSection>

      <LegalSection id="audit" number="8" title="Audits">
        <p>
          On request, Zynthoro will provide an annual SOC 2 Type II report (or
          equivalent) once available, and respond to reasonable written audit
          questionnaires within 30 days. On-site audits may be conducted at
          Controller's cost once per year with 60 days' notice.
        </p>
      </LegalSection>

      <LegalSection id="liability" number="9" title="Liability & termination">
        <p>
          Each party's liability under this DPA is subject to the limits in the
          main Terms of Service. The DPA terminates automatically with the main
          Terms.
        </p>
      </LegalSection>

      <LegalSection id="contact" number="10" title="Contact">
        <p>
          DPO contact:{" "}
          <a className="text-[var(--zy-blue)] font-semibold" href="mailto:dpo@zynthoro.ai">
            dpo@zynthoro.ai
          </a>
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
