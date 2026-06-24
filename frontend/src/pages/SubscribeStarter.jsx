import { useState, useRef } from "react";
import axios from "axios";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Upload, FileCheck2, FileX2, ShieldCheck, ArrowRight, ArrowLeft,
  Loader2, CheckCircle2, Sparkles, BadgeCheck,
} from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { ZyLogo } from "@/components/ZyLogo";

const PACKAGES = {
  starter_founder: { label: "Founder pricing", priceLabel: "€99/mo · 3 months · then €499/mo" },
  starter_standard: { label: "Standard pricing", priceLabel: "€499/mo" },
};

export default function SubscribeStarter() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [step, setStep] = useState("offer"); // offer | uploading | result | checkout
  const [verification, setVerification] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [submittingCheckout, setSubmittingCheckout] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="animate-spin" style={{ color: "#1A4FFF" }} />
      </div>
    );
  }
  if (!user) {
    return <Navigate to={`/signup?return=${encodeURIComponent("/subscribe/starter")}`} replace />;
  }

  const onPickFile = () => fileRef.current?.click();

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.type !== "application/pdf") {
      toast.error("Please upload a PDF file.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast.error("File is too large (max 8 MB).");
      return;
    }
    setUploading(true);
    setStep("uploading");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await axios.post(`${API}/business-verification/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setVerification(data);
      setStep("result");
    } catch (err) {
      toast.error(formatApiError(err?.response?.data?.detail) || "Upload failed.");
      setStep("offer");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const startCheckout = async (packageId) => {
    setSubmittingCheckout(true);
    try {
      const { data } = await axios.post(`${API}/checkout/starter/session`, {
        package_id: packageId,
        origin_url: window.location.origin,
        verification_id: verification?.verification_id || null,
      });
      window.location.href = data.url;
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not start checkout.");
      setSubmittingCheckout(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <header className="px-6 sm:px-10 py-6 border-b border-[#eee] flex items-center justify-between">
        <Link to="/" className="inline-flex items-center" style={{ background: "#0A1628", padding: "8px 14px", borderRadius: 8 }}>
          <ZyLogo size={18} />
        </Link>
        <Link to="/" className="text-[13px] text-[#666] hover:text-[#1A4FFF] inline-flex items-center gap-1.5">
          <ArrowLeft size={14} /> Back to home
        </Link>
      </header>

      <main className="flex-1 flex items-start justify-center px-6 py-12 sm:py-16">
        <div className="w-full max-w-[600px]" data-testid={`subscribe-starter-${step}`}>
          <p className="zy-eyebrow mb-3">Subscribe · Starter</p>

          {step === "offer" && (
            <>
              <h1 className="text-[30px] sm:text-[34px] font-bold tracking-tight leading-tight">
                Are you a new business?
              </h1>
              <p className="text-[16px] text-[#555] mt-3 leading-relaxed">
                Get <b>Starter for €99/month for your first 3 months</b>. Verify your business with an official registration document and we&apos;ll apply Founder pricing automatically.
              </p>

              <div className="mt-9 space-y-4">
                <button
                  onClick={onPickFile}
                  data-testid="verify-business-cta"
                  className="w-full text-left p-5 rounded-xl border bg-white hover:border-[#1A4FFF] hover:shadow-[0_12px_32px_-20px_rgba(26,79,255,0.45)] transition-all"
                  style={{ borderColor: "#eee" }}
                >
                  <div className="flex items-start gap-3">
                    <span className="zy-domain-icon shrink-0" style={{ width: 40, height: 40, marginBottom: 0 }}>
                      <BadgeCheck size={18} />
                    </span>
                    <div className="flex-1">
                      <p className="text-[15px] font-semibold text-black">Yes, verify my business</p>
                      <p className="text-[13.5px] text-[#555] mt-1">
                        Upload your KvK, LLC, Companies House, Handelsregister, CIF or equivalent — any country.
                      </p>
                      <p className="text-[12.5px] mt-2 font-semibold" style={{ color: "#1A4FFF" }}>
                        Founder pricing · €99/mo × 3 months · then €499/mo
                      </p>
                    </div>
                    <ArrowRight size={16} className="mt-1.5" style={{ color: "#1A4FFF" }} />
                  </div>
                </button>

                <button
                  onClick={() => startCheckout("starter_standard")}
                  disabled={submittingCheckout}
                  data-testid="skip-verification-cta"
                  className="w-full text-left p-5 rounded-xl border bg-white hover:border-[#1A4FFF] transition-all disabled:opacity-70"
                  style={{ borderColor: "#eee" }}
                >
                  <div className="flex items-start gap-3">
                    <span className="shrink-0 inline-flex items-center justify-center rounded-lg" style={{ width: 40, height: 40, background: "#F4F6FB", color: "#555" }}>
                      <Sparkles size={18} />
                    </span>
                    <div className="flex-1">
                      <p className="text-[15px] font-semibold text-black">No thanks, continue at €499/month</p>
                      <p className="text-[13.5px] text-[#555] mt-1">
                        Skip verification and start your Starter plan right away.
                      </p>
                    </div>
                    {submittingCheckout ? (
                      <Loader2 size={16} className="animate-spin mt-1.5" />
                    ) : (
                      <ArrowRight size={16} className="mt-1.5 text-[#666]" />
                    )}
                  </div>
                </button>
              </div>

              <input
                ref={fileRef}
                type="file"
                accept="application/pdf"
                onChange={onFile}
                className="hidden"
                data-testid="verify-file-input"
              />

              <p className="text-[12px] text-[#888] mt-8 leading-relaxed">
                <ShieldCheck size={11} className="inline mr-1 -mt-0.5" />
                Your document is processed by Claude AI to read company name, registration number, country and date. It is stored encrypted alongside your account and never shared.
              </p>
            </>
          )}

          {step === "uploading" && (
            <div className="text-center py-10">
              <Loader2 size={36} className="mx-auto animate-spin" style={{ color: "#1A4FFF" }} />
              <h2 className="text-[20px] font-bold mt-5">Verifying your business registration…</h2>
              <p className="text-[14px] text-[#555] mt-2">
                This usually takes about ten seconds. We&apos;re reading your document with AI.
              </p>
            </div>
          )}

          {step === "result" && verification && (
            <div data-testid={`verify-result-${verification.status}`}>
              {verification.status === "eligible" ? (
                <>
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-semibold" style={{ background: "rgba(212,175,55,0.16)", color: "#8a6e1d" }}>
                    <FileCheck2 size={14} /> Founder pricing unlocked
                  </div>
                  <h1 className="text-[28px] font-bold tracking-tight mt-4">
                    Verified — you qualify for Founder pricing
                  </h1>
                  <p className="text-[15px] text-[#555] mt-3">
                    €99/month for your first 3 months. After that, your subscription continues at €499/month — cancel anytime.
                  </p>
                </>
              ) : verification.status === "not_eligible" ? (
                <>
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-semibold" style={{ background: "#EAF0FF", color: "#1A4FFF" }}>
                    <FileCheck2 size={14} /> Document verified
                  </div>
                  <h1 className="text-[28px] font-bold tracking-tight mt-4">
                    Your business is established — standard pricing applies
                  </h1>
                  <p className="text-[15px] text-[#555] mt-3">
                    {verification.message}
                  </p>
                </>
              ) : (
                <>
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-semibold" style={{ background: "#FEE2E2", color: "#991b1b" }}>
                    <FileX2 size={14} /> Couldn&apos;t verify
                  </div>
                  <h1 className="text-[28px] font-bold tracking-tight mt-4">
                    We couldn&apos;t verify your document
                  </h1>
                  <p className="text-[15px] text-[#555] mt-3">
                    {verification.message}
                  </p>
                </>
              )}

              <dl className="mt-7 grid grid-cols-2 gap-x-6 gap-y-3 text-[13.5px] border border-[#eee] rounded-xl p-5">
                <Field label="Company" value={verification.company_name} />
                <Field label="Registration #" value={verification.registration_number} />
                <Field label="Country" value={verification.country} />
                <Field label="Registered" value={verification.registration_date ? new Date(verification.registration_date).toLocaleDateString() : null} />
              </dl>

              <div className="mt-8 flex flex-col sm:flex-row gap-3">
                <button
                  onClick={() => startCheckout(verification.status === "eligible" ? "starter_founder" : "starter_standard")}
                  disabled={submittingCheckout}
                  data-testid="proceed-to-payment"
                  className="zy-btn-primary flex-1 disabled:opacity-70"
                >
                  {submittingCheckout ? (
                    <><Loader2 size={15} className="animate-spin" /> Redirecting…</>
                  ) : verification.status === "eligible" ? (
                    <>Pay €99 and start <ArrowRight size={15} /></>
                  ) : (
                    <>Pay €499 and start <ArrowRight size={15} /></>
                  )}
                </button>
                <button
                  onClick={() => { setStep("offer"); setVerification(null); }}
                  className="zy-btn-outline"
                >
                  Try another document
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-[0.14em] text-[#888] font-semibold">{label}</dt>
      <dd className="text-[14px] font-medium text-black mt-0.5">{value || "—"}</dd>
    </div>
  );
}
