/**
 * AI Studio — generate photos (Nano Banana / Gemini 3 Flash Image) and
 * videos (fal.ai Kling 2.5 Pro) from a text prompt. Includes a one-click
 * "Publish to Meta" step for generated images.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Image as ImageIcon, Video, Sparkles, Loader2, Wand2,
  Download, Copy, Share2, Facebook, Instagram, Send,
  Link as LinkIcon, AlertCircle, Check, Clock, CalendarClock, X,
} from "lucide-react";
import { API, formatApiError } from "@/contexts/AuthContext";

// Default schedule = 1 hour from now, formatted for <input type="datetime-local">.
function defaultScheduleLocal() {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  const tzOffset = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
}

const PHOTO_PRESETS = [
  { label: "Cinematic hero shot of a modern SME office at golden hour", aspect: "16:9" },
  { label: "Isometric illustration of an AI assistant replacing 15 SaaS logos", aspect: "1:1" },
  { label: "Portrait of a European small-business founder, natural light, warm palette", aspect: "4:5" },
];

const VIDEO_PRESETS = [
  { label: "Slow cinematic dolly-in on an AI-native ERP dashboard rendered on a MacBook Pro", duration: "5", aspect: "16:9" },
  { label: "Aerial drone shot flying over a modern European city at sunrise, minimalist", duration: "10", aspect: "16:9" },
  { label: "Handheld product shot of a smartphone showing invoicing UI, macro lens", duration: "5", aspect: "9:16" },
];

const ASPECT_PHOTO = ["1:1", "16:9", "9:16", "4:5", "3:4"];
const ASPECT_VIDEO = ["16:9", "9:16", "1:1"];
const DURATIONS = ["5", "10"];

export default function AIStudio() {
  const [tab, setTab] = useState("photo");
  const [history, setHistory] = useState([]);
  const [metaPages, setMetaPages] = useState([]);
  const [metaConnected, setMetaConnected] = useState(false);

  const reloadHistory = async () => {
    try {
      const { data } = await axios.get(`${API}/ai-studio/history?limit=30`);
      setHistory(data.generations || []);
    } catch { /* noop */ }
  };
  const reloadMeta = async () => {
    try {
      const { data } = await axios.get(`${API}/oauth/meta/status`);
      setMetaConnected(!!data.connected);
      setMetaPages(data.pages || []);
    } catch { /* noop */ }
  };
  useEffect(() => { reloadHistory(); reloadMeta(); }, []);

  return (
    <div className="space-y-6" data-testid="ai-studio">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0A1628]">AI Studio</h1>
        <p className="text-[13.5px] text-[#0A1628]/60 mt-1.5">
          Generate on-brand photos and short videos from a text prompt. Publish straight to Facebook + Instagram.
        </p>
      </div>

      <div className="flex items-center gap-2 border-b border-[#0A162814]">
        <TabBtn active={tab === "photo"} onClick={() => setTab("photo")} icon={ImageIcon} label="Photo" testId="ai-studio-tab-photo" />
        <TabBtn active={tab === "video"} onClick={() => setTab("video")} icon={Video} label="Video" testId="ai-studio-tab-video" />
      </div>

      {tab === "photo" && (
        <PhotoTab
          onGenerated={reloadHistory}
          metaConnected={metaConnected}
          metaPages={metaPages}
        />
      )}
      {tab === "video" && <VideoTab onGenerated={reloadHistory} />}

      {history.length > 0 && (
        <div className="pt-6">
          <h2 className="text-[15px] font-semibold text-[#0A1628] mb-3">Recent generations</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="ai-studio-history">
            {history.map((g) => (
              <HistoryTile key={g.id} g={g} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- shared bits -----------------------------------------------------------
function TabBtn({ active, onClick, icon: Icon, label, testId }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className={`inline-flex items-center gap-2 px-4 py-2.5 text-[13px] font-semibold border-b-2 -mb-px transition-colors ${
        active
          ? "border-[var(--zy-blue)] text-[var(--zy-blue)]"
          : "border-transparent text-[#0A1628]/60 hover:text-[#0A1628]"
      }`}
    >
      <Icon size={14} /> {label}
    </button>
  );
}

// ---- Photo tab -------------------------------------------------------------
function PhotoTab({ onGenerated, metaConnected, metaPages }) {
  const [prompt, setPrompt] = useState(PHOTO_PRESETS[0].label);
  const [aspect, setAspect] = useState("16:9");
  const [busy, setBusy] = useState(false);
  const [gen, setGen] = useState(null); // last generation
  const [publishing, setPublishing] = useState(false);
  const [publishTargets, setPublishTargets] = useState({ fb: true, ig: true });
  const [selectedPage, setSelectedPage] = useState("");
  const [schedule, setSchedule] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(defaultScheduleLocal());
  const [queue, setQueue] = useState([]);

  const reloadQueue = async () => {
    try {
      const { data } = await axios.get(`${API}/oauth/meta/scheduled`);
      setQueue(data.posts || []);
    } catch { /* noop */ }
  };
  useEffect(() => { reloadQueue(); }, [metaConnected]);

  useEffect(() => {
    if (metaPages.length && !selectedPage) setSelectedPage(metaPages[0].page_id);
  }, [metaPages, selectedPage]);

  const generate = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setGen(null);
    try {
      const { data } = await axios.post(`${API}/ai-studio/photo/generate`, {
        prompt: prompt.trim(),
        aspect_ratio: aspect,
      });
      setGen(data);
      toast.success("Image generated.");
      onGenerated?.();
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Photo generation failed.");
    }
    setBusy(false);
  };

  const publish = async () => {
    if (!gen?.output_url || !selectedPage) return;
    setPublishing(true);
    try {
      if (schedule) {
        const iso = new Date(scheduledAt).toISOString();
        await axios.post(`${API}/oauth/meta/schedule`, {
          page_id: selectedPage,
          message: prompt.trim(),
          image_url: gen.output_url,
          target_fb: publishTargets.fb,
          target_ig: publishTargets.ig,
          scheduled_at: iso,
        });
        toast.success(`Scheduled for ${new Date(iso).toLocaleString()}.`);
        await reloadQueue();
      } else {
        const { data } = await axios.post(`${API}/oauth/meta/publish`, {
          page_id: selectedPage,
          message: prompt.trim(),
          image_url: gen.output_url,
          target_fb: publishTargets.fb,
          target_ig: publishTargets.ig,
        });
        toast.success(
          data.mode === "mock"
            ? "Published (mock mode — connect real Meta app to publish for real)."
            : `Published! FB=${data.fb_post_id || "—"} IG=${data.ig_post_id || "—"}`
        );
      }
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Publish failed.");
    }
    setPublishing(false);
  };

  const cancelScheduled = async (id) => {
    try {
      await axios.post(`${API}/oauth/meta/scheduled/${id}/cancel`);
      setQueue((q) => q.map((p) => (p.id === id ? { ...p, status: "cancelled" } : p)));
      toast.success("Scheduled post cancelled.");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Cancel failed.");
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="ai-studio-photo">
      {/* Prompt panel */}
      <div className="space-y-4">
        <PromptCard
          value={prompt}
          onChange={setPrompt}
          placeholder="Describe the image you want…"
          presets={PHOTO_PRESETS.map((p) => p.label)}
          onPreset={(v, i) => { setPrompt(v); setAspect(PHOTO_PRESETS[i].aspect); }}
          testId="ai-studio-photo-prompt"
        />

        <div className="flex items-center gap-3">
          <label className="text-[12.5px] font-semibold text-[#0A1628]">Aspect</label>
          <div className="flex gap-1.5">
            {ASPECT_PHOTO.map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAspect(a)}
                data-testid={`ai-studio-photo-aspect-${a}`}
                className={`rounded-full px-3 py-1 text-[12px] border transition-colors ${
                  aspect === a
                    ? "bg-[var(--zy-blue)] text-white border-[var(--zy-blue)]"
                    : "bg-white text-[#0A1628]/70 border-[#0A162814] hover:border-[var(--zy-blue)]/40"
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={generate}
          disabled={busy || !prompt.trim()}
          className="zy-btn-primary w-full sm:w-auto inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
          data-testid="ai-studio-photo-generate"
        >
          {busy ? (
            <><Loader2 size={14} className="animate-spin" /> Generating…</>
          ) : (
            <><Wand2 size={14} /> Generate image</>
          )}
        </button>
      </div>

      {/* Preview + Publish panel */}
      <div>
        <div
          className="relative rounded-2xl bg-[#F1F3F8] border border-[#0A162814] overflow-hidden flex items-center justify-center"
          style={{ minHeight: 320 }}
          data-testid="ai-studio-photo-preview"
        >
          {busy && (
            <div className="text-center text-[#0A1628]/50 py-16">
              <Loader2 size={26} className="animate-spin mx-auto mb-3" />
              <p className="text-[13px]">Nano Banana is painting…</p>
            </div>
          )}
          {!busy && !gen && (
            <div className="text-center text-[#0A1628]/40 py-16 px-6">
              <ImageIcon size={26} className="mx-auto mb-3" />
              <p className="text-[13px]">Your generated image will appear here.</p>
            </div>
          )}
          {gen?.output_url && (
            <img src={gen.output_url} alt="Generated" className="w-full h-auto max-h-[540px] object-contain" />
          )}
        </div>

        {gen?.output_url && (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-2 text-[12.5px]">
              <a
                href={gen.output_url}
                download
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-full border border-[#0A16281A] px-3 py-1.5 font-semibold text-[#0A1628] hover:bg-[#F7F8FA]"
                data-testid="ai-studio-photo-download"
              >
                <Download size={13} /> Download
              </a>
              <button
                type="button"
                onClick={() => { navigator.clipboard.writeText(gen.output_url); toast.success("URL copied"); }}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#0A16281A] px-3 py-1.5 font-semibold text-[#0A1628] hover:bg-[#F7F8FA]"
                data-testid="ai-studio-photo-copy-url"
              >
                <LinkIcon size={13} /> Copy URL
              </button>
            </div>

            <div className="rounded-xl border border-[#0A162814] p-4" data-testid="ai-studio-photo-publish">
              <div className="flex items-center gap-2 mb-3">
                <Share2 size={14} className="text-[#0A1628]/60" />
                <p className="text-[13px] font-semibold text-[#0A1628]">Publish to Meta</p>
              </div>

              {!metaConnected ? (
                <MetaConnectInline />
              ) : (
                <div className="space-y-3">
                  <select
                    value={selectedPage}
                    onChange={(e) => setSelectedPage(e.target.value)}
                    className="w-full text-[13px] px-3 py-2 border border-[#0A162814] rounded-md bg-white"
                    data-testid="ai-studio-publish-page-select"
                  >
                    {metaPages.map((p) => (
                      <option key={p.page_id} value={p.page_id}>
                        {p.page_name}{p.ig_account_id ? ` · @${p.ig_username || "ig"}` : ""}
                      </option>
                    ))}
                  </select>
                  <div className="flex items-center gap-4 text-[13px]">
                    <label className="inline-flex items-center gap-1.5">
                      <input type="checkbox" checked={publishTargets.fb} onChange={(e) => setPublishTargets((t) => ({ ...t, fb: e.target.checked }))} data-testid="ai-studio-publish-fb" />
                      <Facebook size={13} className="text-[#1877F2]" /> Facebook
                    </label>
                    <label className="inline-flex items-center gap-1.5">
                      <input type="checkbox" checked={publishTargets.ig} onChange={(e) => setPublishTargets((t) => ({ ...t, ig: e.target.checked }))} data-testid="ai-studio-publish-ig" />
                      <Instagram size={13} className="text-[#E1306C]" /> Instagram
                    </label>
                  </div>

                  <label
                    className="flex items-center gap-2 text-[13px] cursor-pointer select-none"
                    data-testid="ai-studio-schedule-toggle"
                  >
                    <input
                      type="checkbox"
                      checked={schedule}
                      onChange={(e) => setSchedule(e.target.checked)}
                    />
                    <CalendarClock size={14} className="text-[#0A1628]/60" />
                    <span className="text-[#0A1628]/80">Schedule for later</span>
                  </label>

                  {schedule && (
                    <div className="flex items-center gap-2" data-testid="ai-studio-schedule-picker">
                      <input
                        type="datetime-local"
                        value={scheduledAt}
                        onChange={(e) => setScheduledAt(e.target.value)}
                        min={defaultScheduleLocal()}
                        className="text-[13px] px-3 py-1.5 border border-[#0A162814] rounded-md bg-white"
                        data-testid="ai-studio-schedule-datetime"
                      />
                      <span className="text-[11.5px] text-[#0A1628]/50">
                        Your local time · runs on our server clock (UTC).
                      </span>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={publish}
                    disabled={publishing || (!publishTargets.fb && !publishTargets.ig)}
                    className="zy-btn-primary text-[13px] inline-flex items-center gap-1.5 disabled:opacity-50"
                    data-testid="ai-studio-publish-btn"
                  >
                    {publishing ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : schedule ? (
                      <CalendarClock size={14} />
                    ) : (
                      <Send size={14} />
                    )}
                    {schedule ? "Schedule post" : "Publish"}
                  </button>
                </div>
              )}
            </div>

            {queue.length > 0 && (
              <div
                className="rounded-xl border border-[#0A162814] p-4"
                data-testid="ai-studio-schedule-queue"
              >
                <div className="flex items-center gap-2 mb-3">
                  <CalendarClock size={14} className="text-[#0A1628]/60" />
                  <p className="text-[13px] font-semibold text-[#0A1628]">
                    Scheduled queue ({queue.filter((p) => p.status === "pending").length} pending)
                  </p>
                </div>
                <ul className="space-y-2">
                  {queue.slice(0, 8).map((p) => (
                    <li
                      key={p.id}
                      className="flex items-center justify-between gap-3 text-[12.5px] border border-[#0A162808] rounded-md px-2.5 py-1.5"
                      data-testid={`ai-studio-schedule-item-${p.id}`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="text-[#0A1628] truncate">
                          {p.message || "(no message)"}
                        </div>
                        <div className="text-[11.5px] text-[#0A1628]/55 mt-0.5">
                          {new Date(p.scheduled_at).toLocaleString()}
                          {p.target_fb && <span className="ml-1.5">· FB</span>}
                          {p.target_ig && <span className="ml-1.5">· IG</span>}
                        </div>
                      </div>
                      <StatusPill status={p.status} />
                      {p.status === "pending" && (
                        <button
                          type="button"
                          onClick={() => cancelScheduled(p.id)}
                          className="p-1 rounded-md text-[#B91C1C]/70 hover:text-[#B91C1C] hover:bg-[#FEE2E280]"
                          title="Cancel"
                          data-testid={`ai-studio-schedule-cancel-${p.id}`}
                        >
                          <X size={13} />
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Schedule status pill --------------------------------------------------
function StatusPill({ status }) {
  const cfg = {
    pending: { bg: "#FEF3C6", color: "#B45309", label: "Pending" },
    publishing: { bg: "#DBEAFE", color: "#1E40AF", label: "Publishing…" },
    published: { bg: "#D1FAE5", color: "#047857", label: "Published" },
    failed: { bg: "#FEE2E2", color: "#B91C1C", label: "Failed" },
    cancelled: { bg: "#F1F3F8", color: "#0A16288F", label: "Cancelled" },
  }[status] || { bg: "#F1F3F8", color: "#0A162880", label: status };
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider"
      style={{ background: cfg.bg, color: cfg.color }}
    >
      {cfg.label}
    </span>
  );
}

// ---- Video tab -------------------------------------------------------------
function VideoTab({ onGenerated }) {
  const [prompt, setPrompt] = useState(VIDEO_PRESETS[0].label);
  const [duration, setDuration] = useState("5");
  const [aspect, setAspect] = useState("16:9");
  const [busy, setBusy] = useState(false);
  const [gen, setGen] = useState(null);
  const [err, setErr] = useState(null);

  const generate = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setGen(null);
    setErr(null);
    try {
      const { data } = await axios.post(`${API}/ai-studio/video/generate`, {
        prompt: prompt.trim(),
        duration,
        aspect_ratio: aspect,
      });
      setGen(data);
      toast.success("Video generated.");
      onGenerated?.();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setErr(detail);
      toast.error(formatApiError(detail) || "Video generation failed.");
    }
    setBusy(false);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="ai-studio-video">
      <div className="space-y-4">
        <PromptCard
          value={prompt}
          onChange={setPrompt}
          placeholder="Describe the shot: subject, camera move, mood, style…"
          presets={VIDEO_PRESETS.map((p) => p.label)}
          onPreset={(v, i) => { setPrompt(v); setDuration(VIDEO_PRESETS[i].duration); setAspect(VIDEO_PRESETS[i].aspect); }}
          testId="ai-studio-video-prompt"
        />

        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-3">
            <label className="text-[12.5px] font-semibold text-[#0A1628]">Duration</label>
            <div className="flex gap-1.5">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDuration(d)}
                  data-testid={`ai-studio-video-duration-${d}`}
                  className={`rounded-full px-3 py-1 text-[12px] border transition-colors ${
                    duration === d
                      ? "bg-[var(--zy-blue)] text-white border-[var(--zy-blue)]"
                      : "bg-white text-[#0A1628]/70 border-[#0A162814] hover:border-[var(--zy-blue)]/40"
                  }`}
                >
                  {d}s
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-[12.5px] font-semibold text-[#0A1628]">Aspect</label>
            <div className="flex gap-1.5">
              {ASPECT_VIDEO.map((a) => (
                <button
                  key={a}
                  type="button"
                  onClick={() => setAspect(a)}
                  data-testid={`ai-studio-video-aspect-${a}`}
                  className={`rounded-full px-3 py-1 text-[12px] border transition-colors ${
                    aspect === a
                      ? "bg-[var(--zy-blue)] text-white border-[var(--zy-blue)]"
                      : "bg-white text-[#0A1628]/70 border-[#0A162814] hover:border-[var(--zy-blue)]/40"
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>
        </div>

        <p className="text-[11.5px] text-[#0A1628]/50">
          Model: <b>Kling 2.5 Pro</b> via fal.ai — expect 1–3 minutes per clip. Cost ~€0.35–0.70 per generation.
        </p>

        <button
          type="button"
          onClick={generate}
          disabled={busy || !prompt.trim()}
          className="zy-btn-primary w-full sm:w-auto inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
          data-testid="ai-studio-video-generate"
        >
          {busy ? (
            <><Loader2 size={14} className="animate-spin" /> Rendering (this can take a few minutes)…</>
          ) : (
            <><Sparkles size={14} /> Generate video</>
          )}
        </button>
      </div>

      <div>
        <div
          className="relative rounded-2xl bg-[#0A1628] border border-[#0A162814] overflow-hidden flex items-center justify-center"
          style={{ minHeight: 320 }}
          data-testid="ai-studio-video-preview"
        >
          {busy && (
            <div className="text-center text-white/70 py-16">
              <Loader2 size={26} className="animate-spin mx-auto mb-3" />
              <p className="text-[13px]">Kling is rendering your clip…</p>
              <p className="text-[11.5px] mt-1 opacity-70">Grab a coffee — this typically takes 1–3 min.</p>
            </div>
          )}
          {!busy && !gen && !err && (
            <div className="text-center text-white/40 py-16 px-6">
              <Video size={26} className="mx-auto mb-3" />
              <p className="text-[13px]">Your generated video will appear here.</p>
            </div>
          )}
          {err && (
            <div className="text-center text-white/85 py-14 px-6 max-w-md">
              <AlertCircle size={22} className="mx-auto mb-3 text-[#F87171]" />
              <p className="text-[13px] font-semibold">
                {typeof err === "object" && err?.code === "FAL_KEY_MISSING"
                  ? "Video generation isn't configured yet"
                  : "Generation failed"}
              </p>
              <p className="text-[12.5px] text-white/60 mt-1.5 leading-relaxed">
                {formatApiError(err) || "Try again in a moment, or contact support."}
              </p>
            </div>
          )}
          {gen?.output_url && (
            <video
              src={gen.output_url}
              controls
              className="w-full h-auto max-h-[540px]"
              data-testid="ai-studio-video-player"
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ---- reused: prompt card ---------------------------------------------------
function PromptCard({ value, onChange, placeholder, presets, onPreset, testId }) {
  const areaRef = useRef(null);
  return (
    <div className="rounded-2xl border border-[#0A162814] p-4 bg-white">
      <textarea
        ref={areaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={4}
        className="w-full text-[14px] leading-relaxed resize-none focus:outline-none placeholder:text-[#0A1628]/40"
        data-testid={testId}
      />
      <div className="mt-3 pt-3 border-t border-[#0A162808]">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[#0A1628]/45 mb-2">Try a preset</p>
        <div className="flex flex-wrap gap-1.5">
          {presets.map((p, i) => (
            <button
              key={p}
              type="button"
              onClick={() => onPreset(p, i)}
              className="text-left text-[12px] rounded-md px-2.5 py-1.5 bg-[#F7F8FA] hover:bg-[#1A4FFF]/[0.06] text-[#0A1628]/80 hover:text-[var(--zy-blue)]"
              data-testid={`${testId}-preset-${i}`}
            >
              {p.length > 55 ? p.slice(0, 55) + "…" : p}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---- Meta "connect" inline banner ------------------------------------------
function MetaConnectInline() {
  const [busy, setBusy] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const connect = async () => {
    setBusy(true);
    setStatusMsg("");
    try {
      const { data } = await axios.get(`${API}/oauth/meta/start`);
      if (data.mode === "mock") {
        // In mock mode, hit the callback directly server-side.
        const url = new URL(data.authorize_url);
        const code = url.searchParams.get("code");
        const state = url.searchParams.get("state");
        await axios.get(`${API}/oauth/meta/callback`, { params: { code, state } });
        setStatusMsg("Connected (demo mode).");
        toast.success("Connected to Meta (demo mode).");
        setTimeout(() => window.location.reload(), 1200);
      } else {
        window.location.href = data.authorize_url;
      }
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't start Meta connect.");
    }
    setBusy(false);
  };
  return (
    <div className="rounded-lg bg-[#F7F8FA] p-3 text-[13px] text-[#0A1628]/75 flex items-center justify-between gap-3">
      <span>Connect a Facebook Page (and linked Instagram Business account) to publish.</span>
      <button
        type="button"
        onClick={connect}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-full bg-[var(--zy-blue)] text-white px-3.5 py-1.5 text-[12.5px] font-semibold hover:opacity-90 disabled:opacity-50"
        data-testid="ai-studio-meta-connect"
      >
        {busy ? <Loader2 size={13} className="animate-spin" /> : <Facebook size={13} />}
        Connect Meta
      </button>
      {statusMsg && <span className="text-[#047857] inline-flex items-center gap-1"><Check size={12} />{statusMsg}</span>}
    </div>
  );
}

// ---- History tile ----------------------------------------------------------
function HistoryTile({ g }) {
  return (
    <div
      className="rounded-xl overflow-hidden border border-[#0A162814] bg-white"
      data-testid={`ai-studio-history-${g.id}`}
    >
      <div className="bg-[#F1F3F8]" style={{ aspectRatio: "1 / 1" }}>
        {g.kind === "video" && g.output_url ? (
          <video src={g.output_url} className="w-full h-full object-cover" muted />
        ) : g.output_url ? (
          <img src={g.output_url} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-[#0A1628]/30">
            {g.status === "in_progress" ? <Loader2 size={18} className="animate-spin" /> : g.kind}
          </div>
        )}
      </div>
      <div className="p-2 flex items-center justify-between text-[11px] text-[#0A1628]/60">
        <span className="inline-flex items-center gap-1">
          {g.kind === "video" ? <Video size={11} /> : <ImageIcon size={11} />}
          {g.kind}
        </span>
        <span>{g.aspect_ratio}</span>
      </div>
    </div>
  );
}
