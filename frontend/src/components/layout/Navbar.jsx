import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";
import { HOME } from "@/constants/testIds";
import { usePresaleDialog } from "@/components/sections/PresaleDialog";

const links = [
  { id: HOME.navPlatform, label: "Platform", href: "#domains" },
  { id: HOME.navPricing, label: "Pricing", href: "#pricing" },
  { id: HOME.navEnterprise, label: "Enterprise", href: "#pricing" },
  { id: HOME.navAbout, label: "About", href: "#why" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { openDialog } = usePresaleDialog();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      data-testid={HOME.nav}
      className={`sticky top-0 z-50 w-full transition-shadow ${
        scrolled ? "shadow-[0_4px_24px_-12px_rgba(10,22,40,0.25)]" : ""
      }`}
      style={{ background: "var(--zy-blue)", height: 80 }}
    >
      <div className="zy-container h-full flex items-center justify-between">
        <a
          href="#top"
          data-testid={HOME.navLogo}
          className="flex items-center gap-1 select-none"
          aria-label="Zynthoro home"
        >
          <span
            style={{ color: "var(--zy-gold)", fontWeight: 800, letterSpacing: "0.02em" }}
            className="text-[22px]"
          >
            ZYN
          </span>
          <span className="text-[22px] font-extrabold tracking-wide text-white">THORO</span>
        </a>

        <nav className="hidden md:flex items-center gap-9">
          {links.map((l) => (
            <a
              key={l.id}
              data-testid={l.id}
              href={l.href}
              className="text-white/90 hover:text-white text-[15px] font-medium transition-colors"
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:block">
          <button
            data-testid={HOME.navCta}
            onClick={openDialog}
            className="zy-btn-nav"
          >
            Start Free Trial
          </button>
        </div>

        <button
          className="md:hidden text-white p-2"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
          data-testid="nav-mobile-toggle"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open && (
        <div className="md:hidden absolute top-20 left-0 right-0 bg-[#1A4FFF] border-t border-white/10">
          <div className="zy-container py-5 flex flex-col gap-4">
            {links.map((l) => (
              <a
                key={`m-${l.id}`}
                href={l.href}
                onClick={() => setOpen(false)}
                className="text-white/90 hover:text-white text-base font-medium"
              >
                {l.label}
              </a>
            ))}
            <button
              onClick={() => {
                setOpen(false);
                openDialog();
              }}
              className="zy-btn-nav self-start"
            >
              Start Free Trial
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
