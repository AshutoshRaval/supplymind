# SupplyMind

An AI-powered inventory management system built with LangGraph, LangChain, and Claude. Uses a multi-agent ReAct architecture to monitor stock levels, compare vendors, and generate procurement recommendations.

## Problem Statement

When inventory drops below threshold, the system:
1. Detects which items are at risk and how urgent
2. Compares available vendors by price, lead time, and rating
3. Computes exact reorder quantities with safety buffers
4. Generates a complete procurement report

## Quick Start

```bash
# Install dependencies
uv sync

# Add your API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env

# Run the full pipeline
uv run python main.py

# Run tests
uv run pytest tests/ -v
```

## Architecture

```
main.py
    │
    ▼
Supervisor
    │
    ├── InventoryMonitor Agent  ──► tools/inventory.py ──► SQLite DB
    │                                                  ──► ChromaDB (RAG)
    │
    └── VendorAdvisor Agent  ────► tools/inventory.py ──► SQLite DB
                                   skills/reorder.py
                                   skills/rag.py

MCP Server (mcp_server/server.py)
    ├── check_stock()          → raw DB query
    ├── get_quotes(item_id)    → raw DB query
    ├── list_suppliers()       → raw DB query
    └── run_inventory_check()  → full agent pipeline
```

## Project Structure

```
supplymind/
├── db/
│   ├── models.py          SQLAlchemy models (Item, Supplier, SupplierItem, ConsumptionLog)
│   └── seed.py            Seed data (10 items, 3 suppliers, 30 days consumption logs)
│
├── tools/
│   └── inventory.py       5 agent tools (@tool decorated functions)
│
├── skills/
│   ├── rag.py             ChromaDB semantic search (embed + query)
│   └── reorder.py         Reorder quantity calculation skill
│
├── graph/
│   ├── inventory_agent.py  InventoryMonitor ReAct agent
│   ├── vendor_agent.py     VendorAdvisor ReAct agent
│   └── supervisor.py       Multi-agent orchestrator
│
├── mcp_server/
│   ├── server.py          MCP server (raw tools + agent pipeline)
│   └── config.json        Claude Desktop connection config
│
├── tests/
│   ├── conftest.py        Pytest fixtures (in-memory DB)
│   ├── test_tools.py      15 tool unit tests
│   └── test_agent.py      5 agent mocked tests
│
└── main.py                CLI entry point
```

## Tech Stack

| Package | Purpose |
|---------|---------|
| `langgraph` | Agent orchestration, ReAct loop |
| `langchain-anthropic` | Claude LLM integration |
| `langchain-core` | `@tool` decorator, base classes |
| `chromadb` | Vector store for semantic search |
| `sqlalchemy` | ORM for SQLite inventory DB |
| `mcp` | Model Context Protocol server |
| `python-dotenv` | Environment variable loading |
| `pytest` | Testing framework |

## Concepts Covered

| Concept | Where |
|---------|-------|
| ReAct Agents | `graph/inventory_agent.py`, `graph/vendor_agent.py` |
| Agent Tools | `tools/inventory.py` |
| Skills | `skills/reorder.py`, `skills/rag.py` |
| RAG | `skills/rag.py` + ChromaDB |
| Multi-agent orchestration | `graph/supervisor.py` |
| MCP Server | `mcp_server/server.py` |
| A2A Protocol | `a2a/` (Day 3) |
