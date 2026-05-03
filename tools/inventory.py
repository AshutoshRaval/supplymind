"""
Agent tools for inventory management.

These are @tool decorated functions — the LLM calls them during its ReAct loop.
Each tool queries the SQLite DB and returns structured data the agent reasons over.
"""

from datetime import date, timedelta
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models import Item, Supplier, SupplierItem, ConsumptionLog, engine


@tool
def check_stock_levels() -> list[dict]:
    """
    Check all inventory items that are at or below their restock threshold.
    Returns a list of items with current stock, threshold, and reorder point.
    Call this first to identify which items need attention.
    """
    try:
        with Session(engine) as session:
            items = session.query(Item).filter(
                Item.current_stock <= Item.threshold
            ).all()

            return [
                {
                    "item_id": item.id,
                    "name": item.name,
                    "sku": item.sku,
                    "unit": item.unit,
                    "current_stock": item.current_stock,
                    "threshold": item.threshold,
                    "reorder_point": item.reorder_point,
                    "deficit": item.threshold - item.current_stock,
                }
                for item in items
            ]
    except Exception as e:
        return [{"error": f"check_stock_levels failed: {str(e)}"}]


@tool
def get_consumption_velocity(item_id: int) -> dict:
    """
    Get the average daily consumption rate for an item over the last 30 days.
    Also estimates how many days until stockout at the current rate.
    Use this after check_stock_levels to understand urgency.

    Args:
        item_id: The integer ID of the inventory item.
    """
    try:
        with Session(engine) as session:
            item = session.query(Item).filter(Item.id == item_id).first()
            if not item:
                return {"error": f"Item with id {item_id} not found."}

            cutoff = date.today() - timedelta(days=30)
            result = session.query(
                func.avg(ConsumptionLog.units_consumed),
                func.sum(ConsumptionLog.units_consumed),
                func.count(ConsumptionLog.id),
            ).filter(
                ConsumptionLog.item_id == item_id,
                ConsumptionLog.date >= cutoff,
            ).one()

            avg_daily = round(result[0] or 0, 2)
            total_consumed = result[1] or 0
            log_days = result[2] or 0

            days_to_stockout = (
                round(item.current_stock / avg_daily, 1)
                if avg_daily > 0
                else None
            )

            return {
                "item_id": item.id,
                "name": item.name,
                "current_stock": item.current_stock,
                "unit": item.unit,
                "avg_daily_consumption": avg_daily,
                "total_consumed_last_30_days": total_consumed,
                "log_days_available": log_days,
                "days_to_stockout": days_to_stockout,
                "urgency": (
                    "CRITICAL" if days_to_stockout and days_to_stockout <= 3
                    else "HIGH" if days_to_stockout and days_to_stockout <= 7
                    else "MEDIUM" if days_to_stockout and days_to_stockout <= 14
                    else "LOW"
                ),
            }
    except Exception as e:
        return {"error": f"get_consumption_velocity failed for item {item_id}: {str(e)}"}


@tool
def get_supplier_quotes(item_id: int) -> list[dict]:
    """
    Get all available supplier quotes for a given inventory item.
    Returns price per unit, supplier rating, and lead time in days.
    Use this to compare vendors before making a reorder recommendation.

    Args:
        item_id: The integer ID of the inventory item.
    """
    try:
        with Session(engine) as session:
            item = session.query(Item).filter(Item.id == item_id).first()
            if not item:
                return [{"error": f"Item with id {item_id} not found."}]

            results = (
                session.query(SupplierItem, Supplier)
                .join(Supplier, SupplierItem.supplier_id == Supplier.id)
                .filter(SupplierItem.item_id == item_id)
                .order_by(SupplierItem.price_per_unit)
                .all()
            )

            if not results:
                return [{"message": f"No suppliers found for item '{item.name}'."}]

            return [
                {
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "rating": supplier.rating,
                    "lead_time_days": supplier.lead_time_days,
                    "price_per_unit": si.price_per_unit,
                    "item_name": item.name,
                    "item_sku": item.sku,
                    "unit": item.unit,
                    "score": round(
                        (si.price_per_unit * lead_time_weight(supplier.lead_time_days))
                        / supplier.rating,
                        3,
                    ),
                }
                for si, supplier in results
            ]
    except Exception as e:
        return [{"error": f"get_supplier_quotes failed for item {item_id}: {str(e)}"}]


@tool
def get_low_stock_summary() -> list[dict]:
    """
    Returns a combined summary of all low-stock items with their
    consumption velocity and urgency level in a single call.
    Use this for a quick full picture of what needs restocking.
    """
    try:
        with Session(engine) as session:
            items = session.query(Item).filter(
                Item.current_stock <= Item.threshold
            ).all()

            summary = []
            cutoff = date.today() - timedelta(days=30)

            for item in items:
                result = session.query(
                    func.avg(ConsumptionLog.units_consumed)
                ).filter(
                    ConsumptionLog.item_id == item.id,
                    ConsumptionLog.date >= cutoff,
                ).scalar()

                avg_daily = round(result or 0, 2)

                days_to_stockout = (
                    round(item.current_stock / avg_daily, 1)
                    if avg_daily > 0 else None
                )

                urgency = (
                    "CRITICAL" if days_to_stockout and days_to_stockout <= 3
                    else "HIGH" if days_to_stockout and days_to_stockout <= 7
                    else "MEDIUM" if days_to_stockout and days_to_stockout <= 14
                    else "LOW"
                )

                summary.append({
                    "item_id": item.id,
                    "name": item.name,
                    "sku": item.sku,
                    "unit": item.unit,
                    "current_stock": item.current_stock,
                    "avg_daily_consumption": avg_daily,
                    "days_to_stockout": days_to_stockout,
                    "urgency": urgency,
                    "deficit": item.threshold - item.current_stock,
                })

            urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            summary.sort(key=lambda x: urgency_order.get(x["urgency"], 4))

            return summary
    except Exception as e:
        return [{"error": f"get_low_stock_summary failed: {str(e)}"}]


@tool
def get_best_supplier(item_id: int) -> dict:
    """
    Returns the single best supplier for a given item based on
    price, lead time, and rating. Use this when you need a direct
    recommendation rather than a full comparison list.

    Args:
        item_id: The integer ID of the inventory item.
    """
    try:
        with Session(engine) as session:
            item = session.query(Item).filter(Item.id == item_id).first()
            if not item:
                return {"error": f"Item with id {item_id} not found."}

            results = (
                session.query(SupplierItem, Supplier)
                .join(Supplier, SupplierItem.supplier_id == Supplier.id)
                .filter(SupplierItem.item_id == item_id)
                .all()
            )

            if not results:
                return {"error": f"No suppliers found for item '{item.name}'."}

            scored = []
            for si, supplier in results:
                score = round(
                    (si.price_per_unit * lead_time_weight(supplier.lead_time_days))
                    / supplier.rating,
                    3,
                )
                scored.append((score, si, supplier))

            scored.sort(key=lambda x: x[0])
            best_score, best_si, best_supplier = scored[0]

            reason = (
                f"Best balance of price (${best_si.price_per_unit}/unit), "
                f"lead time ({best_supplier.lead_time_days} days), "
                f"and rating ({best_supplier.rating}/5)."
            )

            return {
                "item_id": item.id,
                "item_name": item.name,
                "item_sku": item.sku,
                "supplier_id": best_supplier.id,
                "supplier_name": best_supplier.name,
                "price_per_unit": best_si.price_per_unit,
                "lead_time_days": best_supplier.lead_time_days,
                "rating": best_supplier.rating,
                "score": best_score,
                "reason": reason,
            }
    except Exception as e:
        return {"error": f"get_best_supplier failed for item {item_id}: {str(e)}"}


def lead_time_weight(days: int) -> float:
    """Penalty multiplier for lead time — longer wait = higher weight."""
    if days <= 2:
        return 1.0
    elif days <= 4:
        return 1.1
    elif days <= 7:
        return 1.25
    else:
        return 1.5
