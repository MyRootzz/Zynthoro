import { createContext, useContext, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { HOME } from "@/constants/testIds";
import { CheckCircle2, Loader2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PresaleCtx = createContext({ openDialog: () => {} });

export function usePresaleDialog() {
  return useContext(PresaleCtx);
}

export function PresaleDialogProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    plan_interest: "Business",
  });

  const openDialog = useCallback(() => {
    setSuccess(false);
    setOpen(true);
  }, []);

  const update = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim()) {
      toast.error("Please enter your name and email.");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/presale/signup`, form);
      setSuccess(true);
      toast.success("You are on the founding member list.");
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        "Something went wrong. Please try again.";
      toast.error(typeof msg === "string" ? msg : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PresaleCtx.Provider value={{ openDialog }}>
      {children}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          data-testid={HOME.presaleDialog}
          className="sm:max-w-[480px] p-0 overflow-hidden"
        >
          {!success ? (
            <>
              <DialogHeader className="px-6 pt-6">
                <DialogTitle className="text-[22px] font-bold tracking-tight">
                  Claim your presale spot
                </DialogTitle>
                <DialogDescription className="text-[14px] text-[#555]">
                  Founding member pricing locked for life. No payment required today.
                </DialogDescription>
              </DialogHeader>

              <form onSubmit={onSubmit} className="px-6 pb-6 pt-2 space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="ps-name" className="text-[13px] font-medium">Name</Label>
                  <Input
                    id="ps-name"
                    data-testid={HOME.presaleNameInput}
                    placeholder="Ramona Vijfvinkel"
                    value={form.name}
                    onChange={(e) => update("name", e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="ps-email" className="text-[13px] font-medium">Work email</Label>
                  <Input
                    id="ps-email"
                    type="email"
                    data-testid={HOME.presaleEmailInput}
                    placeholder="you@company.com"
                    value={form.email}
                    onChange={(e) => update("email", e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="ps-company" className="text-[13px] font-medium">Company (optional)</Label>
                  <Input
                    id="ps-company"
                    data-testid={HOME.presaleCompanyInput}
                    placeholder="Casa Haya International BV"
                    value={form.company}
                    onChange={(e) => update("company", e.target.value)}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-[13px] font-medium">Interested in</Label>
                  <Select
                    value={form.plan_interest}
                    onValueChange={(v) => update("plan_interest", v)}
                  >
                    <SelectTrigger data-testid={HOME.presalePlanSelect}>
                      <SelectValue placeholder="Choose a plan" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Starter">Starter — €499/mo</SelectItem>
                      <SelectItem value="Business">Business — €899/mo</SelectItem>
                      <SelectItem value="Agency">Agency — €1,199/mo</SelectItem>
                      <SelectItem value="Enterprise">Enterprise — from €2,499/mo</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <button
                  type="submit"
                  data-testid={HOME.presaleSubmit}
                  disabled={submitting}
                  className="zy-btn-primary w-full mt-2 disabled:opacity-70"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" /> Reserving spot…
                    </>
                  ) : (
                    <>Reserve my founding spot</>
                  )}
                </button>

                <p className="text-[12px] text-[#777] text-center">
                  By submitting you agree to be contacted about the Zynthoro presale.
                </p>
              </form>
            </>
          ) : (
            <div
              data-testid={HOME.presaleSuccess}
              className="px-6 py-10 text-center"
            >
              <div
                className="w-14 h-14 rounded-full mx-auto flex items-center justify-center"
                style={{ background: "#EAF0FF", color: "var(--zy-blue)" }}
              >
                <CheckCircle2 size={28} />
              </div>
              <h3 className="text-[20px] font-bold mt-5 tracking-tight">
                You&apos;re on the founding list
              </h3>
              <p className="mt-3 text-[14px] text-[#555] max-w-sm mx-auto">
                We&apos;ll email you {form.email} before launch on <b>June 22, 2026</b> with your founding-member pricing locked in for life.
              </p>
              <button
                onClick={() => setOpen(false)}
                className="zy-btn-outline mt-7"
              >
                Close
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </PresaleCtx.Provider>
  );
}
