/**
 * Brief 4-assistant grid for the slim homepage. Full detail lives at /assistants.
 * The four assistants: Zyntha (content/SEO), Thoro (workflows/builder),
 * Zyona (business/growth), Zynthoro Assist (always-on guide).
 */
import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";

const BRIEF = [
  {
    key: "zyntha",
    name: "Zyntha",
    role: "Content & SEO",
    tag: "Creative, energetic.",
    image: "/assistants/zyntha.png",
    accent: "#1A4FFF",
  },
  {
    key: "thoro",
    name: "Thoro",
    role: "Builder & Workflows",
    tag: "Technical, precise.",
    image: "/assistants/thoro.png",
    accent: "#1A4FFF",
  },
  {
    key: "zyona",
    name: "Zyona",
    role: "Business & Growth",
    tag: "Strategic, decisive.",
    image: "/assistants/zyona.png",
    accent: "#D4AF37",
  },
  {
    key: "assist",
    name: "Zynthoro Assist",
    role: "Your 24/7 platform guide",
    tag: "Always on, everywhere in the app.",
    icon: Sparkles,
    accent: "#1A4FFF",
  },
];

export default function HomeAssistantsBrief() {
  return (
    <section
      data-testid="home-assistants-brief"
      className="zy-section bg-[#F7F8FA]"
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-12 zy-reveal">
          <p className="zy-eyebrow mb-4">AI assistants</p>
          <h2 className="zy-h2">Four specialists. One platform.</h2>
          <p className="zy-body mt-5">
            Purpose-built AIs that already know your data. No prompt engineering required.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {BRIEF.map((a, i) => {
            const Icon = a.icon;
            return (
              <article
                key={a.key}
                data-testid={`home-assistant-brief-${a.key}`}
                className="zy-reveal bg-white rounded-2xl border border-[#0A162814] p-5 flex flex-col transition-all hover:shadow-[0_18px_44px_-24px_rgba(10,22,40,0.25)]"
                style={{ transitionDelay: `${i * 70}ms` }}
              >
                <div
                  className="w-14 h-14 rounded-2xl mb-4 flex items-center justify-center overflow-hidden"
                  style={{ background: `${a.accent}14` }}
                >
                  {Icon ? (
                    <Icon size={26} style={{ color: a.accent }} />
                  ) : (
                    <img
                      src={a.image}
                      alt={a.name}
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
                <h3 className="text-[17px] font-semibold text-[#0A1628]">{a.name}</h3>
                <p className="text-[13px] mt-0.5" style={{ color: a.accent }}>{a.role}</p>
                <p className="text-[13.5px] text-[#0A1628]/65 mt-2">{a.tag}</p>
              </article>
            );
          })}
        </div>

        <div className="mt-10 flex justify-center zy-reveal">
          <Link
            to="/assistants"
            data-testid="home-assistants-brief-cta"
            className="inline-flex items-center gap-2 rounded-full border border-[#0A162820] px-5 py-2.5 text-[14px] font-semibold text-[#0A1628] bg-white hover:bg-[#F7F8FA] transition-colors"
          >
            Explore the assistants <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </section>
  );
}
