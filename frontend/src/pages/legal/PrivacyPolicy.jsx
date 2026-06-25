import LegalLayout from "@/components/legal/LegalLayout";
import { LegalSection, LegalList } from "@/components/legal/LegalSection";

export default function PrivacyPolicy() {
  return (
    <LegalLayout
      title="Privacy Policy"
      lastUpdated="February 5, 2026"
      current="privacy-policy"
    >
      <p className="text-[16px] text-black/80 mb-10 leading-[1.8]">
        Zynthoro is operated by <strong>Casa Haya International BV</strong>{" "}
        (KvK 99196581, "Zynthoro", "we", "us"), a private limited company
        registered in the Netherlands. This Privacy Policy explains what
        personal data we collect when you use the Zynthoro platform
        (zynthoro.ai), how we use it, and the rights you have under the EU
        General Data Protection Regulation (GDPR) and the Dutch GDPR
        Implementation Act (UAVG). All personal data is hosted on EU-based
        infrastructure, primarily in the Republic of Ireland (eu-west).
      </p>

      <LegalSection id="controller" number="1" title="Data Controller">
        <p>
          Casa Haya International BV (KvK 99196581) is the data controller for
          personal data processed through Zynthoro. You can reach us at{" "}
          <a className="text-[var(--zy-blue)] font-semibold" href="mailto:info@zynthoro.ai">
            info@zynthoro.ai
          </a>
          .
        </p>
      </LegalSection>

      <LegalSection id="data" number="2" title="Personal data we collect">
        <p>We collect only what we need to run the platform:</p>
        <LegalList
          items={[
            "Account data: full name, work email, company name, role, hashed password, 2FA secret.",
            "Subscription data: plan tier, billing email, Stripe customer ID, founder-discount eligibility.",
            "Business verification data: PDF business-registration documents you upload (KvK, LLC, Companies House, etc.) and the AI-extracted metadata (company name, registration number, registration date).",
            "Usage data: page views, feature events, AI assistant prompts and responses (linked to your workspace, never sold).",
            "Technical data: IP address, browser, device, language, session cookies.",
          ]}
        />
      </LegalSection>

      <LegalSection id="purpose" number="3" title="Why we process it">
        <LegalList
          items={[
            "To create and secure your Zynthoro account (Art. 6(1)(b) GDPR — contract).",
            "To verify your business age for the €99/month founder discount (Art. 6(1)(b) GDPR).",
            "To run the AI Assistants (Zynthoro Assist, Zyntha, Thoro, Zyona) on your behalf (Art. 6(1)(b)).",
            "To bill you via Stripe and prevent payment fraud (Art. 6(1)(c) — legal obligation).",
            "To improve product quality and security (Art. 6(1)(f) — legitimate interest).",
            "To send service emails about your account (transactional, never marketing without consent).",
          ]}
        />
      </LegalSection>

      <LegalSection id="ai" number="4" title="AI processing">
        <p>
          When you chat with a Zynthoro AI Assistant, your prompts are forwarded
          to Anthropic (Claude Sonnet 4.6 / Opus 4) and/or Google (Gemini 2.5
          Flash) under our zero-retention enterprise contracts. Neither provider
          uses your prompts to train their foundation models. AI session logs
          are stored inside your workspace database and you can delete them at
          any time from <em>Settings → AI history</em>.
        </p>
      </LegalSection>

      <LegalSection id="sharing" number="5" title="Sub-processors & EU hosting">
        <p>
          All Customer Data is hosted on EU-based infrastructure, primarily in
          the Republic of Ireland (eu-west). We share data only with the
          sub-processors needed to deliver the service:
        </p>
        <LegalList
          items={[
            "Stripe Payments Europe Ltd. (Ireland, EU) — payments and invoicing.",
            "Anthropic PBC (USA, SCCs + zero-retention) — Claude AI inference.",
            "Google LLC (USA, SCCs + zero-retention) — Gemini AI inference.",
            "Resend Inc. (USA, SCCs) — transactional emails (account, 2FA, password resets).",
            "MongoDB Atlas (Ireland, eu-west region) — primary database storage.",
            "Amazon Web Services EMEA SARL (Ireland, eu-west) — file/object storage and backups.",
            "Cloudflare Inc. (USA, SCCs) — DNS, CDN, DDoS protection.",
          ]}
        />
        <p>
          A full, version-controlled list lives in our DPA. International
          transfers use Standard Contractual Clauses (SCCs) plus supplementary
          measures (end-to-end encryption, zero-retention AI contracts).
        </p>
      </LegalSection>

      <LegalSection id="retention" number="6" title="Retention">
        <LegalList
          items={[
            "Active account data: kept while your subscription is active.",
            "After cancellation: 90-day grace period for export, then permanent deletion.",
            "Billing records: retained 7 years (Dutch tax law).",
            "AI chat sessions: retained until you delete them; default purge after 24 months of inactivity.",
            "Backups: rolling 30-day encrypted backups.",
          ]}
        />
      </LegalSection>

      <LegalSection id="rights" number="7" title="Your rights under GDPR">
        <p>You have the right to:</p>
        <LegalList
          items={[
            "Access the personal data we hold about you.",
            "Rectify inaccurate data directly from Settings or by email.",
            "Erase your data ('right to be forgotten') after subscription end.",
            "Restrict or object to certain processing activities.",
            "Data portability — export your workspace as JSON/CSV.",
            "Withdraw consent for any optional processing at any time.",
            "Lodge a complaint with the Dutch Autoriteit Persoonsgegevens (autoriteitpersoonsgegevens.nl).",
          ]}
        />
      </LegalSection>

      <LegalSection id="security" number="8" title="Security">
        <p>
          All data is encrypted in transit (TLS 1.3) and at rest (AES-256).
          Passwords are hashed with bcrypt (cost 12). Two-factor authentication
          is available on all plans. We run quarterly penetration tests and
          maintain a public security.txt.
        </p>
      </LegalSection>

      <LegalSection id="changes" number="9" title="Changes to this policy">
        <p>
          We will notify you by email at least 14 days before any material
          change. Continued use of Zynthoro after that date constitutes
          acceptance of the updated policy.
        </p>
      </LegalSection>

      <LegalSection id="contact" number="10" title="Contact">
        <p>
          Casa Haya International BV (KvK 99196581)<br />
          Amsterdam, The Netherlands<br />
          <a className="text-[var(--zy-blue)] font-semibold" href="mailto:info@zynthoro.ai">
            info@zynthoro.ai
          </a>
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
