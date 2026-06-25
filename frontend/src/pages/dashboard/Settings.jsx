import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Image as ImageIcon, Loader2, Trash2, Upload, Save, CreditCard } from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import ChangePlanDialog from "@/components/dashboard/ChangePlanDialog";

export default function Settings() {
  const { user, refresh } = useAuth();
  const fileRef = useRef(null);
  const [form, setForm] = useState({
    company_name: user?.company || "",
    company_country: user?.company_country || "",
    company_industry: user?.company_industry || "",
    company_website: user?.company_website || "",
    vat_number: user?.vat_number || "",
    address_line1: user?.address_line1 || "",
    postal_code: user?.postal_code || "",
    city: user?.city || "",
  });
  const [saving, setSaving] = useState(false);
  const [logoPreview, setLogoPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [changePlanOpen, setChangePlanOpen] = useState(false);

  // Handle Stripe Checkout return: ?checkout=success&session_id=… or ?checkout=cancelled
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("checkout");
    if (status === "success") {
      toast.success("Subscription updated. Your new plan is active.");
      refresh?.();
      window.history.replaceState({}, "", "/dashboard/settings");
    } else if (status === "cancelled") {
      toast.message("Checkout cancelled — no charges made.");
      window.history.replaceState({}, "", "/dashboard/settings");
    }
  }, [refresh]);

  const refreshLogo = () => {
    if (!user?.id) return;
    // Bust cache after upload/delete
    setLogoPreview(`${API}/account/logo?u=${encodeURIComponent(user.id)}&t=${Date.now()}`);
  };

  useEffect(() => {
    if (user?.has_company_logo) refreshLogo();
    else setLogoPreview(null);
    // eslint-disable-next-line
  }, [user?.has_company_logo]);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await axios.patch(`${API}/account/company`, form);
      await refresh();
      toast.success("Company details saved.");
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Could not save.");
    } finally {
      setSaving(false);
    }
  };

  const onLogo = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      toast.error("Logo too large (max 2 MB).");
      return;
    }
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await axios.post(`${API}/account/logo`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Logo uploaded.");
      await refresh();
      refreshLogo();
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const removeLogo = async () => {
    try {
      await axios.delete(`${API}/account/logo`);
      toast.success("Logo removed.");
      await refresh();
      setLogoPreview(null);
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Could not remove logo.");
    }
  };

  return (
    <div data-testid="settings-page" className="max-w-3xl">
      <p className="zy-eyebrow mb-2">Settings</p>
      <h1 className="text-[28px] font-bold tracking-tight">Company &amp; account</h1>
      <p className="text-[14px] text-[#555] mt-1">
        These details appear on invoices, contracts and documents your team and clients see.
      </p>

      {/* Logo */}
      <section className="mt-8 bg-white border border-[#eee] rounded-2xl p-6">
        <h2 className="text-[15px] font-semibold mb-4">Company logo</h2>
        <div className="flex items-center gap-5">
          <div
            className="w-24 h-24 rounded-xl border border-dashed flex items-center justify-center overflow-hidden bg-[#FAFAFB]"
            style={{ borderColor: "#ddd" }}
            data-testid="logo-preview"
          >
            {logoPreview ? (
              <img src={logoPreview} alt="Company logo" className="max-w-full max-h-full object-contain" />
            ) : (
              <ImageIcon size={26} className="text-[#aaa]" />
            )}
          </div>
          <div className="flex-1">
            <p className="text-[13.5px] text-[#555]">
              PNG, JPEG, SVG or WebP — up to 2 MB. Square or transparent backgrounds work best.
            </p>
            <div className="flex flex-wrap gap-2 mt-3">
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                className="zy-btn-primary disabled:opacity-70"
                data-testid="logo-upload-btn"
              >
                {uploading ? <><Loader2 size={14} className="animate-spin" /> Uploading…</> : <><Upload size={14} /> Upload new</>}
              </button>
              {user?.has_company_logo && (
                <button type="button" onClick={removeLogo} className="zy-btn-outline" data-testid="logo-remove-btn">
                  <Trash2 size={14} /> Remove
                </button>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/svg+xml,image/webp"
                onChange={onLogo}
                className="hidden"
                data-testid="logo-file-input"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Company details */}
      <form onSubmit={save} className="mt-6 bg-white border border-[#eee] rounded-2xl p-6 space-y-5">
        <h2 className="text-[15px] font-semibold">Company details</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Company name" value={form.company_name} onChange={(v) => update("company_name", v)} />
          <Field label="Website" value={form.company_website} onChange={(v) => update("company_website", v)} placeholder="https://" />
          <Field label="VAT number" value={form.vat_number} onChange={(v) => update("vat_number", v)} />
          <Field label="Industry" value={form.company_industry} onChange={(v) => update("company_industry", v)} />
          <Field label="Country" value={form.company_country} onChange={(v) => update("company_country", v)} />
          <Field label="City" value={form.city} onChange={(v) => update("city", v)} />
          <Field label="Address" value={form.address_line1} onChange={(v) => update("address_line1", v)} className="sm:col-span-2" />
          <Field label="Postal code" value={form.postal_code} onChange={(v) => update("postal_code", v)} />
        </div>
        <div className="pt-2">
          <button type="submit" disabled={saving} className="zy-btn-primary disabled:opacity-70" data-testid="settings-save">
            {saving ? <><Loader2 size={14} className="animate-spin" /> Saving…</> : <><Save size={14} /> Save changes</>}
          </button>
        </div>
      </form>

      <section id="billing" className="mt-6 bg-white border border-[#eee] rounded-2xl p-6" data-testid="billing-section">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <h2 className="text-[15px] font-semibold mb-1">Subscription &amp; Billing</h2>
            <p className="text-[13.5px] text-[#555]">
              You&apos;re on the <b>{user?.subscription_plan || "Presale"}</b> plan.
              {user?.founder_pricing && (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold" style={{ background: "rgba(212,175,55,0.18)", color: "#8a6e1d" }}>
                  Founder pricing active
                </span>
              )}
              {user?.is_founder && user?.billing_exempt && (
                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold" style={{ background: "rgba(34,197,94,0.12)", color: "#16a34a" }}>
                  Owner Unlimited · No billing
                </span>
              )}
            </p>
          </div>
          {!user?.billing_exempt && (
            <button
              type="button"
              onClick={() => setChangePlanOpen(true)}
              className="zy-btn-primary"
              data-testid="change-plan-btn"
            >
              <CreditCard size={14} /> Change plan
            </button>
          )}
        </div>
      </section>

      <ChangePlanDialog open={changePlanOpen} onOpenChange={setChangePlanOpen} />
    </div>
  );
}

function Field({ label, value, onChange, placeholder, className = "" }) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      <Label className="text-[12.5px] font-medium">{label}</Label>
      <Input value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  );
}
