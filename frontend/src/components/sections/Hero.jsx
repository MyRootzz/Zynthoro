import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Play } from "lucide-react";
import { HOME } from "@/constants/testIds";

// Zynthoro product walkthrough on YouTube. Clicking the thumbnail opens
// the video on YouTube in a new tab (we don't embed to avoid iframe
// policy restrictions).
const DEMO_VIDEO_URL =
  process.env.REACT_APP_DEMO_VIDEO_URL ||
  "https://www.youtube.com/watch?v=_5psEgtULpg";
const DEMO_VIDEO_ID = "_5psEgtULpg";
const YT_THUMB_MAXRES = `https://img.youtube.com/vi/${DEMO_VIDEO_ID}/maxresdefault.jpg`;
const YT_THUMB_HQ = `https://img.youtube.com/vi/${DEMO_VIDEO_ID}/hqdefault.jpg`;

// VideoObject JSON-LD — helps Google surface the demo as a rich video
// snippet on the SERP. Upload date + duration can be overridden via env
// (ISO 8601, e.g. PT2M30S). Safe defaults are used when unset so the
// schema is always complete.
const VIDEO_UPLOAD_DATE =
  process.env.REACT_APP_DEMO_VIDEO_UPLOAD_DATE || "2026-06-25T00:00:00+02:00";
const VIDEO_DURATION =
  process.env.REACT_APP_DEMO_VIDEO_DURATION || "PT2M20S";

export default function Hero() {
  const [thumbSrc, setThumbSrc] = useState(YT_THUMB_MAXRES);

  // Inject VideoObject JSON-LD on mount, remove on unmount.
  useEffect(() => {
    const id = "home-hero-video-jsonld";
    let tag = document.getElementById(id);
    if (!tag) {
      tag = document.createElement("script");
      tag.type = "application/ld+json";
      tag.id = id;
      document.head.appendChild(tag);
    }
    tag.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "VideoObject",
      name: "Zynthoro — Product Demo",
      description:
        "A 2-minute walkthrough of Zynthoro, the AI-native ERP for European SMEs. See how four AI specialists — Zyntha, Thoro, Zyona and Zynthoro Assist — replace 8–15 disconnected business tools with one platform.",
      thumbnailUrl: [YT_THUMB_MAXRES, YT_THUMB_HQ],
      uploadDate: VIDEO_UPLOAD_DATE,
      duration: VIDEO_DURATION,
      contentUrl: DEMO_VIDEO_URL,
      embedUrl: `https://www.youtube.com/embed/${DEMO_VIDEO_ID}`,
      publisher: {
        "@type": "Organization",
        name: "Zynthoro",
        logo: {
          "@type": "ImageObject",
          url: "https://zynthoro.ai/logo.png",
        },
      },
    });
    return () => {
      document.getElementById(id)?.remove();
    };
  }, []);

  return (
    <section
      id="top"
      data-testid={HOME.hero}
      className="relative overflow-hidden"
      style={{ paddingTop: 140, paddingBottom: 140 }}
    >
      <div className="zy-hero-bg" aria-hidden="true">
        <div className="zy-hero-grid" />
        <div className="zy-hero-orb zy-hero-orb-a" />
        <div className="zy-hero-orb zy-hero-orb-b" />
      </div>

      <div className="zy-container relative">
        <div className="max-w-4xl mx-auto text-center">
          <div className="zy-badge zy-reveal" style={{ transitionDelay: "0ms" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-[#1A4FFF]" />
            Powered by Anthropic Claude AI
          </div>

          <h1
            data-testid={HOME.heroHeadline}
            className="zy-h1 mt-6 zy-reveal"
            style={{ transitionDelay: "80ms" }}
          >
            The Next-Gen <span style={{ color: "var(--zy-blue)" }}>AI ERP</span> Ecosystem
          </h1>

          <p
            data-testid={HOME.heroSubheadline}
            className="zy-body mt-7 max-w-2xl mx-auto zy-reveal"
            style={{ transitionDelay: "160ms" }}
          >
            One platform. One AI. One truth. Replace 15+ tools with Zynthoro.
          </p>

          <div
            className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 zy-reveal"
            style={{ transitionDelay: "240ms" }}
          >
            <Link
              to="/signup?trial=1"
              data-testid={HOME.heroPrimaryCta}
              className="zy-btn-primary"
            >
              Start free 24h trial
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/signup"
              data-testid="hero-cta-get-started"
              className="zy-btn-outline"
            >
              Get started
            </Link>
          </div>

          <p className="mt-4 text-[13px] text-[#888] zy-reveal" style={{ transitionDelay: "300ms" }}>
            No credit card · Cancel anytime · Full AI access for 24 hours
          </p>
        </div>

        {/* YouTube demo thumbnail — opens the walkthrough on YouTube in a
            new tab. We use the maxres thumbnail with an onError fallback
            to hqdefault (guaranteed to exist for any public video). */}
        <div
          className="mt-16 max-w-3xl mx-auto zy-reveal"
          style={{ transitionDelay: "400ms" }}
        >
          <a
            href={DEMO_VIDEO_URL}
            target="_blank"
            rel="noopener noreferrer"
            data-testid={HOME.heroSecondaryCta}
            aria-label="Watch the Zynthoro product demo on YouTube"
            className="group relative block rounded-2xl overflow-hidden bg-[#0A1628] shadow-[0_30px_80px_-30px_rgba(26,79,255,0.45)] ring-1 ring-black/5 hover:shadow-[0_35px_90px_-25px_rgba(26,79,255,0.6)] transition-shadow duration-300"
            style={{ aspectRatio: "16 / 9" }}
          >
            <img
              src={thumbSrc}
              alt="Zynthoro product demo — watch on YouTube"
              loading="lazy"
              onError={() => {
                if (thumbSrc !== YT_THUMB_HQ) setThumbSrc(YT_THUMB_HQ);
              }}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
            />

            {/* Subtle dark scrim so the play button pops on any thumbnail */}
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-gradient-to-t from-black/40 via-black/10 to-transparent group-hover:from-black/50 transition-colors duration-300"
            />

            {/* Play button overlay */}
            <div className="absolute inset-0 flex items-center justify-center">
              <span
                className="flex items-center justify-center rounded-full bg-white/95 shadow-2xl transition-transform duration-300 group-hover:scale-110"
                style={{ width: 84, height: 84 }}
              >
                <Play
                  size={34}
                  strokeWidth={0}
                  fill="#1A4FFF"
                  style={{ marginLeft: 4 }}
                />
              </span>
            </div>

            {/* Bottom caption bar */}
            <div className="absolute bottom-0 left-0 right-0 p-5 flex items-center justify-between text-white">
              <div className="flex items-center gap-3">
                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wider"
                  style={{ background: "rgba(255,255,255,0.14)", backdropFilter: "blur(6px)" }}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#D4AF37]" />
                  Product demo
                </span>
                <span className="text-[13px] text-white/85 hidden sm:inline">
                  Watch the 2-minute Zynthoro walkthrough
                </span>
              </div>
              <span className="text-[12px] text-white/70 hidden sm:inline">
                Opens on YouTube ↗
              </span>
            </div>
          </a>
        </div>
      </div>
    </section>
  );
}
