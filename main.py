import argparse
import time
import httpx
from db.seed import seed
from skills.rag import embed_inventory
from graph.supervisor import run_supervisor

A2A_SERVER_URL = "http://localhost:8001"


def check_a2a_server() -> bool:
    """Check if the A2A server is reachable."""
    try:
        response = httpx.get(f"{A2A_SERVER_URL}/health", timeout=3.0)
        return response.status_code == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="SupplyMind — AI Inventory Management")
    parser.add_argument("--evaluate", action="store_true",
                        help="Run DeepEval evaluation after generating report")
    args = parser.parse_args()

    print("=" * 50)
    print("  SUPPLYMIND — AI Inventory Management")
    print("=" * 50 + "\n")

    print("Checking A2A server...")
    if check_a2a_server():
        print("  A2A server is running\n")
    else:
        print("  A2A server not found at", A2A_SERVER_URL)
        print("  Start it with:")
        print("    PYTHONPATH=$(pwd) uv run uvicorn a2a.server:app --port 8001")
        return

    # Step 1
    print("[1/3] Seeding database...")
    t = time.time()
    seed()
    print(f"  Done ({time.time() - t:.1f}s)\n")

    # Step 2
    print("[2/3] Embedding inventory into ChromaDB...")
    t = time.time()
    embed_inventory()
    print(f"  Done ({time.time() - t:.1f}s)\n")

    # Step 3
    print("[3/3] Running Supervisor...\n")
    t = time.time()
    report = run_supervisor()
    print(f"  Done ({time.time() - t:.1f}s)\n")

    print(report)

    if args.evaluate:
        from evaluation.eval import run_evaluation
        run_evaluation(report)


if __name__ == "__main__":
    main()
