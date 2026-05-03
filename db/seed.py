"""
Seed the database with sample inventory data:
- 10 items across different categories
- 3 suppliers with different ratings and lead times
- Supplier-item pricing (not every supplier carries every item)
- 30 days of daily consumption logs per item
"""

import random
from datetime import date, timedelta
from db.models import Base, Item, Supplier, SupplierItem, ConsumptionLog, engine
from sqlalchemy.orm import Session


ITEMS = [
    # name,               sku,       unit,     stock, threshold, reorder_point
    ("Printer Paper A4",  "PPR-001", "ream",   15,    20,        40),
    ("Toner Cartridge",   "TNR-002", "units",   4,    10,        15),
    ("Office Chair",      "CHR-003", "units",  30,    10,        20),
    ("Laptop 14-inch",    "LPT-004", "units",   3,     5,        10),
    ("USB-C Cable 1m",    "USB-005", "units",  80,    30,        50),
    ("Notebook A5",       "NTB-006", "units",  12,    25,        50),
    ("Whiteboard Marker", "MRK-007", "box",     6,    10,        20),
    ("Hand Sanitizer 1L", "SAN-008", "bottle", 18,    20,        40),
    ("Coffee Pods",       "COF-009", "box",     5,    15,        30),
    ("Water Bottle 500ml","WTR-010", "units",  45,    20,        40),
]

SUPPLIERS = [
    # name,            rating, lead_time_days
    ("QuickSupply Co",  4.5,   3),
    ("BulkMart",        3.8,   7),
    ("FastTrack Ltd",   4.2,   2),
]

# (supplier_index, item_index, price_per_unit)
# Not every supplier carries every item
SUPPLIER_ITEMS = [
    (0, 0, 12.50),   # QuickSupply -> Printer Paper
    (1, 0, 10.00),   # BulkMart   -> Printer Paper (cheaper, slower)
    (2, 0, 13.50),   # FastTrack  -> Printer Paper (most expensive, fastest)

    (0, 1, 45.00),   # QuickSupply -> Toner
    (1, 1, 38.00),   # BulkMart   -> Toner
    (2, 1, 50.00),   # FastTrack  -> Toner

    (0, 2, 150.00),  # QuickSupply -> Chair
    (1, 2, 120.00),  # BulkMart   -> Chair

    (0, 3, 850.00),  # QuickSupply -> Laptop
    (2, 3, 900.00),  # FastTrack  -> Laptop

    (0, 4, 3.50),    # QuickSupply -> USB Cable
    (1, 4, 2.80),    # BulkMart   -> USB Cable
    (2, 4, 4.00),    # FastTrack  -> USB Cable

    (0, 5, 1.20),    # QuickSupply -> Notebook
    (1, 5, 0.90),    # BulkMart   -> Notebook

    (0, 6, 8.00),    # QuickSupply -> Whiteboard Marker
    (1, 6, 6.50),    # BulkMart   -> Whiteboard Marker
    (2, 6, 9.00),    # FastTrack  -> Whiteboard Marker

    (0, 7, 7.50),    # QuickSupply -> Hand Sanitizer
    (1, 7, 5.80),    # BulkMart   -> Hand Sanitizer
    (2, 7, 8.00),    # FastTrack  -> Hand Sanitizer

    (0, 8, 22.00),   # QuickSupply -> Coffee Pods
    (1, 8, 18.00),   # BulkMart   -> Coffee Pods

    (0, 9, 2.00),    # QuickSupply -> Water Bottle
    (1, 9, 1.60),    # BulkMart   -> Water Bottle
    (2, 9, 2.20),    # FastTrack  -> Water Bottle
]

# Average daily consumption rates per item (used to generate realistic logs)
DAILY_CONSUMPTION = [4, 1, 1, 0, 3, 2, 1, 3, 2, 4]


def seed():
    from db.models import init_db
    init_db()

    with Session(engine) as session:
        # Skip if already seeded
        if session.query(Item).count() > 0:
            print("Database already seeded. Skipping.")
            return

        # Insert items
        item_objects = []
        for name, sku, unit, stock, threshold, reorder in ITEMS:
            item = Item(
                name=name,
                sku=sku,
                unit=unit,
                current_stock=stock,
                threshold=threshold,
                reorder_point=reorder,
            )
            session.add(item)
            item_objects.append(item)

        # Insert suppliers
        supplier_objects = []
        for name, rating, lead_time in SUPPLIERS:
            supplier = Supplier(name=name, rating=rating, lead_time_days=lead_time)
            session.add(supplier)
            supplier_objects.append(supplier)

        session.flush()  # get IDs assigned before creating relationships

        # Insert supplier-item pricing
        for sup_idx, item_idx, price in SUPPLIER_ITEMS:
            si = SupplierItem(
                supplier_id=supplier_objects[sup_idx].id,
                item_id=item_objects[item_idx].id,
                price_per_unit=price,
            )
            session.add(si)

        # Insert 30 days of consumption logs
        today = date.today()
        for item_idx, item in enumerate(item_objects):
            avg_rate = DAILY_CONSUMPTION[item_idx]
            for days_ago in range(30, 0, -1):
                log_date = today - timedelta(days=days_ago)
                # Add some randomness around the average rate
                consumed = max(0, avg_rate + random.randint(-1, 1))
                log = ConsumptionLog(
                    item_id=item.id,
                    date=log_date,
                    units_consumed=consumed,
                )
                session.add(log)

        session.commit()
        print(f"Seeded {len(item_objects)} items, {len(supplier_objects)} suppliers, "
              f"{len(SUPPLIER_ITEMS)} supplier-item prices, "
              f"{len(item_objects) * 30} consumption log entries.")


if __name__ == "__main__":
    seed()
