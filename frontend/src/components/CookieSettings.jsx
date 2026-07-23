import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { X, ShieldCheck, BarChart3, Settings as Cog } from "lucide-react";

const KEY = "zy_cookie_prefs_v1";

const defaultPrefs = { necessary: true, functional: true, analytics: false };

const CookieCtx = createContext({ open: () => {}, prefs: defaultPrefs });
export const useCookieSettings = () => useContext(CookieCtx);

/**
 * Provides:
 *  - A cookie consent banner on first visit (bottom-right)
 *  - A "Cookie settings" modal openable via context (footer link, Cookie Policy page)
 *  - Preferences persisted in localStorage under `zy_cookie_prefs_v1`
 */
export function CookieSettingsProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [bannerVisible, setBannerVisible] = useState(false);
  const [prefs, setPrefs] = useState(defaultPrefs);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setPrefs({ ...defaultPrefs, ...JSON.parse(raw) });
      else setBannerVisible(true);
    } catch {
      setBannerVisible(true);
    }
  }, []);

  const save = useCallback((next) => {
    setPrefs(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignored */ }
    setBannerVisible(false);
    setOpen(false);
    // Propagate the analytics choice to Google Analytics (Consent Mode v2).
    // GA is loaded from public/index.html with all storage denied by default;
    // this call upgrades or downgrades in real time when the user changes
    // their cookie preference.
    if (typeof window !== "undefined" && typeof window.gtag === "function") {
      window.gtag("consent", "update", {
        analytics_storage: next.analytics ? "granted" : "denied",
      });
    }
  }, []);

  return (
    <CookieCtx.Provider value={{ open: () => setOpen(true), prefs }}>
      {children}
      {bannerVisible && !open && (
        <div
          role="dialog"
          aria-label="Cookie consent"
          data-testid="cookie-banner"
          className="fixed bottom-4 right-4 z-50 max-w-sm w-[min(92vw,420px)] bg-white border border-[#eee] rounded-xl shadow-[0_10px_40px_-8px_rgba(10,22,40,0.25)] p-5"
        >
          <p className="text-[13.5px] font-semibold text-black mb-1">We respect your privacy</p>
          <p className="text-[12.5px] text-[#555] leading-relaxed">
            We use strictly necessary cookies to run Zynthoro. Functional and
            analytics cookies are optional. Read our{" "}
            <a href="/legal/cookie-policy" className="text-[#1A4FFF] font-semibold">Cookie Policy</a>.
          </p>
          <div className="flex flex-wrap gap-2 mt-4">
            <button
              onClick={() => save({ necessary: true, functional: false, analytics: false })}
              className="px-3 py-1.5 text-[12.5px] font-medium rounded-md border border-[#eee] text-[#333]"
              data-testid="cookie-reject"
            >
              Reject all
            </button>
            <button
              onClick={() => setOpen(true)}
              className="px-3 py-1.5 text-[12.5px] font-medium rounded-md border border-[#eee] text-[#333]"
              data-testid="cookie-customize"
            >
              Customize
            </button>
            <button
              onClick={() => save({ necessary: true, functional: true, analytics: true })}
              className="px-3 py-1.5 text-[12.5px] font-semibold rounded-md text-white"
              style={{ background: "#1A4FFF" }}
              data-testid="cookie-accept"
            >
              Accept all
            </button>
          </div>
        </div>
      )}

      {open && (
        <CookieSettingsModal
          prefs={prefs}
          onClose={() => setOpen(false)}
          onSave={save}
        />
      )}
    </CookieCtx.Provider>
  );
}

function Row({ icon: Icon, title, desc, checked, onChange, locked, testid }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-[#f3f3f3] last:border-0">
      <div className="w-8 h-8 rounded-md flex items-center justify-center bg-[#F4F6FB] shrink-0">
        <Icon size={15} style={{ color: "#1A4FFF" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[13.5px] font-semibold text-black">{title}</p>
        <p className="text-[12.5px] text-[#666] mt-0.5 leading-relaxed">{desc}</p>
      </div>
      <label className="inline-flex items-center cursor-pointer select-none">
        <input
          type="checkbox"
          checked={checked}
          disabled={locked}
          onChange={(e) => onChange?.(e.target.checked)}
          className="sr-only peer"
          data-testid={testid}
        />
        <span className={`w-9 h-5 rounded-full transition-colors ${locked ? "bg-[#1A4FFF] opacity-50" : checked ? "bg-[#1A4FFF]" : "bg-[#ddd]"} relative`}>
          <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${checked ? "translate-x-4" : ""}`} />
        </span>
      </label>
    </div>
  );
}

function CookieSettingsModal({ prefs, onClose, onSave }) {
  const [local, setLocal] = useState(prefs);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/45" onClick={onClose} />
      <div
        role="dialog"
        aria-label="Cookie settings"
        data-testid="cookie-settings-modal"
        className="relative bg-white rounded-2xl shadow-xl w-[min(92vw,520px)] max-h-[88vh] overflow-y-auto p-6"
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 rounded hover:bg-[#F4F6FB]"
          aria-label="Close"
          data-testid="cookie-modal-close"
        >
          <X size={18} />
        </button>
        <p className="zy-eyebrow mb-2">Cookie settings</p>
        <h3 className="text-[22px] font-bold tracking-tight">Manage your preferences</h3>
        <p className="text-[13.5px] text-[#555] mt-2">
          Toggle the types of cookies you want Zynthoro to use. Strictly necessary
          cookies are always on so the platform can function.
        </p>

        <div className="mt-5">
          <Row
            icon={ShieldCheck}
            title="Strictly necessary"
            desc="Session, authentication and security cookies. Always on."
            checked
            locked
            testid="cookie-pref-necessary"
          />
          <Row
            icon={Cog}
            title="Functional"
            desc="Remember your UI preferences (theme, language)."
            checked={local.functional}
            onChange={(v) => setLocal((p) => ({ ...p, functional: v }))}
            testid="cookie-pref-functional"
          />
          <Row
            icon={BarChart3}
            title="Analytics"
            desc="Anonymous, first-party usage data — no third-party ad pixels."
            checked={local.analytics}
            onChange={(v) => setLocal((p) => ({ ...p, analytics: v }))}
            testid="cookie-pref-analytics"
          />
        </div>

        <div className="flex flex-wrap gap-2 justify-end mt-6">
          <button
            onClick={() => onSave({ necessary: true, functional: false, analytics: false })}
            className="px-3.5 py-2 text-[13px] font-medium rounded-md border border-[#eee] text-[#333]"
            data-testid="cookie-modal-reject"
          >
            Reject non-essential
          </button>
          <button
            onClick={() => onSave(local)}
            className="px-4 py-2 text-[13px] font-semibold rounded-md text-white"
            style={{ background: "#1A4FFF" }}
            data-testid="cookie-modal-save"
          >
            Save preferences
          </button>
        </div>
      </div>
    </div>
  );
}

/** Footer-style link that opens the cookie settings modal (Fix 11). */
export function CookieSettingsLink({ className = "" }) {
  const { open } = useCookieSettings();
  return (
    <button
      type="button"
      onClick={open}
      data-testid="footer-cookie-settings"
      className={`text-[14px] text-white/70 hover:text-white underline-offset-2 hover:underline ${className}`}
    >
      Cookie settings
    </button>
  );
}
