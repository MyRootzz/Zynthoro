import { useEffect } from "react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Hero from "@/components/sections/Hero";
import SocialProof from "@/components/sections/SocialProof";
import WhyZynthoro from "@/components/sections/WhyZynthoro";
import Domains from "@/components/sections/Domains";
import Pricing from "@/components/sections/Pricing";
import PricingComparisonTables from "@/components/sections/PricingComparisonTables";
import EnterpriseSection from "@/components/sections/EnterpriseSection";
import Assist from "@/components/sections/Assist";
import Assistants from "@/components/sections/Assistants";
import Comparison from "@/components/sections/Comparison";
import AnyDeviceSection from "@/components/sections/AnyDeviceSection";
import ProductionSection from "@/components/sections/ProductionSection";
import VoiceAISection from "@/components/sections/VoiceAISection";
import PresaleCTA from "@/components/sections/PresaleCTA";
import { PresaleDialogProvider } from "@/components/sections/PresaleDialog";

export default function Home() {
  useEffect(() => {
    document.title =
      "Zynthoro — The Next-Gen AI ERP Ecosystem | All-in-One Business Platform";

    const setMeta = (name, content) => {
      let el = document.querySelector(`meta[name="${name}"]`);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute("name", name);
        document.head.appendChild(el);
      }
      el.setAttribute("content", content);
    };
    setMeta(
      "description",
      "The next-gen AI ERP ecosystem. Replace 15+ business tools with one AI-native platform. Starting at €499/month. Launching 30 June 2026."
    );

    // Reveal on scroll
    const els = document.querySelectorAll(".zy-reveal");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <PresaleDialogProvider>
      <Navbar />
      <main>
        <Hero />
        <SocialProof />
        <WhyZynthoro />
        <Domains />
        <ProductionSection />
        <Assistants />
        <VoiceAISection />
        <Pricing />
        <PricingComparisonTables />
        <EnterpriseSection />
        <Assist />
        <Comparison />
        <AnyDeviceSection />
        <PresaleCTA />
      </main>
      <Footer />
    </PresaleDialogProvider>
  );
}
