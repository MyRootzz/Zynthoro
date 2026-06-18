import { Linkedin, Twitter, Instagram } from "lucide-react";
import { HOME } from "@/constants/testIds";

const cols = [
  {
    title: "Platform",
    links: [
      { label: "Features", href: "#domains" },
      { label: "Pricing", href: "#pricing" },
      { label: "Enterprise", href: "#pricing" },
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
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "#" },
      { label: "Terms of Service", href: "#" },
      { label: "Cookie Policy", href: "#" },
      { label: "DPA", href: "#" },
    ],
  },
];

export default function Footer() {
  return (
    <footer data-testid={HOME.footer} className="zy-footer">
      <div className="zy-container py-20">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10">
          <div>
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
                {c.links.map((l) => (
                  <li key={l.label}>
                    <a href={l.href} className="text-[14px]">
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 pt-6 border-t border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <p className="text-white/55 text-[13px]">
            © 2026 Zynthoro — Casa Haya International BV. All rights reserved.
          </p>
          <p className="text-white/45 text-[12px]">
            Powered by Anthropic Claude AI · Selected for the Anthropic Claude for Startups program
          </p>
        </div>
      </div>
    </footer>
  );
}
