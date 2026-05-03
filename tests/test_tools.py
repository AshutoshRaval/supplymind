"""
Level 1 — Tool unit tests.

Tests each tool in isolation using an in-memory DB.
No LLM calls, no API key needed. Fast.
"""

import pytest
from unittest.mock import patch


# ─── check_stock_levels ───────────────────────────────────────────────────────

def test_check_stock_levels_returns_low_items(seeded_engine):
    """Items below threshold should appear in results."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import check_stock_levels
        result = check_stock_levels.invoke({})

    names = [r["name"] for r in result]
    assert "Toner Cartridge" in names


def test_check_stock_levels_excludes_ok_items(seeded_engine):
    """Items above threshold should NOT appear in results."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import check_stock_levels
        result = check_stock_levels.invoke({})

    names = [r["name"] for r in result]
    assert "Office Chair" not in names


def test_check_stock_levels_deficit_is_correct(seeded_engine):
    """Deficit = threshold - current_stock."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import check_stock_levels
        result = check_stock_levels.invoke({})

    toner = next(r for r in result if r["name"] == "Toner Cartridge")
    assert toner["deficit"] == 6   # threshold(10) - stock(4)


# ─── get_consumption_velocity ────────────────────────────────────────────────

def test_get_consumption_velocity_known_rate(seeded_engine):
    """Avg daily consumption should be ~1.0 for Toner (seeded at 1/day)."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_consumption_velocity
        result = get_consumption_velocity.invoke({"item_id": 1})

    assert result["avg_daily_consumption"] == pytest.approx(1.0, abs=0.1)


def test_get_consumption_velocity_days_to_stockout(seeded_engine):
    """4 units at 1/day = 4.0 days to stockout."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_consumption_velocity
        result = get_consumption_velocity.invoke({"item_id": 1})

    assert result["days_to_stockout"] == pytest.approx(4.0, abs=0.5)


def test_get_consumption_velocity_urgency_is_high(seeded_engine):
    """4 days to stockout → HIGH urgency (3 < days <= 7)."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_consumption_velocity
        result = get_consumption_velocity.invoke({"item_id": 1})

    assert result["urgency"] == "HIGH"


def test_get_consumption_velocity_invalid_item(seeded_engine):
    """Invalid item_id should return an error dict, not raise exception."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_consumption_velocity
        result = get_consumption_velocity.invoke({"item_id": 9999})

    assert "error" in result


# ─── get_supplier_quotes ─────────────────────────────────────────────────────

def test_get_supplier_quotes_returns_both_suppliers(seeded_engine):
    """Both FastTrack and BulkMart supply Toner — both should appear."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_supplier_quotes
        result = get_supplier_quotes.invoke({"item_id": 1})

    supplier_names = [r["supplier_name"] for r in result]
    assert "FastTrack Ltd" in supplier_names
    assert "BulkMart" in supplier_names


def test_get_supplier_quotes_sorted_by_price(seeded_engine):
    """Results should be sorted cheapest first."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_supplier_quotes
        result = get_supplier_quotes.invoke({"item_id": 1})

    prices = [r["price_per_unit"] for r in result]
    assert prices == sorted(prices)


def test_get_supplier_quotes_invalid_item(seeded_engine):
    """Invalid item_id should return error list, not raise exception."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_supplier_quotes
        result = get_supplier_quotes.invoke({"item_id": 9999})

    assert "error" in result[0]


# ─── get_best_supplier ───────────────────────────────────────────────────────

def test_get_best_supplier_returns_one(seeded_engine):
    """Should return a single dict, not a list."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_best_supplier
        result = get_best_supplier.invoke({"item_id": 1})

    assert isinstance(result, dict)
    assert "supplier_name" in result


def test_get_best_supplier_prefers_fast_over_cheap(seeded_engine):
    """
    FastTrack: $50, 2-day lead, 4.2 rating → score = (50 * 1.0) / 4.2 = 11.9
    BulkMart:  $38, 7-day lead, 3.8 rating → score = (38 * 1.25) / 3.8 = 12.5
    FastTrack should win (lower score = better).
    """
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_best_supplier
        result = get_best_supplier.invoke({"item_id": 1})

    assert result["supplier_name"] == "FastTrack Ltd"


def test_get_best_supplier_invalid_item(seeded_engine):
    """Invalid item_id should return error dict, not raise exception."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_best_supplier
        result = get_best_supplier.invoke({"item_id": 9999})

    assert "error" in result


# ─── get_low_stock_summary ───────────────────────────────────────────────────

def test_get_low_stock_summary_only_low_items(seeded_engine):
    """Summary should only contain items below threshold."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_low_stock_summary
        result = get_low_stock_summary.invoke({})

    names = [r["name"] for r in result]
    assert "Toner Cartridge" in names
    assert "Office Chair" not in names


def test_get_low_stock_summary_no_duplicates(seeded_engine):
    """Each item should appear exactly once."""
    with patch("tools.inventory.engine", seeded_engine):
        from tools.inventory import get_low_stock_summary
        result = get_low_stock_summary.invoke({})

    names = [r["name"] for r in result]
    assert len(names) == len(set(names))
