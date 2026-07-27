/**
 * Slim homepage (restructured 2026-07-26).
 *
 * Landing visitors should understand what Zynthoro is in 10 seconds and
 * know exactly where to click for depth. Long-form sections live at:
 *   /modules     — the 12 ERP modules
 *   /assistants  — the four AI specialists in detail
 *   /pricing     — full tier comparison, Enterprise, competitor comparison
 *   /blog        — Latest Articles
 */
import { useEffect } from "react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Hero from "@/components/sections/Hero";
import SocialProof from "@/components/sections/SocialProof";
import HomeIntro from "@/components/sections/HomeIntro";
import HomeAssistantsBrief from "@/components/sections/HomeAssistantsBrief";
import HomePricingBrief from "@/components/sections/HomePricingBrief";
import LatestArticles from "@/components/sections/LatestArticles";
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
      "AI-native ERP for European SMEs · Kickstart lifetime deals from €79 · Starting at €24.99/mo."
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
      <main data-testid="page-home">
        <Hero />
        <SocialProof />
        <HomeIntro />
        <HomeAssistantsBrief />
        <HomePricingBrief />
        <LatestArticles />
      </main>
      <Footer />
    </PresaleDialogProvider>
  );
}
