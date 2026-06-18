import { Wallet, Zap, BrainCircuit } from "lucide-react";
import { HOME } from "@/constants/testIds";

const items = [
  {
    icon: Wallet,
    title: "€10,000–€35,000/mo",
    body: "The average SME spends this much on separate tools across finance, marketing, HR, content and ops.",
  },
  {
    icon: Zap,
    title: "From €499/month",
    body: "Zynthoro replaces all of them — finance, ops, marketing, content, HR — in one connected workspace.",
  },
  {
    icon: BrainCircuit,
    title: "Anthropic Claude AI",
    body: "Powered by the world's most trusted enterprise AI. Selected for the Claude for Startups program.",
  },
];

export default function WhyZynthoro() {
  return (
    <section id="why" data-testid={HOME.why} className="zy-section bg-white">
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-16 zy-reveal">
          <p className="zy-eyebrow mb-4">Why Zynthoro</p>
          <h2 className="zy-h2">
            Stop paying for 15 tools.<br className="hidden md:block" /> Start using one.
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-10">
          {items.map(({ icon: Icon, title, body }, i) => (
            <div
              key={title}
              className="zy-reveal"
              style={{ transitionDelay: `${i * 100}ms` }}
            >
              <div className="zy-domain-icon" style={{ width: 52, height: 52 }}>
                <Icon size={22} />
              </div>
              <h3 className="zy-h3 mt-1 mb-3">{title}</h3>
              <p className="zy-body" style={{ fontSize: "1rem" }}>
                {body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
