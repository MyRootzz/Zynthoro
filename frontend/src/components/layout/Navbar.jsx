import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { HOME } from "@/constants/testIds";

const links = [
  { id: HOME.navPlatform, label: "Modules",    to: "/modules"    },
  { id: "nav-assistants", label: "Assistants", to: "/assistants" },
  { id: HOME.navPricing,  label: "Pricing",    to: "/pricing"    },
  { id: "nav-blog",       label: "Blog",       to: "/blog"       },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { pathname } = useLocation();

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
        <Link
          to="/"
          data-testid={HOME.navLogo}
          className="flex items-center gap-1 select-none"
          aria-label="Zynthoro home"
        >
          <span
            style={{ color: "var(--zy-gold)", fontWeight: 800, letterSpacing: "0.02em" }}
            className="text-[22px]"
          >
            ZYNTHORO
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-9">
          {links.map((l) => {
            const active = pathname === l.to || (l.to !== "/" && pathname.startsWith(l.to));
            return (
              <Link
                key={l.id}
                data-testid={l.id}
                to={l.to}
                className={`text-[15px] font-medium transition-colors ${
                  active ? "text-white" : "text-white/85 hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <a
            href="https://calendly.com/zynthoro/30min"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="nav-book-call"
            className="zy-btn-nav-ghost"
          >
            Book a free 30-min call
          </a>
          <Link
            to="/login"
            data-testid="nav-login"
            className="zy-btn-nav-ghost"
          >
            Log in
          </Link>
          <Link
            to="/signup"
            data-testid={HOME.navCta}
            className="zy-btn-nav"
          >
            Get started
          </Link>
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
              <Link
                key={`m-${l.id}`}
                to={l.to}
                onClick={() => setOpen(false)}
                className="text-white/90 hover:text-white text-base font-medium"
              >
                {l.label}
              </Link>
            ))}
            <Link
              to="/signup"
              onClick={() => setOpen(false)}
              className="zy-btn-nav self-start"
            >
              Get started
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
