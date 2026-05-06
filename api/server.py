"""
FastAPI backend — bridges the React frontend and the agent pipeline.

Endpoints:
  GET  /api/stock    → all inventory items with status
  GET  /api/flagged  → only CRITICAL and HIGH urgency items
  POST /api/analyze  → runs the full multi-agent pipeline
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db.models import Item, engine
from tools.inventory import get_low_stock_summary
from graph.supervisor import get_recommendations

app = FastAPI(title="SupplyMind API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/stock")
def get_stock() -> list[dict]:
    """Return all inventory items with current stock and status."""
    with Session(engine) as session:
        items = session.query(Item).all()
        result = []
        for item in items:
            if item.current_stock <= item.threshold * 0.5:
                status = "CRITICAL"
            elif item.current_stock <= item.threshold:
                status = "HIGH"
            else:
                status = "OK"

            result.append({
                "id": item.id,
                "name": item.name,
                "sku": item.sku,
                "unit": item.unit,
                "current_stock": item.current_stock,
                "threshold": item.threshold,
                "status": status,
            })
        return result


@app.get("/api/flagged")
def get_flagged() -> list[dict]:
    """Return only CRITICAL and HIGH urgency items."""
    items = get_low_stock_summary.invoke({})
    return [i for i in items if i["urgency"] in ("CRITICAL", "HIGH")]


@app.post("/api/analyze")
def analyze() -> dict:
    """Run the full multi-agent pipeline and return structured recommendations."""
    recommendations = get_recommendations()
    critical = [r for r in recommendations if r["urgency"] == "CRITICAL"]
    high = [r for r in recommendations if r["urgency"] == "HIGH"]
    return {
        "critical": critical,
        "high": high,
        "total": len(recommendations),
    }
