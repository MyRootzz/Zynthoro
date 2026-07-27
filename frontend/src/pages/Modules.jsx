/**
 * /modules — dedicated page for the 12 ERP modules and platform breadth.
 * Moved off the homepage on 2026-07-26 as part of the density cleanup.
 */
import { useEffect } from "react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Domains from "@/components/sections/Domains";
import ProductionSection from "@/components/sections/ProductionSection";
import AnyDeviceSection from "@/components/sections/AnyDeviceSection";
import WhyZynthoro from "@/components/sections/WhyZynthoro";
import { PresaleDialogProvider } from "@/components/sections/PresaleDialog";

export default function Modules() {
  useEffect(() => {
    document.title = "Modules — Zynthoro | 12 AI-native ERP modules for SMEs";
    const setMeta = (name, content) => {
      let el = document.querySelector(`meta[name="${name}"]`);
      if (!el) { el = document.createElement("meta"); el.setAttribute("name", name); document.head.appendChild(el); }
      el.setAttribute("content", content);
    };
    setMeta(
      "description",
      "Explore Zynthoro's 12 AI-native ERP modules — Finance, Sales, HR, Projects, Planning, Marketing, and more. One platform, one truth."
    );

    // Reveal on scroll (same pattern as Home)
    const els = document.querySelectorAll(".zy-reveal");
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
      }),
      { threshold: 0.12 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <PresaleDialogProvider>
      <Navbar />
      <main data-testid="page-modules">
        {/* Page hero */}
        <section className="zy-section bg-white pb-0">
          <div className="zy-container max-w-4xl">
            <p className="zy-eyebrow mb-4">The platform</p>
            <h1 className="zy-h1">12 modules. One AI. One truth.</h1>
            <p className="zy-body mt-6 max-w-2xl">
              Every module talks to every other module — no more copying data between disconnected tools.
              Zynthoro replaces 8–15 SaaS subscriptions with a single AI-native ERP built for European SMEs.
            </p>
          </div>
        </section>
        <Domains />
        <ProductionSection />
        <WhyZynthoro />
        <AnyDeviceSection />
      </main>
      <Footer />
    </PresaleDialogProvider>
  );
}
