"""
Supervisor graph — orchestrates InventoryMonitor and VendorAdvisor agents.

Flow:
  1. Calls get_low_stock_summary directly for structured data
  2. Filters CRITICAL and HIGH urgency items
  3. For each flagged item, calls VendorAdvisor agent
  4. Combines everything into one final report
"""

from tools.inventory import get_low_stock_summary
from a2a.client import call_vendor_advisor


def get_recommendations() -> list[dict]:
    """Return structured recommendations for each urgent item."""
    print("[Supervisor] Step 1: Scanning inventory for low stock items...")
    flagged_items = get_low_stock_summary.invoke({})

    if flagged_items and "error" in flagged_items[0]:
        return []

    urgent_items = [
        item for item in flagged_items
        if item["urgency"] in ("CRITICAL", "HIGH")
    ]

    if not urgent_items:
        return []

    print(f"[Supervisor] Found {len(urgent_items)} urgent items. Calling VendorAdvisor...")

    recommendations = []
    for item in urgent_items:
        print(f"[Supervisor] → Getting recommendation for {item['name']} ({item['urgency']})")
        recommendation = call_vendor_advisor(
            item_id=item["item_id"],
            urgency=item["urgency"],
            days_to_stockout=item["days_to_stockout"] or 0,
        )
        recommendations.append({
            "item_name": item["name"],
            "sku": item["sku"],
            "urgency": item["urgency"],
            "days_to_stockout": item["days_to_stockout"],
            "recommendation": recommendation,
        })

    return recommendations


def run_supervisor() -> str:
    recommendations = get_recommendations()
    if not recommendations:
        return "All inventory levels are healthy. No restocking needed."
    return _build_final_report(recommendations)


def _build_final_report(recommendations: list[dict]) -> str:
    """Combine all VendorAdvisor outputs into one final report."""
    lines = []
    lines.append("=" * 60)
    lines.append("SUPPLYMIND — PROCUREMENT REPORT")
    lines.append("=" * 60)

    critical = [r for r in recommendations if r["urgency"] == "CRITICAL"]
    high = [r for r in recommendations if r["urgency"] == "HIGH"]

    if critical:
        lines.append(f"\n🚨 CRITICAL ({len(critical)} items)\n")
        for r in critical:
            lines.append(f"--- {r['item_name']} ({r['sku']}) ---")
            lines.append(f"Days to stockout: {r['days_to_stockout']}")
            lines.append(r["recommendation"])
            lines.append("")

    if high:
        lines.append(f"\n⚠️  HIGH PRIORITY ({len(high)} items)\n")
        for r in high:
            lines.append(f"--- {r['item_name']} ({r['sku']}) ---")
            lines.append(f"Days to stockout: {r['days_to_stockout']}")
            lines.append(r["recommendation"])
            lines.append("")

    lines.append("=" * 60)
    lines.append(f"Total items requiring action: {len(recommendations)}")
    lines.append("=" * 60)

    return "\n".join(lines)
