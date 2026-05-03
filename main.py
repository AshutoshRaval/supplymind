from db.seed import seed
from skills.rag import embed_inventory
from graph.supervisor import run_supervisor


def main():
    print("=== SupplyMind ===\n")

    print("[1/3] Seeding database...")
    seed()

    print("[2/3] Embedding inventory into ChromaDB...")
    embed_inventory()

    print("[3/3] Running Supervisor...\n")
    report = run_supervisor()

    print(report)


if __name__ == "__main__":
    main()
