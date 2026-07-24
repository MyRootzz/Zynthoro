import { Linkedin, Twitter, Instagram } from "lucide-react";
import { Link } from "react-router-dom";
import { HOME } from "@/constants/testIds";
import { CookieSettingsLink } from "@/components/CookieSettings";

const cols = [
  {
    title: "Platform",
    links: [
      { label: "Features", href: "#domains" },
      { label: "Pricing", href: "#pricing" },
      { label: "Enterprise", href: "#enterprise" },
      { label: "Integrations", href: "#domains" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "#why" },
      { label: "Blog", href: "#" },
      { label: "Careers", href: "#" },
      { label: "Press", href: "#" },
    ],
  },
  {
    title: "Contact",
    links: [
      { label: "info@zynthoro.ai", href: "mailto:info@zynthoro.ai" },
      { label: "hello@zynthoro.ai", href: "mailto:hello@zynthoro.ai" },
      { label: "support@zynthoro.ai", href: "mailto:support@zynthoro.ai" },
      { label: "enterprise@zynthoro.ai", href: "mailto:enterprise@zynthoro.ai" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "/legal/privacy-policy" },
      { label: "Terms of Service", href: "/legal/terms-of-service" },
      { label: "Cookie Policy", href: "/legal/cookie-policy" },
      { label: "DPA", href: "/legal/dpa" },
      { label: "SLA", href: "/legal/sla" },
    ],
  },
];

export default function Footer() {
  return (
    <footer data-testid={HOME.footer} className="zy-footer">
      <div className="zy-container py-20">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-1 mb-4">
              <span style={{ color: "var(--zy-gold)", fontWeight: 800 }} className="text-[22px]">
                ZYNTHORO
              </span>
            </div>
            <p className="text-white/70 text-[15px] leading-relaxed max-w-xs">
              The Next-Gen AI ERP Ecosystem. One platform. One AI. One truth. Replace 15+ tools with Zynthoro.
            </p>
            <div className="flex items-center gap-3 mt-6">
              <a href="#" aria-label="LinkedIn" className="p-2 rounded-md bg-white/5 hover:bg-white/10">
                <Linkedin size={18} />
              </a>
              <a href="#" aria-label="Twitter" className="p-2 rounded-md bg-white/5 hover:bg-white/10">
                <Twitter size={18} />
              </a>
              <a href="#" aria-label="Instagram" className="p-2 rounded-md bg-white/5 hover:bg-white/10">
                <Instagram size={18} />
              </a>
            </div>
          </div>

          {cols.map((c) => (
            <div key={c.title}>
              <h4 className="text-white font-semibold mb-4 text-[15px]" style={{ color: "var(--zy-gold)" }}>
                {c.title}
              </h4>
              <ul className="space-y-3">
                {c.links.map((l) => {
                  const isInternal = l.href.startsWith("/");
                  return (
                    <li key={l.label}>
                      {isInternal ? (
                        <Link to={l.href} className="text-[14px]" data-testid={`footer-link-${l.label.toLowerCase().replace(/\s+/g, "-")}`}>
                          {l.label}
                        </Link>
                      ) : (
                        <a href={l.href} className="text-[14px]">
                          {l.label}
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        {/* "As seen on" — consolidated social proof strip. TAAFT/PH/Uneed
            badges live here as the canonical, user-visible React version.
            Static <a> anchors also exist in public/index.html so non-JS
            crawlers (TAAFT verifier, etc.) can discover them. Do not
            remove those static anchors. */}
        <div
          data-testid="footer-as-seen-on"
          className="mt-16 pt-8 border-t border-white/10"
        >
          <div className="flex flex-col md:flex-row md:items-center gap-6 md:gap-10">
            <div className="flex items-center gap-3 md:min-w-[140px]">
              <span
                className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/50"
              >
                As seen on
              </span>
              <span className="hidden md:block h-px w-8 bg-white/15" />
            </div>
            <div className="flex flex-wrap items-center gap-x-8 gap-y-5">
              <a
                href="https://theresanaiforthat.com/ai/zynthoro/?ref=featured&v=11900095"
                target="_blank"
                rel="nofollow noopener noreferrer"
                className="inline-flex items-center opacity-80 hover:opacity-100 transition-opacity"
                data-testid="footer-taaft-badge"
                aria-label="Featured on There's An AI For That"
              >
                <img
                  src="https://media.theresanaiforthat.com/social/icon_full.svg"
                  alt="Featured on TAAFT"
                  loading="lazy"
                  style={{ display: "block", height: 54, width: "auto" }}
                />
              </a>
              <a
                href="https://www.producthunt.com/products/zynthoro-the-next?embed=true&utm_source=badge-featured&utm_medium=badge&utm_campaign=badge-zynthoro-the-next"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center opacity-80 hover:opacity-100 transition-opacity"
                data-testid="footer-producthunt-badge"
                aria-label="Featured on Product Hunt"
              >
                <img
                  src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1202551&theme=light&t=1784786507425"
                  alt="Zynthoro — The Next - Replace 15+ business tools with one AI-native ERP | Product Hunt"
                  width="220"
                  height="48"
                  loading="lazy"
                  style={{ display: "block", height: 48, width: "auto" }}
                />
              </a>
              <a
                href="https://www.uneed.best/tool/zynthoro"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center opacity-80 hover:opacity-100 transition-opacity"
                data-testid="footer-uneed-badge"
                aria-label="Featured on Uneed"
              >
                <img
                  src="https://www.uneed.best/EMBED1A.png"
                  alt="Featured on Uneed"
                  loading="lazy"
                  style={{ display: "block", height: 48, width: "auto" }}
                />
              </a>
            </div>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <p className="text-white/55 text-[13px]">
            © 2026 Zynthoro — Casa Haya International BV (KvK 99196581). All rights reserved.
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <CookieSettingsLink />
            <p className="text-white/45 text-[12px]">
              Powered by Anthropic Claude AI · Selected for the Anthropic Claude for Startups program
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
