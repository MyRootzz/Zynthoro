import { useEffect } from "react";
import { Link } from "react-router-dom";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { PresaleDialogProvider } from "@/components/sections/PresaleDialog";

const LEGAL_PAGES = [
  { to: "/legal/privacy-policy", label: "Privacy Policy" },
  { to: "/legal/terms-of-service", label: "Terms of Service" },
  { to: "/legal/cookie-policy", label: "Cookie Policy" },
  { to: "/legal/dpa", label: "Data Processing Agreement" },
  { to: "/legal/sla", label: "Service Level Agreement" },
];

export default function LegalLayout({ title, lastUpdated, current, children }) {
  useEffect(() => {
    document.title = `${title} — Zynthoro`;
    window.scrollTo(0, 0);
  }, [title]);

  return (
    <PresaleDialogProvider>
      <Navbar />

      {/* Hero strip */}
      <section
        style={{ background: "var(--zy-blue)" }}
        className="text-white"
        data-testid={`legal-${current}-hero`}
      >
        <div className="zy-container py-14 md:py-20">
          <p
            className="uppercase tracking-[0.18em] text-[12px] mb-3"
            style={{ color: "var(--zy-gold)" }}
          >
            Legal · Zynthoro
          </p>
          <h1 className="text-3xl md:text-5xl font-bold tracking-tight">
            {title}
          </h1>
          {lastUpdated && (
            <p className="text-white/70 mt-4 text-[14px]">
              Last updated: <span className="text-white">{lastUpdated}</span>
            </p>
          )}
        </div>
      </section>

      {/* Body */}
      <section className="bg-white">
        <div className="zy-container py-14 md:py-20 grid md:grid-cols-[260px_1fr] gap-10 md:gap-14">
          {/* Side nav */}
          <aside className="md:sticky md:top-[100px] self-start">
            <p className="text-[11px] uppercase tracking-[0.18em] text-black/40 mb-3">
              Documents
            </p>
            <nav className="flex flex-col gap-1" data-testid="legal-sidenav">
              {LEGAL_PAGES.map((p) => {
                const active = p.to.endsWith(current);
                return (
                  <Link
                    key={p.to}
                    to={p.to}
                    data-testid={`legal-nav-${p.to.split("/").pop()}`}
                    className={`text-[14px] py-2 px-3 rounded-md transition-colors border-l-2 ${
                      active
                        ? "border-[var(--zy-blue)] text-[var(--zy-blue)] bg-[#1A4FFF]/5 font-semibold"
                        : "border-transparent text-black/70 hover:text-black hover:bg-black/[0.03]"
                    }`}
                  >
                    {p.label}
                  </Link>
                );
              })}
            </nav>
            <div className="mt-8 p-4 rounded-md border border-black/10 text-[13px] text-black/70 leading-relaxed">
              Questions about this document?{" "}
              <a
                href="mailto:info@zynthoro.ai"
                className="text-[var(--zy-blue)] font-semibold"
              >
                info@zynthoro.ai
              </a>
            </div>
          </aside>

          {/* Article */}
          <article
            data-testid={`legal-${current}-content`}
            className="legal-prose max-w-[760px]"
          >
            {children}
          </article>
        </div>
      </section>

      <Footer />
    </PresaleDialogProvider>
  );
}
