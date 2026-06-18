import {
  CalendarClock,
  Timer,
  PackageSearch,
  ShoppingCart,
  Calculator,
  ReceiptEuro,
  KanbanSquare,
  Users,
  Workflow,
  Megaphone,
  MessagesSquare,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";
import { HOME } from "@/constants/testIds";

const domains = [
  { icon: CalendarClock, title: "Planning & Organisation", desc: "AI-assisted scheduling, goals and OKRs in one view." },
  { icon: Timer, title: "Time Tracking", desc: "Automatic time capture per project, client and task." },
  { icon: PackageSearch, title: "Purchase Administration", desc: "Supplier orders, approvals and inventory in sync." },
  { icon: ShoppingCart, title: "Sales Administration", desc: "Quotes, orders, customers and pipeline unified." },
  { icon: Calculator, title: "Accounting", desc: "Real-time ledger, VAT and reporting — EU-ready." },
  { icon: ReceiptEuro, title: "Invoicing & Finance", desc: "Send, chase and reconcile invoices automatically." },
  { icon: KanbanSquare, title: "Project Management", desc: "Plan, assign and ship with AI status summaries." },
  { icon: Users, title: "HR & Personnel", desc: "Contracts, leave, payroll and onboarding flows." },
  { icon: Workflow, title: "Operations & Processes", desc: "Map, automate and monitor every workflow." },
  { icon: Megaphone, title: "Marketing & Content", desc: "Campaigns, copy, video and visuals in one studio." },
  { icon: MessagesSquare, title: "Communication & Collaboration", desc: "Chat, meetings and docs — no more tab chaos." },
  { icon: ShieldCheck, title: "Compliance & Security", desc: "GDPR, audit trails and role-based access built-in." },
];

export default function Domains() {
  return (
    <section
      id="domains"
      data-testid={HOME.domains}
      className="zy-section"
      style={{ background: "var(--zy-grey-light)" }}
    >
      <div className="zy-container">
        <div className="max-w-3xl mx-auto text-center mb-16 zy-reveal">
          <p className="zy-eyebrow mb-4">The 12 Domains</p>
          <h2 className="zy-h2">Everything your business needs. In one place.</h2>
          <p className="zy-body mt-5">
            Twelve connected modules. One AI brain. Real-time data flowing between finance, ops, marketing and people.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {domains.map(({ icon: Icon, title, desc }, i) => (
            <div
              key={title}
              className="zy-domain-card zy-reveal"
              style={{ transitionDelay: `${(i % 4) * 60}ms` }}
              data-testid={`domain-card-${i + 1}`}
            >
              <span className="zy-domain-icon">
                <Icon size={20} />
              </span>
              <h3 className="zy-h3" style={{ fontSize: "1.05rem" }}>
                {title}
              </h3>
              <p className="mt-2 text-[14px] leading-relaxed text-[#555]">{desc}</p>
            </div>
          ))}
        </div>

        <div className="mt-14 text-center zy-reveal">
          <a href="#pricing" className="zy-link">
            Explore all 12 domains <ArrowRight size={16} />
          </a>
        </div>
      </div>
    </section>
  );
}
