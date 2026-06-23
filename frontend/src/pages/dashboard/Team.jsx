import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import { ShieldCheck, ShieldOff, UserPlus, Crown } from "lucide-react";

const ROLES_BY_PLAN = {
  Starter: ["Owner", "Admin", "Employee"],
  Creator: ["Owner", "Admin", "Employee"],
  Business: ["Owner", "Admin", "Manager", "Employee"],
  Agency: ["Owner", "Admin", "Team Lead", "Manager", "Employee"],
  "Enterprise Basic": ["Owner", "Director", "Senior Manager", "Admin", "Manager", "Employee"],
  "Enterprise Plus": ["Owner", "Director", "Senior Manager", "Admin", "Manager", "Employee"],
  "Enterprise Advanced": ["Owner", "Director", "Senior Manager", "Admin", "Manager", "Employee", "Custom"],
  "Enterprise Elite": ["Owner", "Director", "Senior Manager", "Admin", "Manager", "Employee", "Custom"],
  "Enterprise Unlimited": ["Owner", "Director", "Senior Manager", "Admin", "Manager", "Employee", "Custom"],
  Presale: ["Owner", "Admin", "Employee"],
};

const SEAT_PRICE = {
  Business: 4.99,
  Agency: 3.99,
};

export default function TeamPage() {
  const { user } = useAuth();
  const [members, setMembers] = useState([]);
  const [invite, setInvite] = useState({ open: false, email: "", role: "Employee", submitting: false });
  const [seats, setSeats] = useState({ open: false, count: 1 });

  const plan = user?.subscription_plan || "Presale";
  const roleOptions = ROLES_BY_PLAN[plan] || ROLES_BY_PLAN.Presale;
  const seatPrice = SEAT_PRICE[plan];

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/team/members`);
      setMembers(data.members || []);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not load team.");
    }
  };
  useEffect(() => { load(); }, []);

  const submitInvite = async (e) => {
    e.preventDefault();
    setInvite((s) => ({ ...s, submitting: true }));
    try {
      await axios.post(`${API}/team/invite`, { email: invite.email, role: invite.role });
      toast.success("Invitation sent.");
      setInvite({ open: false, email: "", role: "Employee", submitting: false });
      load();
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Could not invite.");
      setInvite((s) => ({ ...s, submitting: false }));
    }
  };

  return (
    <div data-testid="team-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
        <div>
          <p className="zy-eyebrow mb-2">Team</p>
          <h1 className="text-[28px] font-bold tracking-tight">Your team</h1>
          <p className="text-[14px] text-[#555] mt-1">
            {members.length} member{members.length === 1 ? "" : "s"} · Plan: <b>{plan}</b>
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setSeats({ open: true, count: 1 })} className="zy-btn-outline" data-testid="buy-seats">
            Buy extra seats
          </button>
          <button onClick={() => setInvite((s) => ({ ...s, open: true }))} className="zy-btn-primary" data-testid="invite-member">
            <UserPlus size={16} /> Invite team member
          </button>
        </div>
      </div>

      <div className="bg-white border border-[#eee] rounded-xl overflow-hidden">
        <table className="w-full text-[14px]">
          <thead className="bg-[#FAFAFB] text-[12px] uppercase tracking-wider text-[#777]">
            <tr>
              <th className="text-left px-5 py-3">Member</th>
              <th className="text-left px-5 py-3">Role</th>
              <th className="text-left px-5 py-3">Status</th>
              <th className="text-left px-5 py-3">2FA</th>
              <th className="text-left px-5 py-3">Last login</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m, i) => {
              const initials = (m.name || m.email || "?").split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase();
              return (
                <tr key={m.id || m.email} className={i % 2 ? "bg-[#FAFAFB]" : ""} data-testid={`team-row-${i}`}>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <span className="w-8 h-8 rounded-full inline-flex items-center justify-center text-white text-[11px] font-semibold" style={{ background: "#1A4FFF" }}>
                        {initials}
                      </span>
                      <div>
                        <p className="font-medium text-black flex items-center gap-1.5">
                          {m.name || m.email}
                          {m.is_owner && <Crown size={13} style={{ color: "#D4AF37" }} />}
                        </p>
                        <p className="text-[12px] text-[#777]">{m.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3">{m.role}</td>
                  <td className="px-5 py-3">
                    <span
                      className="text-[11.5px] font-semibold px-2 py-0.5 rounded-full"
                      style={
                        m.status === "active"
                          ? { background: "rgba(34,197,94,0.12)", color: "#16a34a" }
                          : { background: "#F4F6FB", color: "#555" }
                      }
                    >
                      {m.status}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    {m.twofa ? (
                      <span className="inline-flex items-center gap-1 text-[12.5px]" style={{ color: "#16a34a" }}>
                        <ShieldCheck size={13} /> Enabled
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[12.5px] text-[#999]">
                        <ShieldOff size={13} /> Off
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-[#666]">{m.last_login ? new Date(m.last_login).toLocaleDateString() : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Invite dialog */}
      <Dialog open={invite.open} onOpenChange={(o) => setInvite((s) => ({ ...s, open: o }))}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle>Invite a team member</DialogTitle>
            <DialogDescription>They&apos;ll receive an invitation link to join your workspace.</DialogDescription>
          </DialogHeader>
          <form onSubmit={submitInvite} className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-[13px] font-medium">Email address</Label>
              <Input
                type="email"
                value={invite.email}
                onChange={(e) => setInvite((s) => ({ ...s, email: e.target.value }))}
                data-testid="invite-email"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[13px] font-medium">Role</Label>
              <Select value={invite.role} onValueChange={(v) => setInvite((s) => ({ ...s, role: v }))}>
                <SelectTrigger data-testid="invite-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {roleOptions.map((r) => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <button type="submit" disabled={invite.submitting} className="zy-btn-primary w-full disabled:opacity-70" data-testid="invite-submit">
              {invite.submitting ? "Sending…" : "Send invitation"}
            </button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Seats dialog */}
      <Dialog open={seats.open} onOpenChange={(o) => setSeats((s) => ({ ...s, open: o }))}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle>Buy extra seats</DialogTitle>
            <DialogDescription>
              Plan <b>{plan}</b>
              {seatPrice ? <> · €{seatPrice.toFixed(2)}/seat/month</> : (plan?.startsWith("Enterprise") ? " · Unlimited included" : "")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {seatPrice ? (
              <>
                <div className="flex flex-wrap gap-2">
                  {[1, 5, 10].map((n) => (
                    <button
                      key={n}
                      onClick={() => setSeats((s) => ({ ...s, count: n }))}
                      className={`px-3 py-1.5 rounded-md text-[13px] border ${seats.count === n ? "border-[#1A4FFF] text-[#1A4FFF] bg-[#EAF0FF]" : "border-[#eee] text-[#333]"}`}
                    >
                      +{n}
                    </button>
                  ))}
                  <Input
                    type="number"
                    min={1}
                    value={seats.count}
                    onChange={(e) => setSeats((s) => ({ ...s, count: Math.max(1, parseInt(e.target.value || "1", 10)) }))}
                    className="w-24"
                  />
                </div>
                <div className="bg-[#FAFAFB] border border-[#eee] rounded-md p-3 text-[13.5px] flex items-center justify-between">
                  <span className="text-[#555]">{seats.count} extra seat{seats.count > 1 ? "s" : ""}</span>
                  <span className="font-semibold">€{(seats.count * seatPrice).toFixed(2)}/mo</span>
                </div>
                <button
                  onClick={() => toast.message("Seat purchase opens at launch on 30 June 2026.")}
                  className="zy-btn-primary w-full"
                >
                  Add seats
                </button>
              </>
            ) : (
              <p className="text-[13.5px] text-[#555]">
                Your Enterprise plan includes unlimited seats — no extra purchase needed.
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
