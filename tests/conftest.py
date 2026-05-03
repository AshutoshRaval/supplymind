"""
Pytest fixtures shared across all tests.

Uses an in-memory SQLite DB so tests never touch the real supplymind.db.
Each test gets a clean DB with controlled seed data.
"""

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.models import Base, Item, Supplier, SupplierItem, ConsumptionLog


@pytest.fixture(scope="function")
def test_engine():
    """Create a fresh in-memory SQLite DB for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def seeded_engine(test_engine):
    """In-memory DB pre-seeded with controlled test data."""
    with Session(test_engine) as session:
        # 2 items: one below threshold, one above
        item_low = Item(
            name="Toner Cartridge",
            sku="TNR-002",
            unit="units",
            current_stock=4,    # below threshold of 10
            threshold=10,
            reorder_point=15,
        )
        item_ok = Item(
            name="Office Chair",
            sku="CHR-003",
            unit="units",
            current_stock=30,   # above threshold of 10
            threshold=10,
            reorder_point=20,
        )
        session.add_all([item_low, item_ok])

        # 2 suppliers
        supplier_fast = Supplier(name="FastTrack Ltd", rating=4.2, lead_time_days=2)
        supplier_bulk = Supplier(name="BulkMart", rating=3.8, lead_time_days=7)
        session.add_all([supplier_fast, supplier_bulk])
        session.flush()

        # pricing
        session.add_all([
            SupplierItem(supplier_id=supplier_fast.id, item_id=item_low.id, price_per_unit=50.0),
            SupplierItem(supplier_id=supplier_bulk.id, item_id=item_low.id, price_per_unit=38.0),
        ])

        # 30 days of consumption logs — 1 unit/day for Toner
        today = date.today()
        for days_ago in range(30, 0, -1):
            session.add(ConsumptionLog(
                item_id=item_low.id,
                date=today - timedelta(days=days_ago),
                units_consumed=1,
            ))

        session.commit()

    return test_engine
