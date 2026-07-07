import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useSearchParams } from "react-router-dom";
import { API, formatApiError } from "@/contexts/AuthContext";
import {
  Palette, ExternalLink, Loader2, Plus, Download, Unplug, RefreshCw, FileText, Presentation, PenTool,
} from "lucide-react";

const PRESETS = [
  { name: "presentation", label: "Presentation", icon: Presentation },
  { name: "doc", label: "Doc", icon: FileText },
  { name: "whiteboard", label: "Whiteboard", icon: PenTool },
];

export const CanvaPanel = () => {
  const [status, setStatus] = useState(null);
  const [designs, setDesigns] = useState([]);
  const [loadingDesigns, setLoadingDesigns] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [creating, setCreating] = useState(null);
  const [exporting, setExporting] = useState({});
  const [searchParams, setSearchParams] = useSearchParams();

  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/canva/status`);
      setStatus(data);
      return data;
    } catch {
      setStatus({ configured: false, connected: false });
      return null;
    }
  }, []);

  const fetchDesigns = useCallback(async () => {
    setLoadingDesigns(true);
    try {
      const { data } = await axios.get(`${API}/canva/designs`);
      setDesigns(data.items || []);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load Canva designs.");
    } finally {
      setLoadingDesigns(false);
    }
  }, []);

  useEffect(() => {
    const param = searchParams.get("canva");
    if (param === "connected") toast.success("Canva connected! Your designs are now available.");
    if (param === "error") toast.error("Canva connection failed. Please try again.");
    if (param) {
      searchParams.delete("canva");
      setSearchParams(searchParams, { replace: true });
    }
    fetchStatus().then((s) => {
      if (s?.connected) fetchDesigns();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connect = async () => {
    setConnecting(true);
    try {
      const { data } = await axios.get(`${API}/canva/connect`);
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't start Canva connection.");
      setConnecting(false);
    }
  };

  const disconnect = async () => {
    try {
      await axios.post(`${API}/canva/disconnect`);
      setDesigns([]);
      await fetchStatus();
      toast.success("Canva disconnected.");
    } catch {
      toast.error("Couldn't disconnect Canva.");
    }
  };

  const createDesign = async (preset) => {
    setCreating(preset);
    try {
      const { data } = await axios.post(`${API}/canva/designs`, { preset, title: "Zynthoro design" });
      const editUrl = data?.design?.urls?.edit_url;
      toast.success("Design created in Canva.");
      if (editUrl) window.open(editUrl, "_blank", "noopener");
      fetchDesigns();
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't create the design.");
    } finally {
      setCreating(null);
    }
  };

  const exportPdf = async (designId) => {
    setExporting((m) => ({ ...m, [designId]: true }));
    try {
      const { data } = await axios.post(`${API}/canva/designs/${designId}/export`, { format: "pdf" });
      const jobId = data?.job?.id;
      if (!jobId) throw new Error("no job");
      toast.info("Export started — preparing your PDF…");
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 2500));
        const { data: poll } = await axios.get(`${API}/canva/exports/${jobId}`);
        const job = poll?.job;
        if (job?.status === "success") {
          const url = job?.urls?.[0];
          if (url) window.open(url, "_blank", "noopener");
          toast.success("PDF export ready.");
          return;
        }
        if (job?.status === "failed") throw new Error("failed");
      }
      toast.error("Export is taking longer than expected — try again in a minute.");
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Export failed.");
    } finally {
      setExporting((m) => ({ ...m, [designId]: false }));
    }
  };

  if (!status) {
    return (
      <div className="flex items-center justify-center py-16 text-[#888]" data-testid="canva-loading">
        <Loader2 size={18} className="animate-spin mr-2" /> Loading Canva…
      </div>
    );
  }

  if (!status.configured) {
    return (
      <div className="bg-white border border-[#eee] rounded-2xl p-8 text-center" data-testid="canva-not-configured">
        <p className="text-[14px] text-[#555]">Canva integration isn't configured on this environment yet.</p>
      </div>
    );
  }

  if (!status.connected) {
    return (
      <div className="bg-white border border-[#eee] rounded-2xl p-8 sm:p-10" data-testid="canva-connect-card">
        <div className="flex items-start gap-4">
          <span className="inline-flex items-center justify-center w-12 h-12 rounded-xl shrink-0" style={{ background: "#EAF0FF" }}>
            <Palette size={22} style={{ color: "#1A4FFF" }} />
          </span>
          <div className="flex-1">
            <p className="zy-eyebrow mb-1" style={{ color: "#1A4FFF" }}>Design integration</p>
            <h3 className="text-[20px] font-bold tracking-tight">Connect your Canva account</h3>
            <p className="text-[14px] text-[#555] mt-1 max-w-xl">
              Create, browse and export Canva designs without leaving Zynthoro. Your designs stay in sync with your Canva workspace.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4 max-w-xl">
              {["Browse your designs", "One-click new design", "Export to PDF", "Open in Canva editor"].map((t) => (
                <div key={t} className="p-3 rounded-md bg-[#F4F6FB] text-[12.5px] font-medium text-center">{t}</div>
              ))}
            </div>
            <button onClick={connect} disabled={connecting} className="zy-btn-primary mt-5" data-testid="canva-connect-btn">
              {connecting ? <Loader2 size={14} className="animate-spin" /> : <Palette size={14} />}
              {connecting ? "Redirecting to Canva…" : "Connect Canva"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="canva-connected-panel">
      <div className="bg-white border border-[#eee] rounded-2xl p-5 flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center justify-center w-9 h-9 rounded-lg" style={{ background: "#EAF0FF" }}>
          <Palette size={16} style={{ color: "#1A4FFF" }} />
        </span>
        <div className="flex-1 min-w-[180px]">
          <p className="text-[13.5px] font-semibold">Canva connected</p>
          <p className="text-[12px] text-[#888]" data-testid="canva-account-name">
            {status.display_name ? `Signed in as ${status.display_name}` : "Account linked"}
          </p>
        </div>
        <button onClick={fetchDesigns} className="zy-btn-outline" data-testid="canva-refresh-btn">
          <RefreshCw size={13} /> Refresh
        </button>
        <button onClick={disconnect} className="zy-btn-outline text-[#B42318]" data-testid="canva-disconnect-btn">
          <Unplug size={13} /> Disconnect
        </button>
      </div>

      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <h3 className="text-[14px] font-semibold mb-3">Create a new design</h3>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => {
            const Icon = p.icon;
            return (
              <button
                key={p.name}
                onClick={() => createDesign(p.name)}
                disabled={!!creating}
                className="zy-btn-outline disabled:opacity-60"
                data-testid={`canva-create-${p.name}`}
              >
                {creating === p.name ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                {p.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[14px] font-semibold">Your Canva designs</h3>
          {loadingDesigns && <Loader2 size={14} className="animate-spin text-[#888]" />}
        </div>
        {designs.length === 0 && !loadingDesigns ? (
          <p className="text-[13px] text-[#888]" data-testid="canva-no-designs">
            No designs yet — create one above or design something in Canva and hit Refresh.
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4" data-testid="canva-designs-grid">
            {designs.map((d) => (
              <div key={d.id} className="border border-[#eee] rounded-xl overflow-hidden bg-white hover:border-[#1A4FFF] transition-colors">
                <div className="h-28 bg-[#F4F6FB] flex items-center justify-center overflow-hidden">
                  {d.thumbnail?.url ? (
                    <img src={d.thumbnail.url} alt={d.title || "Canva design"} className="w-full h-full object-cover" />
                  ) : (
                    <Palette size={22} className="text-[#ccc]" />
                  )}
                </div>
                <div className="p-3">
                  <p className="text-[12.5px] font-semibold truncate">{d.title || "Untitled design"}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <a
                      href={d.urls?.edit_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11.5px] font-medium text-[#1A4FFF] hover:underline"
                      data-testid={`canva-open-${d.id}`}
                    >
                      <ExternalLink size={11} /> Open
                    </a>
                    <button
                      onClick={() => exportPdf(d.id)}
                      disabled={!!exporting[d.id]}
                      className="ml-auto inline-flex items-center gap-1 text-[11.5px] font-medium text-[#555] hover:text-[#1A4FFF] disabled:opacity-60"
                      data-testid={`canva-export-${d.id}`}
                    >
                      {exporting[d.id] ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />}
                      PDF
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CanvaPanel;
