import LegalLayout from "@/components/legal/LegalLayout";
import { LegalSection, LegalList } from "@/components/legal/LegalSection";

export default function TermsOfService() {
  return (
    <LegalLayout
      title="Terms of Service"
      lastUpdated="February 5, 2026"
      current="terms-of-service"
    >
      <p className="text-[16px] text-black/80 mb-10 leading-[1.8]">
        These Terms of Service ("Terms") govern your access to and use of the
        Zynthoro platform operated by{" "}
        <strong>Casa Haya International BV</strong> (KvK 99196581), a private
        limited company registered in the Netherlands. By creating an account,
        you accept these Terms in full.
      </p>

      <LegalSection id="service" number="1" title="The service">
        <p>
          Zynthoro is an AI-native ERP platform combining 12 business domains
          (HR, Finance, CRM, Operations, Inventory, Projects, Marketing,
          Support, Legal, Analytics, Procurement, Compliance) with four AI
          Assistants — Zynthoro Assist, Zyntha, Thoro and Zyona — accessible
          through a single workspace at zynthoro.ai.
        </p>
      </LegalSection>

      <LegalSection id="eligibility" number="2" title="Eligibility & account">
        <LegalList
          items={[
            "You must be 18 years or older and authorised to bind your company.",
            "You must provide accurate company information at signup.",
            "You are responsible for all activity under your account, including invited team members.",
            "Two-factor authentication is strongly recommended; on Enterprise plans it is mandatory.",
          ]}
        />
      </LegalSection>

      <LegalSection id="plans" number="3" title="Plans, billing & Kickstart lifetime deals">
        <LegalList
          items={[
            "Standard subscription pricing: Starter €499/mo, Creator €699/mo, Business €899/mo, Agency €1,199/mo, Enterprise from €2,499/mo. Annual billing (2 months free) is available on all subscription plans.",
            "Kickstart lifetime deals are one-time purchases: Kickstart 1 €79, Kickstart 2 €129, Kickstart 3 €199 — each capped at 100 seats. The purchased tier includes lifetime access to the modules and workspaces defined in the tier at time of purchase.",
            "Kickstart Compleet is a monthly subscription (€49/mo) with the full non-ERP module suite.",
            "AI+Social top-ups (Week €24.99 / Month €59.99) grant additional AI credits for a fixed period on top of any existing plan. Top-ups do not modify or extend the base plan.",
            "Subscriptions are billed in advance via Stripe in EUR. All fees are exclusive of VAT, which is added where legally required.",
            "Failed payments on subscriptions trigger a 7-day grace period before service suspension.",
          ]}
        />
      </LegalSection>

      <LegalSection id="lifetime-terms" number="3a" title="Kickstart lifetime — specific terms">
        <p className="mb-3">
          "Lifetime" means for the operational lifetime of the Zynthoro
          platform in its consumer-facing form. Zynthoro Labs BV commits to
          maintaining the service for a minimum of five (5) years from your
          purchase date. If the service is sunset, migrated, or the entity
          restructures such that the platform is discontinued, we will provide
          at least ninety (90) days' notice and, where technically feasible, a
          data export.
        </p>
        <p className="mb-3">
          Lifetime access is bound to the account (email) that made the
          purchase. It is non-transferable, non-refundable after activation
          (see waiver below), and cannot be resold. Feature parity is preserved:
          your Kickstart tier will always include the modules and workspace
          count listed at the time of your purchase, even if we later restructure
          plan tiers.
        </p>
        <p>
          Fair-use limits apply on AI credits per the tier you purchased.
          Exceeding your allowance requires an AI+Social top-up or a Compleet
          subscription.
        </p>
      </LegalSection>

      <LegalSection id="withdrawal-waiver" number="3b" title="EU right of withdrawal — waiver (herroepingsrecht)">
        <p className="mb-3">
          Under EU Directive 2011/83/EU and Article 6:230p sub h of the Dutch
          Civil Code (BW), you normally have 14 days to withdraw from a distance
          purchase. By checking the herroepingsrecht waiver on the Kickstart
          checkout page, you <strong>expressly consent to immediate performance
          of the service</strong> and <strong>acknowledge that you lose your
          right of withdrawal</strong> once we begin providing access — which
          happens immediately on successful payment.
        </p>
        <p>
          This waiver applies exclusively to Kickstart lifetime tiers and
          AI+Social top-ups (one-time digital services). It does <em>not</em>
          apply to subscription plans, which are governed by clause 4
          (Cancellation) below.
        </p>
      </LegalSection>

      <LegalSection id="cancellation" number="4" title="Cancellation & refunds (subscriptions only)">
        <p>
          Subscription plans (Starter, Creator, Business, Agency, Enterprise,
          Compleet) can be cancelled any time from Settings → Billing.
          Cancellation takes effect at the end of the current billing period;
          you keep access until then. We do not refund partial months.
          Annual contracts on Enterprise follow their negotiated termination
          clause.
        </p>
        <p className="mt-3">
          Kickstart lifetime purchases and AI+Social top-ups are one-time
          digital services and are governed by clauses 3a and 3b above — they
          are non-refundable after activation (herroepingsrecht waived at
          checkout).
        </p>
      </LegalSection>

      <LegalSection id="acceptable" number="5" title="Acceptable use">
        <p>You agree not to:</p>
        <LegalList
          items={[
            "Use Zynthoro to build a competing AI ERP product or to benchmark it for that purpose.",
            "Submit data you do not have the right to process (no scraped or stolen PII).",
            "Attempt to jailbreak, prompt-inject or otherwise misuse the AI Assistants.",
            "Reverse-engineer, decompile or scrape the platform.",
            "Resell, sublicense or white-label the service without a written Enterprise agreement.",
            "Use the service for activities prohibited by EU/NL law (sanctions, money laundering, CSAM, etc.).",
          ]}
        />
      </LegalSection>

      <LegalSection id="ip" number="6" title="Intellectual property">
        <LegalList
          items={[
            "Zynthoro retains all rights, title and interest in the platform, including the AI Assistants' personas, prompts, UI and Zynthoro brand assets.",
            "You retain ownership of all data and content you upload ('Customer Data').",
            "You grant Zynthoro a limited licence to process Customer Data solely to deliver the service.",
            "AI outputs generated for you are owned by you, subject to Anthropic's and Google's underlying model terms.",
          ]}
        />
      </LegalSection>

      <LegalSection id="confidentiality" number="7" title="Confidentiality">
        <p>
          Each party will treat the other's non-public information as
          confidential and use it only to fulfil these Terms, for a period of
          five years after termination.
        </p>
      </LegalSection>

      <LegalSection id="warranties" number="8" title="Warranties & disclaimer">
        <p>
          Zynthoro is provided "as is" and "as available". We make no warranty
          that the AI Assistants will produce factually correct or
          legally-compliant output. <strong>You must independently verify any
          AI-generated content before relying on it for critical decisions.</strong>
        </p>
      </LegalSection>

      <LegalSection id="liability" number="9" title="Limitation of liability">
        <p>
          To the maximum extent permitted by law, Zynthoro's aggregate liability
          for any claim arising out of these Terms is limited to the fees paid
          by you in the 12 months preceding the claim. We are not liable for
          indirect, incidental, consequential or punitive damages, lost profits
          or lost data.
        </p>
      </LegalSection>

      <LegalSection id="termination" number="10" title="Termination">
        <p>
          We may suspend or terminate your account for material breach of these
          Terms, illegal activity, or non-payment after the grace period. Upon
          termination, you retain a 90-day window to export Customer Data,
          after which it is permanently deleted.
        </p>
      </LegalSection>

      <LegalSection id="law" number="11" title="Governing law & jurisdiction">
        <p>
          These Terms are governed by the laws of the Netherlands. Any dispute
          will be submitted to the exclusive jurisdiction of the courts of
          Amsterdam, without prejudice to your mandatory consumer rights.
        </p>
      </LegalSection>

      <LegalSection id="contact" number="12" title="Contact">
        <p>
          For legal notices, send to Casa Haya International BV (KvK 99196581):{" "}
          <a className="text-[var(--zy-blue)] font-semibold" href="mailto:info@zynthoro.ai">
            info@zynthoro.ai
          </a>
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
