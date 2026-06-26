"""
Operations & Production module — Zynthoro
==========================================

Provides REST endpoints for the full production-management stack:

- Recipes & formulas (with allergens, versioning, cost roll-up)
- Bill of Materials (multi-level BOMs)
- Production orders / batches
- Work orders (per-step instructions, status)
- Quality control inspections
- Lot / batch traceability
- Cost summaries

Plan gating (enforced by `_require_plan`):
- Business+   → recipes + basic production orders
- Agency+     → full BOM + quality control
- Enterprise+ → full traceability, compliance, multi-location
"""

from datetime import datetime, timezone
from typing import List, Optional, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from motor.motor_asyncio import AsyncIOMotorDatabase


# ========================================================================
#  Plan gating
# ========================================================================
_PLAN_RANK = {
    "Presale": 0, "Starter": 1, "Creator": 2, "Business": 3, "Agency": 4,
    "Enterprise Basic": 5, "Enterprise Plus": 6, "Enterprise Advanced": 7,
    "Enterprise Elite": 7, "Enterprise Unlimited": 7,
}

_TIER_MIN_RANK = {
    "business": _PLAN_RANK["Business"],
    "agency": _PLAN_RANK["Agency"],
    "enterprise": _PLAN_RANK["Enterprise Basic"],
}


def _plan_rank(plan: Optional[str]) -> int:
    return _PLAN_RANK.get(plan or "Presale", 0)


def _require_plan(user: dict, tier: str) -> None:
    """Raise 402 if user is below the required tier.

    Demo accounts and `is_unlimited` users always pass.
    """
    if user.get("is_demo") or user.get("is_unlimited") or user.get("billing_exempt"):
        return
    needed = _TIER_MIN_RANK.get(tier, _PLAN_RANK["Business"])
    if _plan_rank(user.get("subscription_plan")) < needed:
        raise HTTPException(
            status_code=402,
            detail=f"Upgrade required: this Operations feature is available from {tier.title()} plan.",
        )


# ========================================================================
#  Pydantic models
# ========================================================================
class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RecipeIngredient(_Base):
    name: str
    quantity: float = Field(ge=0)
    unit: str = "g"
    cost_per_unit_eur: float = Field(default=0.0, ge=0)


class RecipeIn(_Base):
    name: str = Field(min_length=1, max_length=200)
    code: Optional[str] = Field(default=None, max_length=60)
    description: Optional[str] = Field(default=None, max_length=2000)
    yield_qty: float = Field(default=1.0, ge=0)
    yield_unit: str = "unit"
    ingredients: List[RecipeIngredient] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    labour_cost_eur: float = Field(default=0.0, ge=0)
    overhead_eur: float = Field(default=0.0, ge=0)


class BomLine(_Base):
    sku: str
    name: str
    quantity: float = Field(ge=0)
    unit: str = "unit"
    level: int = Field(default=1, ge=1, le=10)
    cost_eur: float = Field(default=0.0, ge=0)


class BomIn(_Base):
    name: str = Field(min_length=1, max_length=200)
    finished_sku: str = Field(min_length=1, max_length=60)
    description: Optional[str] = Field(default=None, max_length=2000)
    lines: List[BomLine] = Field(default_factory=list)


class ProductionOrderIn(_Base):
    name: str = Field(min_length=1, max_length=200)
    recipe_id: Optional[str] = None
    bom_id: Optional[str] = None
    quantity: float = Field(ge=0)
    unit: str = "unit"
    scheduled_for: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=2000)


class WorkOrderStepIn(_Base):
    title: str = Field(min_length=1, max_length=200)
    instruction: Optional[str] = Field(default=None, max_length=4000)
    quality_checks: List[str] = Field(default_factory=list)


class WorkOrderIn(_Base):
    production_order_id: str
    name: str = Field(min_length=1, max_length=200)
    assignee_email: Optional[str] = None
    steps: List[WorkOrderStepIn] = Field(default_factory=list)


class WorkOrderStatusUpdate(_Base):
    status: Literal["planned", "in_progress", "completed", "cancelled"]


class QualityInspectionIn(_Base):
    production_order_id: str
    batch_lot: Optional[str] = None
    checklist: List[str] = Field(default_factory=list)
    results: List[Literal["pass", "fail", "skip"]] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2000)


class LotIn(_Base):
    production_order_id: str
    expiry_date: Optional[str] = None
    raw_material_lots: List[str] = Field(default_factory=list)


# ========================================================================
#  Router factory
# ========================================================================
def build_router(db: AsyncIOMotorDatabase, get_user) -> APIRouter:
    """Construct the operations router with shared db + auth dependency."""
    router = APIRouter(prefix="/api/operations", tags=["operations"])

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _wo(user: dict) -> str:
        return user.get("id") or user.get("email")

    # ---------------------------------------------------------------- Recipes
    @router.post("/recipes", status_code=201)
    async def create_recipe(payload: RecipeIn, user=Depends(get_user)):
        _require_plan(user, "business")
        material_cost = sum(i.quantity * i.cost_per_unit_eur for i in payload.ingredients)
        cost_total = round(material_cost + payload.labour_cost_eur + payload.overhead_eur, 2)
        cost_per_unit = round(cost_total / payload.yield_qty, 2) if payload.yield_qty else 0.0
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "version": 1,
            "name": payload.name,
            "code": payload.code,
            "description": payload.description,
            "yield_qty": payload.yield_qty,
            "yield_unit": payload.yield_unit,
            "ingredients": [i.model_dump() for i in payload.ingredients],
            "allergens": payload.allergens,
            "labour_cost_eur": payload.labour_cost_eur,
            "overhead_eur": payload.overhead_eur,
            "material_cost_eur": round(material_cost, 2),
            "cost_total_eur": cost_total,
            "cost_per_unit_eur": cost_per_unit,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.recipes.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/recipes")
    async def list_recipes(user=Depends(get_user)):
        _require_plan(user, "business")
        rows = await db.recipes.find(
            {"workspace_owner": _wo(user)}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        return {"recipes": rows, "count": len(rows)}

    @router.patch("/recipes/{rid}")
    async def update_recipe(rid: str, payload: RecipeIn, user=Depends(get_user)):
        _require_plan(user, "business")
        existing = await db.recipes.find_one({"id": rid, "workspace_owner": _wo(user)})
        if not existing:
            raise HTTPException(404, "Recipe not found")
        material_cost = sum(i.quantity * i.cost_per_unit_eur for i in payload.ingredients)
        cost_total = round(material_cost + payload.labour_cost_eur + payload.overhead_eur, 2)
        cost_per_unit = round(cost_total / payload.yield_qty, 2) if payload.yield_qty else 0.0
        new_version = int(existing.get("version", 1)) + 1
        update = {
            **payload.model_dump(),
            "ingredients": [i.model_dump() for i in payload.ingredients],
            "version": new_version,
            "material_cost_eur": round(material_cost, 2),
            "cost_total_eur": cost_total,
            "cost_per_unit_eur": cost_per_unit,
            "updated_at": _now(),
        }
        await db.recipes.update_one({"id": rid}, {"$set": update})
        return {"ok": True, "version": new_version}

    @router.delete("/recipes/{rid}")
    async def delete_recipe(rid: str, user=Depends(get_user)):
        _require_plan(user, "business")
        res = await db.recipes.delete_one({"id": rid, "workspace_owner": _wo(user)})
        if not res.deleted_count:
            raise HTTPException(404, "Recipe not found")
        return {"ok": True}

    # ---------------------------------------------------------------- BOMs
    @router.post("/boms", status_code=201)
    async def create_bom(payload: BomIn, user=Depends(get_user)):
        _require_plan(user, "agency")
        total_cost = round(sum(line.quantity * line.cost_eur for line in payload.lines), 2)
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "version": 1,
            "name": payload.name,
            "finished_sku": payload.finished_sku,
            "description": payload.description,
            "lines": [line.model_dump() for line in payload.lines],
            "total_cost_eur": total_cost,
            "max_level": max([line.level for line in payload.lines], default=1),
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.boms.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/boms")
    async def list_boms(user=Depends(get_user)):
        _require_plan(user, "agency")
        rows = await db.boms.find(
            {"workspace_owner": _wo(user)}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        return {"boms": rows, "count": len(rows)}

    @router.delete("/boms/{bid}")
    async def delete_bom(bid: str, user=Depends(get_user)):
        _require_plan(user, "agency")
        res = await db.boms.delete_one({"id": bid, "workspace_owner": _wo(user)})
        if not res.deleted_count:
            raise HTTPException(404, "BOM not found")
        return {"ok": True}

    # ---------------------------------------------------------------- Production orders
    @router.post("/production-orders", status_code=201)
    async def create_production_order(payload: ProductionOrderIn, user=Depends(get_user)):
        _require_plan(user, "business")
        order_no = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "order_no": order_no,
            "status": "planned",
            "name": payload.name,
            "recipe_id": payload.recipe_id,
            "bom_id": payload.bom_id,
            "quantity": payload.quantity,
            "unit": payload.unit,
            "scheduled_for": payload.scheduled_for,
            "location": payload.location,
            "notes": payload.notes,
            "actual_quantity": None,
            "cost_estimate_eur": 0.0,
            "cost_actual_eur": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        # Pull cost estimate from recipe if linked
        if payload.recipe_id:
            recipe = await db.recipes.find_one({"id": payload.recipe_id}, {"_id": 0})
            if recipe:
                doc["cost_estimate_eur"] = round(
                    (recipe.get("cost_per_unit_eur") or 0) * payload.quantity, 2
                )
        await db.production_orders.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/production-orders")
    async def list_production_orders(user=Depends(get_user), status: Optional[str] = None):
        _require_plan(user, "business")
        q = {"workspace_owner": _wo(user)}
        if status:
            q["status"] = status
        rows = await db.production_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"orders": rows, "count": len(rows)}

    @router.patch("/production-orders/{oid}/status")
    async def update_po_status(oid: str, payload: WorkOrderStatusUpdate, user=Depends(get_user)):
        _require_plan(user, "business")
        res = await db.production_orders.update_one(
            {"id": oid, "workspace_owner": _wo(user)},
            {"$set": {"status": payload.status, "updated_at": _now()}},
        )
        if not res.matched_count:
            raise HTTPException(404, "Production order not found")
        return {"ok": True}

    # ---------------------------------------------------------------- Work orders
    @router.post("/work-orders", status_code=201)
    async def create_work_order(payload: WorkOrderIn, user=Depends(get_user)):
        _require_plan(user, "business")
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "production_order_id": payload.production_order_id,
            "name": payload.name,
            "assignee_email": (payload.assignee_email or "").lower() or None,
            "status": "planned",
            "steps": [
                {**s.model_dump(), "id": str(uuid.uuid4()), "status": "planned", "results": []}
                for s in payload.steps
            ],
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.work_orders.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/work-orders")
    async def list_work_orders(user=Depends(get_user), production_order_id: Optional[str] = None):
        _require_plan(user, "business")
        q = {"workspace_owner": _wo(user)}
        if production_order_id:
            q["production_order_id"] = production_order_id
        rows = await db.work_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"work_orders": rows, "count": len(rows)}

    @router.patch("/work-orders/{wid}/status")
    async def update_work_order_status(wid: str, payload: WorkOrderStatusUpdate, user=Depends(get_user)):
        _require_plan(user, "business")
        res = await db.work_orders.update_one(
            {"id": wid, "workspace_owner": _wo(user)},
            {"$set": {"status": payload.status, "updated_at": _now()}},
        )
        if not res.matched_count:
            raise HTTPException(404, "Work order not found")
        return {"ok": True}

    # ---------------------------------------------------------------- Quality
    @router.post("/quality-inspections", status_code=201)
    async def create_inspection(payload: QualityInspectionIn, user=Depends(get_user)):
        _require_plan(user, "agency")
        pass_count = payload.results.count("pass")
        fail_count = payload.results.count("fail")
        overall = "pass" if fail_count == 0 and pass_count > 0 else "fail" if fail_count > 0 else "incomplete"
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "production_order_id": payload.production_order_id,
            "batch_lot": payload.batch_lot,
            "checklist": payload.checklist,
            "results": payload.results,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "overall": overall,
            "notes": payload.notes,
            "created_at": _now(),
        }
        await db.quality_inspections.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/quality-inspections")
    async def list_inspections(user=Depends(get_user)):
        _require_plan(user, "agency")
        rows = await db.quality_inspections.find(
            {"workspace_owner": _wo(user)}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        return {"inspections": rows, "count": len(rows)}

    # ---------------------------------------------------------------- Lots / traceability
    @router.post("/lots", status_code=201)
    async def create_lot(payload: LotIn, user=Depends(get_user)):
        _require_plan(user, "enterprise")
        lot_no = f"LOT-{datetime.now(timezone.utc).strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        doc = {
            "id": str(uuid.uuid4()),
            "workspace_owner": _wo(user),
            "lot_no": lot_no,
            "production_order_id": payload.production_order_id,
            "expiry_date": payload.expiry_date,
            "raw_material_lots": payload.raw_material_lots,
            "status": "active",
            "created_at": _now(),
        }
        await db.lots.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/lots")
    async def list_lots(user=Depends(get_user)):
        _require_plan(user, "enterprise")
        rows = await db.lots.find(
            {"workspace_owner": _wo(user)}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        return {"lots": rows, "count": len(rows)}

    @router.get("/lots/{lot_no}/trace")
    async def trace_lot(lot_no: str, user=Depends(get_user)):
        _require_plan(user, "enterprise")
        lot = await db.lots.find_one(
            {"lot_no": lot_no, "workspace_owner": _wo(user)}, {"_id": 0}
        )
        if not lot:
            raise HTTPException(404, "Lot not found")
        po = await db.production_orders.find_one(
            {"id": lot["production_order_id"]}, {"_id": 0}
        )
        upstream = []
        for raw_lot_no in lot.get("raw_material_lots", []):
            up = await db.lots.find_one({"lot_no": raw_lot_no}, {"_id": 0})
            if up:
                upstream.append(up)
        return {"lot": lot, "production_order": po, "upstream_lots": upstream}

    @router.post("/lots/{lot_no}/recall")
    async def recall_lot(lot_no: str, user=Depends(get_user)):
        _require_plan(user, "enterprise")
        res = await db.lots.update_one(
            {"lot_no": lot_no, "workspace_owner": _wo(user)},
            {"$set": {"status": "recalled", "recalled_at": _now()}},
        )
        if not res.matched_count:
            raise HTTPException(404, "Lot not found")
        return {"ok": True, "status": "recalled"}

    # ---------------------------------------------------------------- Cost summary
    @router.get("/costs/summary")
    async def cost_summary(user=Depends(get_user)):
        _require_plan(user, "business")
        wo = _wo(user)
        recipes = await db.recipes.find({"workspace_owner": wo}, {"_id": 0}).to_list(500)
        orders = await db.production_orders.find({"workspace_owner": wo}, {"_id": 0}).to_list(500)
        avg_unit_cost = (
            round(sum(r.get("cost_per_unit_eur") or 0 for r in recipes) / len(recipes), 2)
            if recipes else 0.0
        )
        total_estimate = round(sum(o.get("cost_estimate_eur") or 0 for o in orders), 2)
        total_actual = round(sum(o.get("cost_actual_eur") or 0 for o in orders if o.get("cost_actual_eur")), 2)
        return {
            "recipe_count": len(recipes),
            "production_order_count": len(orders),
            "average_unit_cost_eur": avg_unit_cost,
            "estimated_production_cost_eur": total_estimate,
            "actual_production_cost_eur": total_actual,
            "variance_eur": round(total_actual - total_estimate, 2) if total_actual else 0.0,
        }

    return router
