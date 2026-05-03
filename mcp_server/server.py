"""
MCP Server — exposes inventory tools AND agent pipeline to any MCP client.

Raw data tools (fast, specific queries):
  - check_stock      : which items are below threshold
  - get_quotes       : supplier prices for a given item
  - list_suppliers   : all suppliers with ratings and lead times

Agent-powered tools (full AI pipeline):
  - run_inventory_check : runs the full multi-agent pipeline
                          InventoryMonitor + VendorAdvisor + Supervisor
                          returns complete procurement recommendations

Run with:
  uv run python mcp_server/server.py
"""

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from db.models import Item, Supplier, SupplierItem, engine
from graph.supervisor import run_supervisor

mcp = FastMCP("SupplyMind Inventory")


@mcp.tool()
def check_stock() -> list[dict]:
    """
    Check all inventory items that are at or below their restock threshold.
    Returns item name, SKU, current stock, threshold, and deficit.
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
                    "deficit": item.threshold - item.current_stock,
                }
                for item in items
            ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def get_quotes(item_id: int) -> list[dict]:
    """
    Get all supplier quotes for a given inventory item.
    Returns supplier name, price per unit, lead time, and rating.

    Args:
        item_id: The integer ID of the inventory item.
    """
    try:
        with Session(engine) as session:
            item = session.query(Item).filter(Item.id == item_id).first()
            if not item:
                return [{"error": f"Item {item_id} not found."}]

            results = (
                session.query(SupplierItem, Supplier)
                .join(Supplier, SupplierItem.supplier_id == Supplier.id)
                .filter(SupplierItem.item_id == item_id)
                .order_by(SupplierItem.price_per_unit)
                .all()
            )

            return [
                {
                    "supplier_name": supplier.name,
                    "price_per_unit": si.price_per_unit,
                    "lead_time_days": supplier.lead_time_days,
                    "rating": supplier.rating,
                    "item_name": item.name,
                    "item_sku": item.sku,
                }
                for si, supplier in results
            ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def list_suppliers() -> list[dict]:
    """
    List all suppliers with their ratings and lead times.
    """
    try:
        with Session(engine) as session:
            suppliers = session.query(Supplier).all()
            return [
                {
                    "supplier_id": s.id,
                    "name": s.name,
                    "rating": s.rating,
                    "lead_time_days": s.lead_time_days,
                }
                for s in suppliers
            ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def run_inventory_check() -> str:
    """
    Run the full AI agent pipeline end-to-end.

    This triggers the complete multi-agent system:
      1. InventoryMonitor scans all stock levels
      2. Identifies CRITICAL and HIGH urgency items
      3. VendorAdvisor fetches quotes and computes reorder quantities
      4. Returns a complete procurement report with recommendations

    Use this when you want the AI to do the full analysis,
    not just raw data lookup.
    """
    try:
        return run_supervisor()
    except Exception as e:
        return f"Agent pipeline failed: {str(e)}"


if __name__ == "__main__":
    print("Starting SupplyMind MCP Server...")
    mcp.run(transport="stdio")
