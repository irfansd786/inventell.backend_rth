import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.recommendation import Recommendation
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.transfer import Transfer
from app.models.warehouse import Warehouse
from app.models.activity_log import ActivityLog
from app.ml.risk_engine import evaluate_inventory_risk


def sync_recommendations(db: Session) -> list[Recommendation]:
    """Ensures persistent Recommendation records exist in DB for all inventory risk profiles."""
    products = db.query(Product).all()
    inv_map = {inv.product_id: inv for inv in db.query(Inventory).all()}

    existing_recs = {r.product_id: r for r in db.query(Recommendation).all()}

    synced = []
    for prod in products:
        inv = inv_map.get(prod.id)
        store_stk = inv.store_stock if inv else 0
        wh_stk = inv.warehouse_stock if inv else 0
        reorder = inv.reorder_level if inv else 15

        pred_7d = round(max(store_stk * 2.2, 28.0), 1)
        daily_avg = round(pred_7d / 7.0, 1)

        eval_result = evaluate_inventory_risk(
            product_id=prod.id,
            product_name=prod.name,
            category=prod.category or "General",
            current_store_stock=store_stk,
            warehouse_stock=wh_stk,
            predicted_7d_demand=pred_7d,
            daily_sales_avg=daily_avg,
            unit_price=prod.price or 15.0,
            reorder_level=reorder,
        )

        rec_type = "REPLENISHMENT"
        discount = 0
        if eval_result["overstock_risk"]:
            rec_type = "PROMOTION"
            discount = 15
        elif eval_result["slow_moving_risk"]:
            rec_type = "MARKDOWN"
            discount = 20
        elif eval_result["stockout_risk"]:
            rec_type = "REPLENISHMENT"

        rec = existing_recs.get(prod.id)
        if not rec:
            rec = Recommendation(
                product_id=prod.id,
                recommendation_type=rec_type,
                title=f"{eval_result['recommended_action']} for {prod.name}",
                reason=eval_result["recommendation_reason"],
                discount_pct=discount,
                suggested_qty=eval_result["suggested_transfer_qty"],
                priority=eval_result["priority"].upper(),
                status="PENDING",
            )
            db.add(rec)
        synced.append(rec)

    db.commit()
    return synced


def list_recommendations(
    db: Session,
    status: str | None = None,
    recommendation_type: str | None = None,
) -> list[dict]:
    """Return persistent list of recommendations with full product & inventory context."""
    sync_recommendations(db)

    q = db.query(Recommendation).join(Product, Product.id == Recommendation.product_id)
    if status and status != "All":
        q = q.filter(Recommendation.status == status)
    if recommendation_type and recommendation_type != "All":
        q = q.filter(Recommendation.recommendation_type == recommendation_type)

    recs = q.order_by(Recommendation.updated_at.desc()).all()
    inv_map = {inv.product_id: inv for inv in db.query(Inventory).all()}

    out = []
    for r in recs:
        p = r.product
        inv = inv_map.get(r.product_id)
        out.append({
            "id": r.id,
            "product_id": r.product_id,
            "product_name": p.name if p else f"Product #{r.product_id}",
            "sku": p.sku if p else f"SKU-{r.product_id}",
            "category": p.category if p else "General",
            "price": p.price if p else 0.0,
            "recommendation_type": r.recommendation_type,
            "title": r.title,
            "reason": r.reason,
            "discount_pct": r.discount_pct,
            "suggested_qty": r.suggested_qty,
            "priority": r.priority,
            "status": r.status,
            "store_stock": inv.store_stock if inv else 0,
            "warehouse_stock": inv.warehouse_stock if inv else 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return out


def approve_recommendation(db: Session, rec_id: int) -> dict:
    """Transition recommendation state from PENDING to APPROVED."""
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")

    if rec.status in ("APPROVED", "LAUNCHED", "COMPLETED"):
        # Already approved/launched, return cleanly
        return list_recommendations(db, status=None)[0]

    if rec.status == "REJECTED":
        raise HTTPException(status_code=422, detail="Cannot approve a REJECTED recommendation")

    rec.status = "APPROVED"
    rec.updated_at = datetime.datetime.now(datetime.timezone.utc)

    # Log activity
    log = ActivityLog(
        action=f"RECOMMENDATION_APPROVED",
        entity="Recommendation",
        details=f"Approved {rec.recommendation_type} recommendation for Product #{rec.product_id}",
    )
    db.add(log)
    db.commit()
    db.refresh(rec)

    return {
        "id": rec.id,
        "product_id": rec.product_id,
        "status": rec.status,
        "message": "Recommendation approved successfully.",
    }


def launch_recommendation(db: Session, rec_id: int) -> dict:
    """Transition recommendation state from APPROVED to LAUNCHED and trigger workflow."""
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")

    if rec.status == "PENDING":
        # Auto-approve if directly launched
        rec.status = "APPROVED"

    if rec.status == "REJECTED":
        raise HTTPException(status_code=422, detail="Cannot launch a REJECTED recommendation")

    rec.status = "LAUNCHED"
    rec.updated_at = datetime.datetime.now(datetime.timezone.utc)

    # Trigger Real Business Workflow based on recommendation type
    if rec.recommendation_type == "REPLENISHMENT" and rec.suggested_qty > 0:
        # Create persistent Warehouse Transfer order
        wh = db.query(Warehouse).first()
        wh_id = wh.id if wh else 1
        count = db.query(Transfer).count() + 1
        trf = Transfer(
            transfer_number=f"TRF-{count:05d}",
            warehouse_id=wh_id,
            product_id=rec.product_id,
            quantity=rec.suggested_qty,
            status="PENDING",
        )
        db.add(trf)

    # Log Activity
    log = ActivityLog(
        action="RECOMMENDATION_LAUNCHED",
        entity="Recommendation",
        details=f"Launched {rec.recommendation_type} action for Product #{rec.product_id}",
    )
    db.add(log)
    db.commit()
    db.refresh(rec)

    return {
        "id": rec.id,
        "product_id": rec.product_id,
        "status": rec.status,
        "message": f"{rec.recommendation_type} campaign launched successfully.",
    }


def reject_recommendation(db: Session, rec_id: int) -> dict:
    """Transition recommendation state to REJECTED."""
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation {rec_id} not found")

    rec.status = "REJECTED"
    rec.updated_at = datetime.datetime.now(datetime.timezone.utc)

    log = ActivityLog(
        action="RECOMMENDATION_REJECTED",
        entity="Recommendation",
        details=f"Rejected recommendation for Product #{rec.product_id}",
    )
    db.add(log)
    db.commit()
    db.refresh(rec)

    return {
        "id": rec.id,
        "product_id": rec.product_id,
        "status": rec.status,
        "message": "Recommendation rejected.",
    }
