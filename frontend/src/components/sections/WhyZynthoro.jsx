import { Workflow, Zap, ShieldCheck } from "lucide-react";
import { HOME } from "@/constants/testIds";

const items = [
  {
    icon: Workflow,
    title: "One platform, zero chaos",
    body: "Twelve business domains, one connected workspace. No more juggling 15 tools that don't talk to each other.",
  },
  {
    icon: Zap,
    title: "From €499/month",
    body: "Replace €10,000–€35,000/month of separate tools — finance, ops, marketing, content, HR — with a single subscription.",
  },
  {
    icon: ShieldCheck,
    title: "Your data, your control",
    body: "EU-hosted, GDPR-ready, audit trails and role-based access built in from day one. Compliance isn't an add-on.",
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
