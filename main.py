import argparse
from db.seed import seed
from skills.rag import embed_inventory
from graph.supervisor import run_supervisor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluate", action="store_true",
                        help="Run DeepEval evaluation after generating report")
    args = parser.parse_args()

    print("=== SupplyMind ===\n")

    print("[1/3] Seeding database...")
    seed()

    print("[2/3] Embedding inventory into ChromaDB...")
    embed_inventory()

    print("[3/3] Running Supervisor...\n")
    report = run_supervisor()
    print(report)

    if args.evaluate:
        from evaluation.eval import run_evaluation
        run_evaluation(report)


if __name__ == "__main__":
    main()
