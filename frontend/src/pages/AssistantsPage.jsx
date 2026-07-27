/**
 * /assistants — dedicated page for the four AI assistants.
 * Moved off the homepage on 2026-07-26 as part of the density cleanup.
 */
import { useEffect } from "react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Assistants from "@/components/sections/Assistants";
import Assist from "@/components/sections/Assist";
import VoiceAISection from "@/components/sections/VoiceAISection";
import { PresaleDialogProvider } from "@/components/sections/PresaleDialog";

export default function AssistantsPage() {
  useEffect(() => {
    document.title = "AI Assistants — Zynthoro | Zyntha · Thoro · Zyona · Zynthoro Assist";
    const setMeta = (name, content) => {
      let el = document.querySelector(`meta[name="${name}"]`);
      if (!el) { el = document.createElement("meta"); el.setAttribute("name", name); document.head.appendChild(el); }
      el.setAttribute("content", content);
    };
    setMeta(
      "description",
      "Meet the four AI specialists inside Zynthoro — Zyntha for content & SEO, Thoro for workflows, Zyona for growth, and Zynthoro Assist your always-on guide."
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
      <main data-testid="page-assistants">
        <section className="zy-section bg-white pb-0">
          <div className="zy-container max-w-4xl">
            <p className="zy-eyebrow mb-4">AI assistants</p>
            <h1 className="zy-h1">Four AI specialists that already know your company.</h1>
            <p className="zy-body mt-6 max-w-2xl">
              Not a chatbot. Not a copilot. Four purpose-built AIs — each with its own personality, expertise and
              access to your live business data. Ask, delegate, ship.
            </p>
          </div>
        </section>
        <Assistants />
        <Assist />
        <VoiceAISection />
      </main>
      <Footer />
    </PresaleDialogProvider>
  );
}
