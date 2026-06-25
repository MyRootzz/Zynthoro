import LegalLayout from "@/components/legal/LegalLayout";
import { LegalSection, LegalList } from "@/components/legal/LegalSection";

export default function CookiePolicy() {
  return (
    <LegalLayout
      title="Cookie Policy"
      lastUpdated="February 5, 2026"
      current="cookies"
    >
      <p className="text-[16px] text-black/80 mb-10 leading-[1.8]">
        This Cookie Policy explains how Zynthoro uses cookies and similar
        technologies on zynthoro.ai. It should be read alongside our Privacy
        Policy.
      </p>

      <LegalSection id="what" number="1" title="What are cookies?">
        <p>
          Cookies are small text files stored on your device. We use them to
          keep you signed in, remember preferences and measure how the platform
          is used. We do not use cross-site advertising trackers.
        </p>
      </LegalSection>

      <LegalSection id="types" number="2" title="Cookies we use">
        <p>
          <strong>Strictly necessary (always on):</strong>
        </p>
        <LegalList
          items={[
            "zy_session — JWT session token (HTTP-only, 7 days).",
            "zy_2fa — short-lived 2FA challenge token (10 minutes).",
            "zy_csrf — anti-CSRF token (session).",
          ]}
        />
        <p className="mt-4">
          <strong>Functional (only set after explicit consent):</strong>
        </p>
        <LegalList
          items={[
            "zy_theme — your theme/UI preference.",
            "zy_locale — language preference.",
          ]}
        />
        <p className="mt-4">
          <strong>Analytics (only after consent):</strong>
        </p>
        <LegalList
          items={[
            "_zy_anon_id — anonymised first-party analytics ID, 12 months.",
          ]}
        />
        <p>
          We do <strong>not</strong> use third-party advertising cookies,
          Facebook Pixel, Google Ads or TikTok pixels.
        </p>
      </LegalSection>

      <LegalSection id="consent" number="3" title="Your choices">
        <p>
          On your first visit you'll see a cookie banner with three options:
          Accept all, Reject non-essential, or Customize. You can change your
          choice any time from the footer link <em>Cookie settings</em>.
          Rejecting analytics cookies does not affect platform functionality.
        </p>
      </LegalSection>

      <LegalSection id="browser" number="4" title="Browser controls">
        <p>
          You can also clear or block cookies from your browser settings (see
          chrome.com, mozilla.org, support.apple.com). Disabling strictly
          necessary cookies will sign you out and prevent the platform from
          working.
        </p>
      </LegalSection>

      <LegalSection id="contact" number="5" title="Questions">
        <p>
          Reach us at{" "}
          <a className="text-[var(--zy-blue)] font-semibold" href="mailto:privacy@zynthoro.ai">
            privacy@zynthoro.ai
          </a>
          .
        </p>
      </LegalSection>
    </LegalLayout>
  );
}
