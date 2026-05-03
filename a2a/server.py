"""
A2A Server — exposes VendorAdvisor as an independent HTTP service.

Any agent (on any machine) can call this server via HTTP:
  POST /recommend
  {"item_id": 2, "urgency": "HIGH", "days_to_stockout": 5.0}

Run with:
  uv run uvicorn a2a.server:app --host 0.0.0.0 --port 8001 --reload
"""

from fastapi import FastAPI
from pydantic import BaseModel
from graph.vendor_agent import run_vendor_advisor

app = FastAPI(title="VendorAdvisor A2A Service")


class RecommendRequest(BaseModel):
    item_id: int
    urgency: str
    days_to_stockout: float


class RecommendResponse(BaseModel):
    item_id: int
    urgency: str
    recommendation: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "VendorAdvisor"}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    """
    Call VendorAdvisor agent for a single item.
    Returns supplier recommendation and reorder quantity.
    """
    result = run_vendor_advisor(
        item_id=req.item_id,
        urgency=req.urgency,
        days_to_stockout=req.days_to_stockout,
    )
    return RecommendResponse(
        item_id=req.item_id,
        urgency=req.urgency,
        recommendation=result,
    )
