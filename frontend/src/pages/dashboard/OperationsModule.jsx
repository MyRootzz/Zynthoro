import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Workflow, Factory, ClipboardList, ShieldCheck, Boxes, BarChart3, ScanLine,
  Plus, Trash2, Loader2, ArrowRight, CheckCircle2, AlertCircle, Clock, Lock,
  Sparkles,
} from "lucide-react";
import { API, formatApiError, useAuth } from "@/contexts/AuthContext";
import UpgradeLock from "@/components/dashboard/UpgradeLock";
import { planAtLeast } from "@/lib/planCatalog";

const TABS = [
  { id: "recipes",    label: "Recipes & Formulas", icon: ClipboardList, tier: "Business" },
  { id: "boms",       label: "Bill of Materials",  icon: Boxes,         tier: "Agency" },
  { id: "orders",     label: "Production Orders",  icon: Factory,       tier: "Business" },
  { id: "work",       label: "Work Orders",        icon: Workflow,      tier: "Business" },
  { id: "quality",    label: "Quality Control",    icon: ShieldCheck,   tier: "Agency" },
  { id: "trace",      label: "Lot Traceability",   icon: ScanLine,      tier: "Enterprise Basic" },
  { id: "costs",      label: "Production Costs",   icon: BarChart3,     tier: "Business" },
];

export default function OperationsModule() {
  const { user } = useAuth();
  const plan = user?.subscription_plan || "Starter";
  const fullAccess = !!(user?.is_demo || user?.is_unlimited || plan?.startsWith("Enterprise"));
  const has = (tier) => fullAccess || planAtLeast(plan, tier);

  const [tab, setTab] = useState("orders");

  return (
    <div data-testid="operations-module" className="max-w-6xl">
      <p className="zy-eyebrow mb-2" style={{ color: "#1A4FFF" }}>Operations & Production</p>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-[24px] sm:text-[28px] font-bold tracking-tight flex items-center gap-2">
            <Factory size={22} style={{ color: "#1A4FFF" }} />
            Production Management
          </h1>
          <p className="text-[13.5px] text-[#555] mt-1 max-w-2xl">
            Recipes, BOMs, work orders, quality checks and full lot traceability — replace SAP & Oracle for food, cosmetics, pharma and manufacturing.
          </p>
        </div>
        <div className="text-[12.5px] text-[#666]">
          Plan: <span className="font-semibold text-black">{plan}</span>
        </div>
      </div>

      <nav className="mt-7 flex flex-wrap gap-1 border-b border-[#eee]" role="tablist">
        {TABS.map((t) => {
          const Icon = t.icon;
          const locked = !has(t.tier);
          return (
            <button
              key={t.id}
              role="tab"
              onClick={() => setTab(t.id)}
              data-testid={`ops-tab-${t.id}`}
              className={`inline-flex items-center gap-1.5 px-3 sm:px-4 py-2.5 text-[13px] font-medium border-b-2 transition-colors ${
                tab === t.id
                  ? "border-[#1A4FFF] text-[#1A4FFF]"
                  : "border-transparent text-[#666] hover:text-black"
              }`}
            >
              <Icon size={14} /> {t.label}
              {locked && <Lock size={11} className="text-[#bbb] ml-0.5" />}
            </button>
          );
        })}
      </nav>

      <div className="mt-6">
        {tab === "recipes"  && (has("Business") ? <RecipesTab /> : <UpgradeLock requiredPlan="Business" feature="Recipes & Formula Management" />)}
        {tab === "boms"     && (has("Agency") ? <BomTab /> : <UpgradeLock requiredPlan="Agency" feature="Bill of Materials (multi-level)" />)}
        {tab === "orders"   && (has("Business") ? <OrdersTab /> : <UpgradeLock requiredPlan="Business" feature="Production Orders" />)}
        {tab === "work"     && (has("Business") ? <WorkOrdersTab /> : <UpgradeLock requiredPlan="Business" feature="Work Orders" />)}
        {tab === "quality"  && (has("Agency") ? <QualityTab /> : <UpgradeLock requiredPlan="Agency" feature="Quality Control" />)}
        {tab === "trace"    && (has("Enterprise Basic") ? <TraceTab /> : <UpgradeLock requiredPlan="Enterprise Basic" feature="Lot & Batch Traceability" />)}
        {tab === "costs"    && (has("Business") ? <CostsTab /> : <UpgradeLock requiredPlan="Business" feature="Production Costs" />)}
      </div>
    </div>
  );
}

/* ----------------------- Recipes ----------------------- */
function RecipesTab() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(blankRecipe());

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/operations/recipes`);
      setRows(data.recipes || []);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load recipes."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.name.trim()) return toast.error("Recipe name is required.");
    setCreating(true);
    try {
      await axios.post(`${API}/operations/recipes`, {
        ...form,
        yield_qty: Number(form.yield_qty) || 1,
        labour_cost_eur: Number(form.labour_cost_eur) || 0,
        overhead_eur: Number(form.overhead_eur) || 0,
        ingredients: form.ingredients
          .filter((i) => i.name.trim())
          .map((i) => ({ ...i, quantity: Number(i.quantity) || 0, cost_per_unit_eur: Number(i.cost_per_unit_eur) || 0 })),
        allergens: (form.allergens || "").split(",").map((s) => s.trim()).filter(Boolean),
      });
      toast.success("Recipe saved.");
      setForm(blankRecipe());
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't save recipe."); }
    finally { setCreating(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this recipe?")) return;
    try { await axios.delete(`${API}/operations/recipes/${id}`); load(); }
    catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Delete failed."); }
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={15} style={{ color: "#1A4FFF" }} />
          <h3 className="text-[14px] font-semibold">Create a recipe / formula</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="recipe-name" />
          <Input label="Code (SKU)" value={form.code} onChange={(v) => setForm({ ...form, code: v })} testId="recipe-code" />
          <Input label="Yield" type="number" value={form.yield_qty} onChange={(v) => setForm({ ...form, yield_qty: v })} testId="recipe-yield" />
          <Input label="Yield unit" value={form.yield_unit} onChange={(v) => setForm({ ...form, yield_unit: v })} />
          <Input label="Labour cost (€)" type="number" value={form.labour_cost_eur} onChange={(v) => setForm({ ...form, labour_cost_eur: v })} />
          <Input label="Overhead (€)" type="number" value={form.overhead_eur} onChange={(v) => setForm({ ...form, overhead_eur: v })} />
          <Input label="Allergens (comma-sep.)" value={form.allergens} onChange={(v) => setForm({ ...form, allergens: v })} className="sm:col-span-2" />
        </div>
        <div className="mt-4">
          <p className="text-[12.5px] font-semibold text-[#555] mb-2">Ingredients</p>
          <div className="space-y-2">
            {form.ingredients.map((ing, i) => (
              <div key={i} className="grid grid-cols-12 gap-2">
                <input value={ing.name} onChange={(e) => updateIng(form, setForm, i, "name", e.target.value)} placeholder="Ingredient" className="col-span-5 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
                <input type="number" value={ing.quantity} onChange={(e) => updateIng(form, setForm, i, "quantity", e.target.value)} placeholder="Qty" className="col-span-2 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
                <input value={ing.unit} onChange={(e) => updateIng(form, setForm, i, "unit", e.target.value)} placeholder="g" className="col-span-2 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
                <input type="number" step="0.001" value={ing.cost_per_unit_eur} onChange={(e) => updateIng(form, setForm, i, "cost_per_unit_eur", e.target.value)} placeholder="€/unit" className="col-span-2 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
                <button onClick={() => setForm({ ...form, ingredients: form.ingredients.filter((_, idx) => idx !== i) })} className="col-span-1 text-[#aaa] hover:text-red-500"><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
          <button onClick={() => setForm({ ...form, ingredients: [...form.ingredients, { name: "", quantity: 0, unit: "g", cost_per_unit_eur: 0 }] })} className="mt-2 inline-flex items-center gap-1 text-[12.5px] text-[#1A4FFF] font-semibold hover:underline">
            <Plus size={12} /> Add ingredient
          </button>
        </div>
        <div className="mt-4 flex items-center gap-2">
          <button onClick={save} disabled={creating} className="zy-btn-primary" data-testid="recipe-save">
            {creating ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            {creating ? "Saving…" : "Save recipe"}
          </button>
        </div>
      </div>

      <DataTable
        loading={loading}
        empty="No recipes yet — create one above."
        rows={rows}
        testId="recipes-table"
        columns={[
          { key: "code",       label: "Code",  render: (r) => <span className="font-mono text-[12px]">{r.code || "—"}</span> },
          { key: "name",       label: "Name",  render: (r) => <span className="font-semibold">{r.name}</span> },
          { key: "yield",      label: "Yield", render: (r) => `${r.yield_qty} ${r.yield_unit}` },
          { key: "ingredients",label: "Ingr.", render: (r) => (r.ingredients || []).length },
          { key: "allergens",  label: "Allergens", render: (r) => (r.allergens || []).join(", ") || "—" },
          { key: "cost",       label: "€/unit", render: (r) => `€${(r.cost_per_unit_eur || 0).toFixed(2)}` },
          { key: "v",          label: "v",     render: (r) => `v${r.version || 1}` },
          { key: "actions",    label: "", render: (r) => <button onClick={() => remove(r.id)} className="text-[#aaa] hover:text-red-500"><Trash2 size={13} /></button> },
        ]}
      />
    </div>
  );
}

/* ----------------------- BOMs ----------------------- */
function BomTab() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", finished_sku: "", description: "", lines: [{ sku: "", name: "", quantity: 0, unit: "unit", level: 1, cost_eur: 0 }] });

  const load = async () => {
    setLoading(true);
    try { const { data } = await axios.get(`${API}/operations/boms`); setRows(data.boms || []); }
    catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load BOMs."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.name.trim() || !form.finished_sku.trim()) return toast.error("Name and finished SKU are required.");
    try {
      await axios.post(`${API}/operations/boms`, {
        ...form,
        lines: form.lines.filter((l) => l.sku.trim()).map((l) => ({ ...l, quantity: Number(l.quantity) || 0, level: Number(l.level) || 1, cost_eur: Number(l.cost_eur) || 0 })),
      });
      toast.success("BOM saved.");
      setForm({ name: "", finished_sku: "", description: "", lines: [{ sku: "", name: "", quantity: 0, unit: "unit", level: 1, cost_eur: 0 }] });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't save BOM."); }
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <h3 className="text-[14px] font-semibold mb-3">Create a multi-level BOM</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input label="BOM name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="bom-name" />
          <Input label="Finished SKU" value={form.finished_sku} onChange={(v) => setForm({ ...form, finished_sku: v })} testId="bom-sku" />
          <Input label="Description" value={form.description} onChange={(v) => setForm({ ...form, description: v })} />
        </div>
        <p className="text-[12.5px] font-semibold text-[#555] mt-4 mb-2">Lines (raw → semi-finished → finished)</p>
        <div className="space-y-2">
          {form.lines.map((l, i) => (
            <div key={i} className="grid grid-cols-12 gap-2">
              <input value={l.sku} onChange={(e) => updateLine(form, setForm, i, "sku", e.target.value)} placeholder="SKU" className="col-span-2 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <input value={l.name} onChange={(e) => updateLine(form, setForm, i, "name", e.target.value)} placeholder="Item name" className="col-span-4 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <input type="number" value={l.quantity} onChange={(e) => updateLine(form, setForm, i, "quantity", e.target.value)} placeholder="Qty" className="col-span-1 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <input value={l.unit} onChange={(e) => updateLine(form, setForm, i, "unit", e.target.value)} placeholder="unit" className="col-span-1 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <input type="number" min={1} max={10} value={l.level} onChange={(e) => updateLine(form, setForm, i, "level", e.target.value)} placeholder="Lvl" className="col-span-1 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <input type="number" step="0.01" value={l.cost_eur} onChange={(e) => updateLine(form, setForm, i, "cost_eur", e.target.value)} placeholder="€/unit" className="col-span-2 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <button onClick={() => setForm({ ...form, lines: form.lines.filter((_, idx) => idx !== i) })} className="col-span-1 text-[#aaa] hover:text-red-500"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
        <button onClick={() => setForm({ ...form, lines: [...form.lines, { sku: "", name: "", quantity: 0, unit: "unit", level: 1, cost_eur: 0 }] })} className="mt-2 inline-flex items-center gap-1 text-[12.5px] text-[#1A4FFF] font-semibold hover:underline">
          <Plus size={12} /> Add line
        </button>
        <div className="mt-4">
          <button onClick={save} className="zy-btn-primary" data-testid="bom-save">
            <Plus size={14} /> Save BOM
          </button>
        </div>
      </div>

      <DataTable
        loading={loading}
        empty="No BOMs yet."
        rows={rows}
        testId="boms-table"
        columns={[
          { key: "sku",      label: "Finished SKU", render: (r) => <span className="font-mono text-[12px]">{r.finished_sku}</span> },
          { key: "name",     label: "Name",         render: (r) => r.name },
          { key: "lines",    label: "Lines",        render: (r) => (r.lines || []).length },
          { key: "levels",   label: "Max level",    render: (r) => `L${r.max_level || 1}` },
          { key: "cost",     label: "Total cost",   render: (r) => `€${(r.total_cost_eur || 0).toFixed(2)}` },
        ]}
      />
    </div>
  );
}

/* ----------------------- Production Orders ----------------------- */
function OrdersTab() {
  const [rows, setRows] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", recipe_id: "", quantity: 1, unit: "unit", scheduled_for: "", location: "", notes: "" });

  const load = async () => {
    setLoading(true);
    try {
      const [o, r] = await Promise.all([
        axios.get(`${API}/operations/production-orders`),
        axios.get(`${API}/operations/recipes`).catch(() => ({ data: { recipes: [] } })),
      ]);
      setRows(o.data.orders || []);
      setRecipes(r.data.recipes || []);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load orders."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.name.trim()) return toast.error("Order name is required.");
    try {
      await axios.post(`${API}/operations/production-orders`, {
        ...form,
        quantity: Number(form.quantity) || 0,
        recipe_id: form.recipe_id || null,
      });
      toast.success("Production order created.");
      setForm({ name: "", recipe_id: "", quantity: 1, unit: "unit", scheduled_for: "", location: "", notes: "" });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't create order."); }
  };

  const updateStatus = async (id, status) => {
    try { await axios.patch(`${API}/operations/production-orders/${id}/status`, { status }); load(); }
    catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Status update failed."); }
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <h3 className="text-[14px] font-semibold mb-3">Schedule a new production order</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input label="Order name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="order-name" />
          <div>
            <label className="block text-[11.5px] font-semibold text-[#555] mb-1">Recipe (optional)</label>
            <select value={form.recipe_id} onChange={(e) => setForm({ ...form, recipe_id: e.target.value })} data-testid="order-recipe" className="w-full text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]">
              <option value="">— none —</option>
              {recipes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
          <Input label="Quantity" type="number" value={form.quantity} onChange={(v) => setForm({ ...form, quantity: v })} />
          <Input label="Unit" value={form.unit} onChange={(v) => setForm({ ...form, unit: v })} />
          <Input label="Scheduled for" type="date" value={form.scheduled_for} onChange={(v) => setForm({ ...form, scheduled_for: v })} />
          <Input label="Location" value={form.location} onChange={(v) => setForm({ ...form, location: v })} />
        </div>
        <div className="mt-4">
          <button onClick={save} className="zy-btn-primary" data-testid="order-save">
            <Plus size={14} /> Create order
          </button>
        </div>
      </div>

      <DataTable
        loading={loading}
        empty="No production orders yet."
        rows={rows}
        testId="orders-table"
        columns={[
          { key: "order_no", label: "Order #", render: (r) => <span className="font-mono text-[12px]">{r.order_no}</span> },
          { key: "name",     label: "Name",    render: (r) => <span className="font-semibold">{r.name}</span> },
          { key: "qty",      label: "Qty",     render: (r) => `${r.quantity} ${r.unit}` },
          { key: "sched",    label: "Scheduled", render: (r) => r.scheduled_for || "—" },
          { key: "loc",      label: "Location", render: (r) => r.location || "—" },
          { key: "est",      label: "Est. cost", render: (r) => `€${(r.cost_estimate_eur || 0).toFixed(2)}` },
          { key: "status",   label: "Status",   render: (r) => <StatusPill value={r.status} /> },
          { key: "actions",  label: "",         render: (r) => (
            <select value={r.status} onChange={(e) => updateStatus(r.id, e.target.value)} className="text-[11.5px] border border-[#eee] rounded px-1.5 py-1">
              <option value="planned">planned</option>
              <option value="in_progress">in_progress</option>
              <option value="completed">completed</option>
              <option value="cancelled">cancelled</option>
            </select>
          ) },
        ]}
      />
    </div>
  );
}

/* ----------------------- Work Orders ----------------------- */
function WorkOrdersTab() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [orders, setOrders] = useState([]);
  const [form, setForm] = useState({ production_order_id: "", name: "", assignee_email: "", steps: [{ title: "", instruction: "", quality_checks: "" }] });

  const load = async () => {
    setLoading(true);
    try {
      const [w, o] = await Promise.all([
        axios.get(`${API}/operations/work-orders`),
        axios.get(`${API}/operations/production-orders`).catch(() => ({ data: { orders: [] } })),
      ]);
      setRows(w.data.work_orders || []);
      setOrders(o.data.orders || []);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load work orders."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.production_order_id || !form.name.trim()) return toast.error("Pick a production order and name the work order.");
    try {
      await axios.post(`${API}/operations/work-orders`, {
        ...form,
        steps: form.steps.filter((s) => s.title.trim()).map((s) => ({
          title: s.title, instruction: s.instruction,
          quality_checks: (s.quality_checks || "").split(",").map((x) => x.trim()).filter(Boolean),
        })),
      });
      toast.success("Work order created.");
      setForm({ production_order_id: "", name: "", assignee_email: "", steps: [{ title: "", instruction: "", quality_checks: "" }] });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't create work order."); }
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <h3 className="text-[14px] font-semibold mb-3">Issue a new work order</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11.5px] font-semibold text-[#555] mb-1">Production order</label>
            <select value={form.production_order_id} onChange={(e) => setForm({ ...form, production_order_id: e.target.value })} data-testid="wo-po" className="w-full text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]">
              <option value="">— pick —</option>
              {orders.map((o) => <option key={o.id} value={o.id}>{o.order_no} · {o.name}</option>)}
            </select>
          </div>
          <Input label="Work-order name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} testId="wo-name" />
          <Input label="Assignee email" value={form.assignee_email} onChange={(v) => setForm({ ...form, assignee_email: v })} />
        </div>
        <p className="text-[12.5px] font-semibold text-[#555] mt-4 mb-2">Steps</p>
        <div className="space-y-2">
          {form.steps.map((s, i) => (
            <div key={i} className="grid grid-cols-12 gap-2">
              <input value={s.title} onChange={(e) => updateLine(form, setForm, i, "title", e.target.value, "steps")} placeholder="Step title" className="col-span-3 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <input value={s.instruction} onChange={(e) => updateLine(form, setForm, i, "instruction", e.target.value, "steps")} placeholder="Instruction" className="col-span-5 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <input value={s.quality_checks} onChange={(e) => updateLine(form, setForm, i, "quality_checks", e.target.value, "steps")} placeholder="QC checks (comma-sep.)" className="col-span-3 text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]" />
              <button onClick={() => setForm({ ...form, steps: form.steps.filter((_, idx) => idx !== i) })} className="col-span-1 text-[#aaa] hover:text-red-500"><Trash2 size={13} /></button>
            </div>
          ))}
        </div>
        <button onClick={() => setForm({ ...form, steps: [...form.steps, { title: "", instruction: "", quality_checks: "" }] })} className="mt-2 inline-flex items-center gap-1 text-[12.5px] text-[#1A4FFF] font-semibold hover:underline">
          <Plus size={12} /> Add step
        </button>
        <div className="mt-4">
          <button onClick={save} className="zy-btn-primary" data-testid="wo-save">
            <Plus size={14} /> Create work order
          </button>
        </div>
      </div>

      <DataTable
        loading={loading}
        empty="No work orders yet."
        rows={rows}
        testId="work-orders-table"
        columns={[
          { key: "name",   label: "Name",     render: (r) => <span className="font-semibold">{r.name}</span> },
          { key: "po",     label: "Prod. order", render: (r) => <span className="font-mono text-[11px]">{r.production_order_id?.slice(0, 8) || "—"}</span> },
          { key: "assg",   label: "Assignee", render: (r) => r.assignee_email || "—" },
          { key: "steps",  label: "Steps",    render: (r) => (r.steps || []).length },
          { key: "status", label: "Status",   render: (r) => <StatusPill value={r.status} /> },
        ]}
      />
    </div>
  );
}

/* ----------------------- Quality ----------------------- */
function QualityTab() {
  const [rows, setRows] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ production_order_id: "", batch_lot: "", checklist: "", results: "", notes: "" });

  const load = async () => {
    setLoading(true);
    try {
      const [q, o] = await Promise.all([
        axios.get(`${API}/operations/quality-inspections`),
        axios.get(`${API}/operations/production-orders`).catch(() => ({ data: { orders: [] } })),
      ]);
      setRows(q.data.inspections || []);
      setOrders(o.data.orders || []);
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load inspections."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    const checklist = (form.checklist || "").split(",").map((s) => s.trim()).filter(Boolean);
    const results = (form.results || "").split(",").map((s) => s.trim().toLowerCase()).filter((x) => ["pass", "fail", "skip"].includes(x));
    if (!form.production_order_id) return toast.error("Pick a production order.");
    if (checklist.length === 0) return toast.error("Add at least one checklist item.");
    try {
      await axios.post(`${API}/operations/quality-inspections`, { ...form, checklist, results });
      toast.success("Inspection recorded.");
      setForm({ production_order_id: "", batch_lot: "", checklist: "", results: "", notes: "" });
      load();
    } catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't save inspection."); }
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#eee] rounded-2xl p-5">
        <h3 className="text-[14px] font-semibold mb-3">Record a QC inspection</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11.5px] font-semibold text-[#555] mb-1">Production order</label>
            <select value={form.production_order_id} onChange={(e) => setForm({ ...form, production_order_id: e.target.value })} data-testid="qc-po" className="w-full text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]">
              <option value="">— pick —</option>
              {orders.map((o) => <option key={o.id} value={o.id}>{o.order_no} · {o.name}</option>)}
            </select>
          </div>
          <Input label="Batch / lot" value={form.batch_lot} onChange={(v) => setForm({ ...form, batch_lot: v })} />
          <Input label="Checklist (comma-sep.)" value={form.checklist} onChange={(v) => setForm({ ...form, checklist: v })} className="sm:col-span-2" />
          <Input label="Results (pass/fail/skip, comma-sep.)" value={form.results} onChange={(v) => setForm({ ...form, results: v })} className="sm:col-span-2" />
          <Input label="Notes" value={form.notes} onChange={(v) => setForm({ ...form, notes: v })} className="sm:col-span-2" />
        </div>
        <div className="mt-4">
          <button onClick={save} className="zy-btn-primary" data-testid="qc-save">
            <CheckCircle2 size={14} /> Record inspection
          </button>
        </div>
      </div>

      <DataTable
        loading={loading}
        empty="No inspections yet."
        rows={rows}
        testId="qc-table"
        columns={[
          { key: "lot",    label: "Batch / lot", render: (r) => <span className="font-mono text-[12px]">{r.batch_lot || "—"}</span> },
          { key: "items",  label: "Items",       render: (r) => (r.checklist || []).length },
          { key: "pass",   label: "Pass",        render: (r) => <span className="text-green-600 font-semibold">{r.pass_count}</span> },
          { key: "fail",   label: "Fail",        render: (r) => <span className="text-red-600 font-semibold">{r.fail_count}</span> },
          { key: "ov",     label: "Overall",     render: (r) => <StatusPill value={r.overall} /> },
          { key: "notes",  label: "Notes",       render: (r) => <span className="text-[12.5px] text-[#555]">{r.notes || "—"}</span> },
        ]}
      />
    </div>
  );
}

/* ----------------------- Lot traceability ----------------------- */
function TraceTab() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trace, setTrace] = useState(null);

  const load = async () => {
    setLoading(true);
    try { const { data } = await axios.get(`${API}/operations/lots`); setRows(data.lots || []); }
    catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load lots."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const showTrace = async (lot_no) => {
    try { const { data } = await axios.get(`${API}/operations/lots/${lot_no}/trace`); setTrace(data); }
    catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Trace failed."); }
  };

  const recall = async (lot_no) => {
    if (!window.confirm(`Recall lot ${lot_no}? This affects downstream traceability.`)) return;
    try { await axios.post(`${API}/operations/lots/${lot_no}/recall`); toast.success("Lot recalled."); load(); }
    catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Recall failed."); }
  };

  return (
    <div className="space-y-5">
      <DataTable
        loading={loading}
        empty="No lots yet."
        rows={rows}
        testId="lots-table"
        columns={[
          { key: "lot",    label: "Lot #",    render: (r) => <span className="font-mono text-[12px]">{r.lot_no}</span> },
          { key: "exp",    label: "Expiry",   render: (r) => r.expiry_date || "—" },
          { key: "raw",    label: "Raw lots", render: (r) => (r.raw_material_lots || []).length },
          { key: "stat",   label: "Status",   render: (r) => <StatusPill value={r.status} /> },
          { key: "act",    label: "",         render: (r) => (
            <div className="flex items-center gap-2">
              <button onClick={() => showTrace(r.lot_no)} className="text-[11.5px] text-[#1A4FFF] font-semibold hover:underline" data-testid="lot-trace">Trace</button>
              {r.status !== "recalled" && (
                <button onClick={() => recall(r.lot_no)} className="text-[11.5px] text-red-500 font-semibold hover:underline" data-testid="lot-recall">Recall</button>
              )}
            </div>
          ) },
        ]}
      />

      {trace && (
        <div className="bg-white border border-[#eee] rounded-2xl p-5" data-testid="trace-result">
          <div className="flex items-center justify-between">
            <h3 className="text-[14px] font-semibold flex items-center gap-2">
              <ScanLine size={15} style={{ color: "#1A4FFF" }} /> Trace · {trace.lot?.lot_no}
            </h3>
            <button onClick={() => setTrace(null)} className="text-[12px] text-[#888] hover:text-black">Close</button>
          </div>
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3 text-[13px]">
            <div className="p-3 rounded-md bg-[#F4F6FB]">
              <p className="text-[11px] uppercase tracking-wider text-[#888]">Lot</p>
              <p className="font-mono mt-1">{trace.lot?.lot_no}</p>
              <p className="text-[12px] text-[#555] mt-1">Expiry: {trace.lot?.expiry_date || "—"}</p>
            </div>
            <div className="p-3 rounded-md bg-[#F4F6FB]">
              <p className="text-[11px] uppercase tracking-wider text-[#888]">Production order</p>
              <p className="mt-1">{trace.production_order?.name || "—"}</p>
              <p className="font-mono text-[12px] text-[#555]">{trace.production_order?.order_no || "—"}</p>
            </div>
            <div className="p-3 rounded-md bg-[#F4F6FB]">
              <p className="text-[11px] uppercase tracking-wider text-[#888]">Upstream raw lots</p>
              <p className="mt-1">{trace.upstream_lots?.length || 0} linked</p>
              <p className="font-mono text-[11.5px] text-[#555] mt-1 line-clamp-2">
                {(trace.lot?.raw_material_lots || []).join(", ") || "—"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ----------------------- Costs ----------------------- */
function CostsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try { const { data } = await axios.get(`${API}/operations/costs/summary`); setData(data); }
      catch (e) { toast.error(formatApiError(e?.response?.data?.detail) || "Couldn't load costs."); }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <p className="text-[13px] text-[#888]">Loading cost summary…</p>;
  if (!data) return <p className="text-[13px] text-[#888]">No data yet.</p>;

  const tiles = [
    { label: "Recipes",            value: data.recipe_count, accent: "#1A4FFF" },
    { label: "Production orders",  value: data.production_order_count, accent: "#1A4FFF" },
    { label: "Avg cost / unit",    value: `€${(data.average_unit_cost_eur || 0).toFixed(2)}`, accent: "#16a34a" },
    { label: "Estimated total",    value: `€${(data.estimated_production_cost_eur || 0).toLocaleString("en-IE", { minimumFractionDigits: 2 })}`, accent: "#1A4FFF" },
    { label: "Actual total",       value: `€${(data.actual_production_cost_eur || 0).toLocaleString("en-IE", { minimumFractionDigits: 2 })}`, accent: "#1A4FFF" },
    { label: "Variance",           value: `€${(data.variance_eur || 0).toLocaleString("en-IE", { minimumFractionDigits: 2 })}`, accent: (data.variance_eur || 0) >= 0 ? "#D97706" : "#16a34a" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" data-testid="costs-summary">
      {tiles.map((t) => (
        <div key={t.label} className="bg-white border border-[#eee] rounded-xl p-4">
          <p className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: t.accent }}>{t.label}</p>
          <p className="text-[22px] font-bold mt-1.5" style={{ color: "#0A1628" }}>{t.value}</p>
        </div>
      ))}
    </div>
  );
}

/* ----------------------- Helpers ----------------------- */
function blankRecipe() {
  return { name: "", code: "", yield_qty: 1, yield_unit: "unit", labour_cost_eur: 0, overhead_eur: 0, allergens: "", ingredients: [{ name: "", quantity: 0, unit: "g", cost_per_unit_eur: 0 }] };
}

function updateIng(form, setForm, i, key, val) {
  const next = [...form.ingredients];
  next[i] = { ...next[i], [key]: val };
  setForm({ ...form, ingredients: next });
}

function updateLine(form, setForm, i, key, val, listKey = "lines") {
  const next = [...form[listKey]];
  next[i] = { ...next[i], [key]: val };
  setForm({ ...form, [listKey]: next });
}

function Input({ label, value, onChange, type = "text", testId, className = "" }) {
  return (
    <div className={className}>
      <label className="block text-[11.5px] font-semibold text-[#555] mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full text-[13px] px-2.5 py-2 rounded-md border border-[#eee] focus:outline-none focus:border-[#1A4FFF]"
      />
    </div>
  );
}

function StatusPill({ value }) {
  const cfg = ({
    pass:        { bg: "rgba(34,197,94,0.12)",  fg: "#16a34a", icon: CheckCircle2 },
    fail:        { bg: "rgba(220,38,38,0.10)",  fg: "#dc2626", icon: AlertCircle },
    incomplete:  { bg: "#F4F6FB",               fg: "#888",    icon: Clock },
    planned:     { bg: "#F4F6FB",               fg: "#666",    icon: Clock },
    in_progress: { bg: "rgba(26,79,255,0.10)",  fg: "#1A4FFF", icon: Clock },
    completed:   { bg: "rgba(34,197,94,0.12)",  fg: "#16a34a", icon: CheckCircle2 },
    cancelled:   { bg: "#F4F6FB",               fg: "#888",    icon: AlertCircle },
    active:      { bg: "rgba(34,197,94,0.12)",  fg: "#16a34a", icon: CheckCircle2 },
    recalled:    { bg: "rgba(220,38,38,0.10)",  fg: "#dc2626", icon: AlertCircle },
  })[value] || { bg: "#F4F6FB", fg: "#666", icon: Clock };
  const Icon = cfg.icon;
  return (
    <span className="inline-flex items-center gap-1 text-[11.5px] font-semibold px-2 py-0.5 rounded-full" style={{ background: cfg.bg, color: cfg.fg }}>
      <Icon size={11} /> {value}
    </span>
  );
}

function DataTable({ loading, empty, rows, columns, testId }) {
  if (loading) return <p className="text-[13px] text-[#888] p-2">Loading…</p>;
  if (!rows || rows.length === 0) return <p className="text-[13px] text-[#888] bg-white border border-[#eee] rounded-2xl p-6 text-center" data-testid={`${testId}-empty`}>{empty}</p>;
  return (
    <div className="bg-white border border-[#eee] rounded-2xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]" data-testid={testId}>
          <thead className="bg-[#FAFAFB] text-[#777] text-[11.5px] uppercase tracking-wider">
            <tr>{columns.map((c) => <th key={c.key} className="text-left py-2.5 px-3">{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id || i} className={i % 2 ? "bg-[#FAFAFB]" : ""}>
                {columns.map((c) => <td key={c.key} className="py-2.5 px-3">{c.render(r)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
