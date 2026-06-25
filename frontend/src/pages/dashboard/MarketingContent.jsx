import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import UpgradeLock from "@/components/dashboard/UpgradeLock";
import { planAtLeast, PLAN_BY_KEY } from "@/lib/planCatalog";
import {
  Facebook, Instagram, Linkedin, Youtube, Twitter, Music2,
  Image as ImageIcon, Video, Calendar, BarChart3, Users, Mail, Sparkles,
  Plus, Lock,
} from "lucide-react";
import { Link } from "react-router-dom";

const PLATFORMS = [
  { id: "facebook", name: "Facebook", icon: Facebook, color: "#1877F2", tier: "Starter" },
  { id: "instagram", name: "Instagram", icon: Instagram, color: "#E4405F", tier: "Starter" },
  { id: "linkedin", name: "LinkedIn", icon: Linkedin, color: "#0A66C2", tier: "Creator" },
  { id: "tiktok", name: "TikTok", icon: Music2, color: "#000000", tier: "Creator" },
  { id: "x", name: "X", icon: Twitter, color: "#000000", tier: "Creator" },
  { id: "youtube", name: "YouTube", icon: Youtube, color: "#FF0000", tier: "Creator" },
];

const TABS = [
  { id: "compose", label: "Compose" },
  { id: "calendar", label: "Calendar" },
  { id: "photo", label: "Photo Studio" },
  { id: "video", label: "Video Studio" },
  { id: "campaigns", label: "Email Campaigns" },
  { id: "analytics", label: "Analytics" },
  { id: "clients", label: "Multi-client" },
];

export default function MarketingContent() {
  const { user } = useAuth();
  const plan = user?.subscription_plan?.startsWith("Enterprise")
    ? "Enterprise"
    : user?.subscription_plan || "Starter";
  const [tab, setTab] = useState("compose");

  const canStarter = planAtLeast(plan, "Starter");
  const canCreator = planAtLeast(plan, "Creator");
  const canBusiness = planAtLeast(plan, "Business");
  const canAgency = planAtLeast(plan, "Agency");

  return (
    <div data-testid="marketing-content-page" className="max-w-6xl">
      <p className="zy-eyebrow mb-2">Marketing & Content</p>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-[26px] sm:text-[28px] font-bold tracking-tight">Social Media Studio</h1>
          <p className="text-[14px] text-[#555] mt-1">
            Publish, schedule and design across every platform — powered by Zyntha.
          </p>
        </div>
        <div className="text-[12.5px] text-[#666]">
          Plan: <span className="font-semibold text-black">{plan}</span>
        </div>
      </div>

      {/* Connected platforms */}
      <section className="mt-6 bg-white border border-[#eee] rounded-2xl p-5 sm:p-6">
        <div className="flex items-center justify-between mb-4 gap-2">
          <h2 className="text-[15px] font-semibold">Connected accounts</h2>
          <span className="text-[12px] text-[#888]">
            {canCreator ? "All platforms unlocked" : `Starter: 2 platforms (FB + IG)`}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {PLATFORMS.map((p) => {
            const Icon = p.icon;
            const locked = p.tier === "Creator" && !canCreator;
            return (
              <button
                key={p.id}
                disabled={locked}
                data-testid={`platform-${p.id}`}
                className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border transition-colors ${
                  locked
                    ? "border-[#eee] bg-[#FAFAFB] cursor-not-allowed"
                    : "border-[#eee] hover:border-[#1A4FFF] hover:bg-[#F4F6FB]"
                }`}
              >
                {locked && (
                  <span className="absolute top-1.5 right-1.5">
                    <Lock size={11} className="text-[#aaa]" />
                  </span>
                )}
                <Icon size={20} style={{ color: locked ? "#bbb" : p.color }} />
                <span className={`text-[12px] font-medium ${locked ? "text-[#aaa]" : "text-[#333]"}`}>
                  {p.name}
                </span>
                <span className={`text-[10px] uppercase tracking-wider ${locked ? "text-[#bbb]" : "text-[#888]"}`}>
                  {locked ? p.tier + "+" : "Connect"}
                </span>
              </button>
            );
          })}
        </div>
        {!canCreator && (
          <div className="mt-4">
            <UpgradeLock requiredPlan="Creator" feature="Connect all 6 platforms" compact />
          </div>
        )}
      </section>

      {/* Tabs */}
      <nav className="mt-8 flex flex-wrap gap-1 border-b border-[#eee]">
        {TABS.map((t) => {
          const lock =
            (t.id === "photo" && !canStarter) ||
            false;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`mc-tab-${t.id}`}
              className={`px-3 sm:px-4 py-2.5 text-[13.5px] font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? "border-[#1A4FFF] text-[#1A4FFF]"
                  : "border-transparent text-[#666] hover:text-black"
              } ${lock ? "opacity-60" : ""}`}
            >
              {t.label}
            </button>
          );
        })}
      </nav>

      <div className="mt-6">
        {tab === "compose" && <ComposePanel canCreator={canCreator} />}
        {tab === "calendar" && (
          canCreator
            ? <CalendarPanel />
            : <UpgradeLock requiredPlan="Creator" feature="Content calendar & auto-scheduler" />
        )}
        {tab === "photo" && <PhotoPanel canCreator={canCreator} />}
        {tab === "video" && <VideoPanel canCreator={canCreator} />}
        {tab === "campaigns" && (
          canBusiness
            ? <ComingSoon title="AI Email Campaigns" desc="Drag-and-drop builder, audience segmentation and lead scoring." />
            : <UpgradeLock requiredPlan="Business" feature="AI Email Campaigns & Lead Scoring" />
        )}
        {tab === "analytics" && (
          canBusiness
            ? <ComingSoon title="Post Analytics" desc="Reach, likes, clicks and AI-suggested next actions per post." />
            : <UpgradeLock requiredPlan="Business" feature="Post Analytics" />
        )}
        {tab === "clients" && (
          canAgency
            ? <ComingSoon title="Multi-client Workspaces" desc="Manage social for multiple clients, approval workflows and white-label reports." />
            : <UpgradeLock requiredPlan="Agency" feature="Multi-client Social Management" />
        )}
      </div>
    </div>
  );
}

function ComposePanel({ canCreator }) {
  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={15} style={{ color: "#1A4FFF" }} />
          <h3 className="text-[14px] font-semibold">Create a post</h3>
          {canCreator && (
            <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-semibold text-[#1A4FFF] bg-[#EAF0FF] px-2 py-0.5 rounded-full">
              Zyntha caption AI
            </span>
          )}
        </div>
        <textarea
          rows={5}
          placeholder="What do you want to share today?"
          data-testid="mc-compose-textarea"
          className="w-full p-3 border border-[#eee] rounded-md text-[14px] focus:outline-none focus:border-[#1A4FFF] resize-y"
        />
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <button className="zy-btn-outline" data-testid="mc-add-photo">
            <ImageIcon size={14} /> Add photo
          </button>
          <button
            disabled={!canCreator}
            className={`zy-btn-outline ${!canCreator ? "opacity-50 cursor-not-allowed" : ""}`}
            data-testid="mc-add-video"
          >
            <Video size={14} /> Add video
            {!canCreator && <Lock size={11} className="ml-1" />}
          </button>
          <button
            disabled={!canCreator}
            className={`zy-btn-outline ${!canCreator ? "opacity-50 cursor-not-allowed" : ""}`}
            data-testid="mc-schedule"
          >
            <Calendar size={14} /> Schedule
            {!canCreator && <Lock size={11} className="ml-1" />}
          </button>
          <button className="zy-btn-primary ml-auto" data-testid="mc-publish">
            Publish now
          </button>
        </div>
      </div>
      {!canCreator && (
        <UpgradeLock
          requiredPlan="Creator"
          feature="AI captions, video uploads & scheduling"
          compact
        />
      )}
    </div>
  );
}

function CalendarPanel() {
  return (
    <ComingSoon
      title="Content Calendar"
      desc="Drag-and-drop weekly view. Auto-schedule across all connected platforms with Zyntha-optimised time slots."
    />
  );
}

function PhotoPanel({ canCreator }) {
  const basicTools = ["Resize", "Crop", "Filters", "Basic enhance"];
  const proTools = [
    "Background removal",
    "Object removal",
    "AI recolor",
    "AI enhance",
    "Sky replacement",
    "Skin retouch",
    "Smart filters",
    "Style transfer",
  ];
  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <h3 className="text-[14px] font-semibold mb-3">Basic photo tools</h3>
        <div className="flex flex-wrap gap-2">
          {basicTools.map((t) => (
            <span
              key={t}
              className="px-3 py-1.5 text-[12.5px] font-medium rounded-full border border-[#eee] text-[#444] bg-white"
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {canCreator ? (
        <div className="bg-white border border-[#eee] rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={15} style={{ color: "#1A4FFF" }} />
            <h3 className="text-[14px] font-semibold">AI Photo Suite</h3>
            <span className="ml-auto text-[11px] text-[#888]">PicsArt-level — included</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {proTools.map((t) => (
              <div key={t} className="p-3 rounded-md bg-[#F4F6FB] text-[12.5px] font-medium text-center">
                {t}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <UpgradeLock requiredPlan="Creator" feature="Full AI Photo Suite (PicsArt-level)" />
      )}
    </div>
  );
}

function VideoPanel({ canCreator }) {
  const basic = ["Trim", "Captions", "Simple templates"];
  const pro = [
    "AI short-form video",
    "AI voiceovers",
    "B-roll auto-fill",
    "Auto-captions per language",
    "AI templates",
    "Style transfer",
    "Background blur",
    "Multi-clip editor",
  ];
  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <h3 className="text-[14px] font-semibold mb-3">Basic video tools</h3>
        <div className="flex flex-wrap gap-2">
          {basic.map((t) => (
            <span
              key={t}
              className="px-3 py-1.5 text-[12.5px] font-medium rounded-full border border-[#eee] text-[#444] bg-white"
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {canCreator ? (
        <div className="bg-white border border-[#eee] rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={15} style={{ color: "#1A4FFF" }} />
            <h3 className="text-[14px] font-semibold">AI Video Suite</h3>
            <span className="ml-auto text-[11px] text-[#888]">CapCut-level — included</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {pro.map((t) => (
              <div key={t} className="p-3 rounded-md bg-[#F4F6FB] text-[12.5px] font-medium text-center">
                {t}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <UpgradeLock requiredPlan="Creator" feature="Full AI Video Suite (CapCut-level)" />
      )}
    </div>
  );
}

function ComingSoon({ title, desc }) {
  return (
    <div className="bg-white border border-[#eee] rounded-2xl p-8 text-center" data-testid="mc-coming-soon">
      <p className="zy-eyebrow mb-2" style={{ color: "#1A4FFF" }}>Coming soon</p>
      <h3 className="text-[20px] font-bold tracking-tight">{title}</h3>
      <p className="text-[14px] text-[#555] mt-2 max-w-md mx-auto">{desc}</p>
    </div>
  );
}
