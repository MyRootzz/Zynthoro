import { ArrowRight } from "lucide-react";

const ASSISTANTS = [
  {
    key: "zyntha",
    name: "Zyntha",
    specialty: "Content & SEO Specialist",
    personality: "Creative, energetic, inspiring.",
    accent: "#1A4FFF",
    accentSoft: "rgba(26,79,255,0.12)",
    image: "/assistants/zyntha.png",
  },
  {
    key: "thoro",
    name: "Thoro",
    specialty: "Builder & Workflow Specialist",
    personality: "Technical, precise, results-driven.",
    accent: "#1A4FFF",
    accentSoft: "rgba(26,79,255,0.12)",
    image: "/assistants/thoro.png",
  },
  {
    key: "zyona",
    name: "Zyona",
    specialty: "Business & Growth Specialist",
    personality: "Strategic, decisive, business-focused.",
    accent: "#D4AF37",
    accentSoft: "rgba(212,175,55,0.16)",
    image: "/assistants/zyona.png",
  },
];

export default function Assistants() {
  return (
    <section
      id="assistants"
      data-testid="section-assistants"
      className="zy-section bg-white"
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-16 zy-reveal">
          <p className="zy-eyebrow mb-4">AI assistants</p>
          <h2 className="zy-h2">Meet your AI assistants</h2>
          <p className="zy-body mt-5">
            Three specialists. One platform. Always on.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
          {ASSISTANTS.map((a, i) => (
            <article
              key={a.key}
              data-testid={`assistant-card-${a.key}`}
              className="zy-reveal bg-white border border-[#eee] rounded-2xl overflow-hidden flex flex-col transition-all"
              style={{ transitionDelay: `${i * 90}ms` }}
            >
              <div
                className="w-full"
                style={{
                  aspectRatio: "1 / 1",
                  background: `radial-gradient(circle at 50% 35%, ${a.accentSoft} 0%, rgba(255,255,255,0) 70%), #FAFAFB`,
                  borderBottom: `1px solid #eee`,
                }}
              >
                <img
                  src={a.image}
                  alt={`${a.name} — ${a.specialty}`}
                  loading="lazy"
                  className="w-full h-full object-cover"
                  style={{ objectPosition: "center top" }}
                />
              </div>

              <div className="p-6 flex flex-col flex-1">
                <h3 className="text-[20px] font-bold tracking-tight text-black">{a.name}</h3>
                <p
                  className="text-[12px] font-semibold tracking-[0.12em] uppercase mt-1.5"
                  style={{ color: a.accent }}
                >
                  {a.specialty}
                </p>
                <p className="text-[14px] text-[#555] mt-3 leading-relaxed flex-1">
                  {a.personality}
                </p>

                <a
                  href="/login"
                  data-testid={`assistant-chat-${a.key}`}
                  className="mt-5 inline-flex items-center gap-1.5 text-[13.5px] font-semibold"
                  style={{ color: a.accent }}
                >
                  Chat with {a.name} <ArrowRight size={14} />
                </a>
              </div>
            </article>
          ))}
        </div>

        <p className="mt-12 text-center text-[12.5px] text-[#777]">
          All three assistants run on Claude Sonnet 4.5 via the Anthropic API.
        </p>
      </div>
    </section>
  );
}
