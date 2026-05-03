from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()
engine = create_engine("sqlite:///supplymind.db", echo=False)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    sku = Column(String, unique=True, nullable=False)
    unit = Column(String, default="units")
    current_stock = Column(Integer, nullable=False)
    threshold = Column(Integer, nullable=False)   # hard breach — triggers alert
    reorder_point = Column(Integer, nullable=False)  # soft trigger — health score watch


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    rating = Column(Float, default=4.0)          # out of 5
    lead_time_days = Column(Integer, default=5)


class SupplierItem(Base):
    __tablename__ = "supplier_items"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    price_per_unit = Column(Float, nullable=False)


class ConsumptionLog(Base):
    __tablename__ = "consumption_log"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    date = Column(Date, nullable=False)
    units_consumed = Column(Integer, nullable=False)


def init_db():
    Base.metadata.create_all(engine)
