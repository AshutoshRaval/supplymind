"""
RAG skill: embed inventory items and supplier descriptions into ChromaDB
so the agent can do semantic similarity search beyond plain SQL lookups.

Uses ChromaDB's default embedding function (all-MiniLM-L6-v2 via onnxruntime)
— no extra API key needed.
"""

import chromadb
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from db.models import Item, Supplier, SupplierItem, engine


# Persistent ChromaDB stored on disk inside the project folder
_client = chromadb.PersistentClient(path="./chroma_db")
_collection = _client.get_or_create_collection(name="inventory")


def _build_item_documents() -> tuple[list[str], list[str], list[dict]]:
    """Build text documents from the items table for embedding."""
    with Session(engine) as session:
        items = session.query(Item).all()

        ids, documents, metadatas = [], [], []
        for item in items:
            doc_id = f"item_{item.id}"
            text = (
                f"Item: {item.name}. "
                f"SKU: {item.sku}. "
                f"Unit: {item.unit}. "
                f"Current stock: {item.current_stock} {item.unit}. "
                f"Restock threshold: {item.threshold} {item.unit}. "
                f"Reorder point: {item.reorder_point} {item.unit}."
            )
            ids.append(doc_id)
            documents.append(text)
            metadatas.append({
                "type": "item",
                "item_id": item.id,
                "name": item.name,
                "sku": item.sku,
            })

        return ids, documents, metadatas


def _build_supplier_documents() -> tuple[list[str], list[str], list[dict]]:
    """Build text documents from the suppliers + what they carry."""
    with Session(engine) as session:
        suppliers = session.query(Supplier).all()

        ids, documents, metadatas = [], [], []
        for supplier in suppliers:
            carried = (
                session.query(Item.name, SupplierItem.price_per_unit)
                .join(SupplierItem, Item.id == SupplierItem.item_id)
                .filter(SupplierItem.supplier_id == supplier.id)
                .all()
            )
            item_list = ", ".join(
                f"{name} at ${price:.2f}/unit" for name, price in carried
            )

            doc_id = f"supplier_{supplier.id}"
            text = (
                f"Supplier: {supplier.name}. "
                f"Rating: {supplier.rating}/5. "
                f"Lead time: {supplier.lead_time_days} days. "
                f"Carries: {item_list}."
            )
            ids.append(doc_id)
            documents.append(text)
            metadatas.append({
                "type": "supplier",
                "supplier_id": supplier.id,
                "name": supplier.name,
                "rating": supplier.rating,
                "lead_time_days": supplier.lead_time_days,
            })

        return ids, documents, metadatas


def embed_inventory():
    """
    Embed all items and suppliers into ChromaDB.
    Safe to call multiple times — upserts existing entries.
    """
    item_ids, item_docs, item_meta = _build_item_documents()
    sup_ids, sup_docs, sup_meta = _build_supplier_documents()

    all_ids = item_ids + sup_ids
    all_docs = item_docs + sup_docs
    all_meta = item_meta + sup_meta

    if not all_ids:
        print("No data to embed — run seed.py first.")
        return

    _collection.upsert(ids=all_ids, documents=all_docs, metadatas=all_meta)
    print(f"Embedded {len(item_ids)} items and {len(sup_ids)} suppliers into ChromaDB.")


@tool
def search_inventory(query: str, n_results: int = 3) -> list[dict]:
    """
    Semantic search over inventory items and supplier descriptions.
    Use this to find items or suppliers by natural language description
    rather than exact SKU or name.

    Examples:
      - "office stationery running low"
      - "fast supplier for electronics"
      - "consumables with high daily usage"

    Args:
        query: Natural language search query.
        n_results: Number of top results to return (default 3).
    """
    results = _collection.query(query_texts=[query], n_results=n_results)

    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        output.append({
            "id": doc_id,
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": round(results["distances"][0][i], 4),
        })
    return output


if __name__ == "__main__":
    embed_inventory()
