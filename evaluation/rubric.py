"""
Agent Evaluation Rubric.

Scores the agent's output against ground truth derived from the DB.
5 dimensions, each scored 0-100. Overall score = weighted average.

Dimensions:
  1. Detection Accuracy   — did it find all items below threshold?
  2. Urgency Accuracy     — did it classify urgency correctly?
  3. Rule Compliance      — did it follow business rules?
  4. Supplier Accuracy    — did it recommend the best supplier?
  5. Report Completeness  — does the report have all required sections?
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from db.models import Item, Supplier, SupplierItem, ConsumptionLog, engine
from tools.inventory import get_low_stock_summary, get_best_supplier

logger = logging.getLogger(__name__)


@dataclass
class DimensionScore:
    name: str
    score: float          # 0.0 to 100.0
    weight: float         # how much this dimension contributes
    passed: bool
    details: str
    failures: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    overall_score: float
    grade: str
    dimensions: list[DimensionScore]
    summary: str

    def display(self):
        print("\n" + "=" * 60)
        print("AGENT EVALUATION REPORT")
        print("=" * 60)
        print(f"\nOverall Score : {self.overall_score:.1f}/100  [{self.grade}]")
        print(f"Summary       : {self.summary}\n")
        print("-" * 60)
        for d in self.dimensions:
            status = "PASS" if d.passed else "FAIL"
            print(f"[{status}] {d.name:<30} {d.score:>5.1f}/100")
            print(f"       {d.details}")
            for f in d.failures:
                print(f"       ✗ {f}")
        print("=" * 60)


def _get_ground_truth() -> dict:
    """
    Compute ground truth from DB directly.
    This is what the agent SHOULD report.
    """
    with Session(engine) as session:
        items = session.query(Item).all()
        cutoff = date.today() - timedelta(days=30)

        ground_truth = {
            "low_stock_items": [],
            "urgency_map": {},       # item_id -> urgency
            "best_supplier_map": {}, # item_id -> supplier_name
        }

        for item in items:
            if item.current_stock > item.threshold:
                continue

            avg_daily = session.query(
                func.avg(ConsumptionLog.units_consumed)
            ).filter(
                ConsumptionLog.item_id == item.id,
                ConsumptionLog.date >= cutoff,
            ).scalar() or 0.0

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

            ground_truth["low_stock_items"].append({
                "item_id": item.id,
                "name": item.name,
                "sku": item.sku,
                "days_to_stockout": days_to_stockout,
                "urgency": urgency,
            })
            ground_truth["urgency_map"][item.id] = urgency

            # best supplier from scoring formula
            results = (
                session.query(SupplierItem, Supplier)
                .join(Supplier, SupplierItem.supplier_id == Supplier.id)
                .filter(SupplierItem.item_id == item.id)
                .all()
            )
            if results:
                def score(si, sup):
                    w = 1.0 if sup.lead_time_days <= 2 else \
                        1.1 if sup.lead_time_days <= 4 else \
                        1.25 if sup.lead_time_days <= 7 else 1.5
                    return (si.price_per_unit * w) / sup.rating

                best = min(results, key=lambda x: score(x[0], x[1]))
                ground_truth["best_supplier_map"][item.id] = best[1].name

        return ground_truth


def _score_detection(agent_output: str, ground_truth: dict) -> DimensionScore:
    """Did the agent mention all items that are below threshold?"""
    expected_items = ground_truth["low_stock_items"]
    found = []
    missing = []

    for item in expected_items:
        if item["name"].lower() in agent_output.lower() or \
           item["sku"].lower() in agent_output.lower():
            found.append(item["name"])
        else:
            missing.append(item["name"])

    score = (len(found) / len(expected_items) * 100) if expected_items else 100.0
    passed = score >= 80.0

    return DimensionScore(
        name="Detection Accuracy",
        score=score,
        weight=0.25,
        passed=passed,
        details=f"{len(found)}/{len(expected_items)} items detected",
        failures=[f"Missing: {m}" for m in missing],
    )


def _score_urgency(agent_output: str, ground_truth: dict) -> DimensionScore:
    """Did the agent correctly classify CRITICAL and HIGH items?"""
    expected_items = ground_truth["low_stock_items"]
    correct = 0
    failures = []

    urgent = [i for i in expected_items if i["urgency"] in ("CRITICAL", "HIGH")]

    for item in urgent:
        urgency = item["urgency"]
        name = item["name"].lower()
        if urgency.lower() in agent_output.lower() and name in agent_output.lower():
            correct += 1
        else:
            failures.append(f"{item['name']} should be {urgency}")

    score = (correct / len(urgent) * 100) if urgent else 100.0
    passed = score >= 80.0

    return DimensionScore(
        name="Urgency Classification",
        score=score,
        weight=0.25,
        passed=passed,
        details=f"{correct}/{len(urgent)} urgency labels correct",
        failures=failures,
    )


def _score_rule_compliance(agent_output: str, ground_truth: dict) -> DimensionScore:
    """
    Key rule: never recommend a supplier whose lead_time > days_to_stockout
    without flagging it as a problem.
    Check: for CRITICAL items, agent must warn about tight lead time.
    """
    critical_items = [
        i for i in ground_truth["low_stock_items"]
        if i["urgency"] == "CRITICAL"
    ]

    if not critical_items:
        return DimensionScore(
            name="Rule Compliance",
            score=100.0,
            weight=0.20,
            passed=True,
            details="No CRITICAL items — rule not applicable",
        )

    flagged = 0
    failures = []

    for item in critical_items:
        name = item["name"].lower()
        # agent should warn about lead time risk for critical items
        warning_keywords = ["lead time", "expedit", "urgent", "critical", "risk", "exceed"]
        context = agent_output.lower()
        if name in context and any(kw in context for kw in warning_keywords):
            flagged += 1
        else:
            failures.append(f"{item['name']} CRITICAL but no lead time warning found")

    score = (flagged / len(critical_items) * 100)
    passed = score >= 80.0

    return DimensionScore(
        name="Rule Compliance",
        score=score,
        weight=0.20,
        passed=passed,
        details=f"{flagged}/{len(critical_items)} CRITICAL items properly warned",
        failures=failures,
    )


def _score_supplier(agent_output: str, ground_truth: dict) -> DimensionScore:
    """Did the agent recommend the correct (best scored) supplier?"""
    urgent_items = [
        i for i in ground_truth["low_stock_items"]
        if i["urgency"] in ("CRITICAL", "HIGH")
    ]

    correct = 0
    failures = []

    for item in urgent_items:
        item_id = item["item_id"]
        expected_supplier = ground_truth["best_supplier_map"].get(item_id)
        if not expected_supplier:
            continue

        if expected_supplier.lower() in agent_output.lower():
            correct += 1
        else:
            failures.append(
                f"{item['name']}: expected {expected_supplier}"
            )

    total = len([i for i in urgent_items
                 if i["item_id"] in ground_truth["best_supplier_map"]])
    score = (correct / total * 100) if total else 100.0
    passed = score >= 70.0

    return DimensionScore(
        name="Supplier Recommendation",
        score=score,
        weight=0.20,
        passed=passed,
        details=f"{correct}/{total} correct supplier recommendations",
        failures=failures,
    )


def _score_completeness(agent_output: str, ground_truth: dict) -> DimensionScore:
    """Does the report contain all required sections?"""
    required = {
        "urgency level": ["critical", "high", "urgent"],
        "item name": [i["name"].lower() for i in ground_truth["low_stock_items"][:3]],
        "supplier info": ["supplier", "quicksupply", "bulkmart", "fasttrack"],
        "price info": ["$", "price", "cost"],
        "action required": ["order", "restock", "immediate", "action"],
    }

    present = 0
    failures = []
    output_lower = agent_output.lower()

    for section, keywords in required.items():
        if any(kw in output_lower for kw in keywords):
            present += 1
        else:
            failures.append(f"Missing section: {section}")

    score = (present / len(required) * 100)
    passed = score >= 80.0

    return DimensionScore(
        name="Report Completeness",
        score=score,
        weight=0.10,
        passed=passed,
        details=f"{present}/{len(required)} required sections present",
        failures=failures,
    )


def evaluate(agent_output: str) -> EvaluationResult:
    """
    Run the full rubric against an agent's output string.
    Returns an EvaluationResult with scores for all 5 dimensions.
    """
    logger.info("Running evaluation rubric...")

    try:
        ground_truth = _get_ground_truth()
    except Exception as e:
        logger.error(f"Failed to compute ground truth: {e}")
        raise

    dimensions = [
        _score_detection(agent_output, ground_truth),
        _score_urgency(agent_output, ground_truth),
        _score_rule_compliance(agent_output, ground_truth),
        _score_supplier(agent_output, ground_truth),
        _score_completeness(agent_output, ground_truth),
    ]

    overall = sum(d.score * d.weight for d in dimensions)

    grade = (
        "A" if overall >= 90
        else "B" if overall >= 80
        else "C" if overall >= 70
        else "D" if overall >= 60
        else "F"
    )

    passed_count = sum(1 for d in dimensions if d.passed)
    summary = (
        f"{passed_count}/{len(dimensions)} dimensions passed. "
        f"{'Agent performing well.' if overall >= 80 else 'Agent needs improvement.'}"
    )

    return EvaluationResult(
        overall_score=round(overall, 1),
        grade=grade,
        dimensions=dimensions,
        summary=summary,
    )
