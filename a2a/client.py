"""
A2A Client — calls the VendorAdvisor A2A server over HTTP.

Used by the Supervisor instead of calling run_vendor_advisor() directly.
"""

import httpx

A2A_SERVER_URL = "http://localhost:8001"


def call_vendor_advisor(item_id: int, urgency: str, days_to_stockout: float) -> str:
    """
    Send a recommendation request to the VendorAdvisor A2A server.
    Returns the recommendation string.
    """
    payload = {
        "item_id": item_id,
        "urgency": urgency,
        "days_to_stockout": days_to_stockout,
    }

    try:
        response = httpx.post(
            f"{A2A_SERVER_URL}/recommend",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["recommendation"]

    except httpx.ConnectError:
        return (
            f"[A2A ERROR] VendorAdvisor server is not running at {A2A_SERVER_URL}. "
            "Start it with: uv run uvicorn a2a.server:app --port 8001"
        )
    except httpx.HTTPStatusError as e:
        return f"[A2A ERROR] Server returned {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"[A2A ERROR] {str(e)}"
