"""
Reorder quantity skill.

Computes how much to order for a given item, factoring in:
- current stock
- reorder point (target level after restocking)
- avg daily consumption (how fast stock depletes)
- supplier lead time (days until delivery arrives)

Used by VendorAdvisor agent to produce a complete order recommendation.
"""

from langchain_core.tools import tool
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta

from db.models import Item, ConsumptionLog, engine


@tool
def calculate_reorder_quantity(item_id: int, lead_time_days: int) -> dict:
    """
    Calculate exactly how many units to order for a given item.

    Takes into account current stock, reorder target, average daily
    consumption, and supplier lead time to ensure stock doesn't run
    out before the order arrives.

    Args:
        item_id: The integer ID of the inventory item.
        lead_time_days: Number of days until supplier delivers the order.
    """
    try:
        with Session(engine) as session:
            item = session.query(Item).filter(Item.id == item_id).first()
            if not item:
                return {"error": f"Item with id {item_id} not found."}

            # get avg daily consumption over last 30 days
            cutoff = date.today() - timedelta(days=30)
            avg_daily = session.query(
                func.avg(ConsumptionLog.units_consumed)
            ).filter(
                ConsumptionLog.item_id == item_id,
                ConsumptionLog.date >= cutoff,
            ).scalar() or 0.0

            avg_daily = round(avg_daily, 2)

            # stock consumed while waiting for delivery
            safety_buffer = round(avg_daily * lead_time_days)

            # how much to order
            quantity_to_order = max(
                0,
                item.reorder_point - item.current_stock + safety_buffer
            )

            return {
                "item_id": item.id,
                "item_name": item.name,
                "item_sku": item.sku,
                "unit": item.unit,
                "current_stock": item.current_stock,
                "reorder_point": item.reorder_point,
                "avg_daily_consumption": avg_daily,
                "lead_time_days": lead_time_days,
                "safety_buffer": safety_buffer,
                "quantity_to_order": quantity_to_order,
                "reasoning": (
                    f"Order {quantity_to_order} {item.unit}: "
                    f"reorder_point({item.reorder_point}) "
                    f"- current_stock({item.current_stock}) "
                    f"+ safety_buffer({safety_buffer}) "
                    f"[{avg_daily}/day × {lead_time_days} days lead time]"
                ),
            }
    except Exception as e:
        return {"error": f"calculate_reorder_quantity failed for item {item_id}: {str(e)}"}
