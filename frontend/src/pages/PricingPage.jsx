/**
 * /pricing — dedicated pricing page with the full tier comparison.
 * Moved off the homepage on 2026-07-26 as part of the density cleanup.
 */
import { useEffect } from "react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import KickstartPricing from "@/components/sections/KickstartPricing";
import Pricing from "@/components/sections/Pricing";
import PricingComparisonTables from "@/components/sections/PricingComparisonTables";
import EnterpriseSection from "@/components/sections/EnterpriseSection";
import Comparison from "@/components/sections/Comparison";
import { PresaleDialogProvider } from "@/components/sections/PresaleDialog";

export default function PricingPage() {
  useEffect(() => {
    document.title = "Pricing — Zynthoro | Lifetime deals from €79 · Subscriptions from €24.99/mo";
    const setMeta = (name, content) => {
      let el = document.querySelector(`meta[name="${name}"]`);
      if (!el) { el = document.createElement("meta"); el.setAttribute("name", name); document.head.appendChild(el); }
      el.setAttribute("content", content);
    };
    setMeta(
      "description",
      "Zynthoro pricing — Kickstart lifetime deals from €79, monthly subscriptions from €24.99, and Enterprise plans. Compare every tier side-by-side."
    );

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
      <main data-testid="page-pricing">
        <section className="zy-section bg-white pb-0">
          <div className="zy-container max-w-4xl">
            <p className="zy-eyebrow mb-4">Pricing</p>
            <h1 className="zy-h1">Simple, honest, European pricing.</h1>
            <p className="zy-body mt-6 max-w-2xl">
              Lifetime deals from €79, transparent monthly tiers, and an Enterprise plan for teams that outgrow SaaS.
              Cancel any subscription any time. No lock-in, no surprise seat fees.
            </p>
          </div>
        </section>
        <KickstartPricing />
        <Pricing />
        <PricingComparisonTables />
        <EnterpriseSection />
        <Comparison />
      </main>
      <Footer />
    </PresaleDialogProvider>
  );
}
