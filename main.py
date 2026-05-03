from db.seed import seed
from skills.rag import embed_inventory
from graph.inventory_agent import run_inventory_monitor


def main():
    print("=== SupplyMind ===\n")

    print("[1/3] Seeding database...")
    seed()

    print("[2/3] Embedding inventory into ChromaDB...")
    embed_inventory()

    print("[3/3] Running Inventory Monitor Agent...\n")
    report = run_inventory_monitor()

    print("=== AGENT REPORT ===")
    print(report)


if __name__ == "__main__":
    main()
