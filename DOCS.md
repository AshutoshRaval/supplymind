# SupplyMind — Detailed Documentation

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Database Layer](#2-database-layer)
3. [Agent Tools](#3-agent-tools)
4. [RAG Skill](#4-rag-skill)
5. [Reorder Skill](#5-reorder-skill)
6. [InventoryMonitor Agent](#6-inventorymonitor-agent)
7. [VendorAdvisor Agent](#7-vendoradvisor-agent)
8. [Supervisor](#8-supervisor)
9. [MCP Server](#9-mcp-server)
10. [Testing](#10-testing)
11. [Failure Handling](#11-failure-handling)
12. [Evaluation](#12-evaluation)
13. [Key Concepts Explained](#13-key-concepts-explained)
14. [A2A Protocol](#14-a2a-protocol)
15. [PO Draft Tool](#15-po-draft-tool)
16. [FastAPI Backend](#16-fastapi-backend)
17. [React Frontend](#17-react-frontend)
18. [Full System Architecture](#18-full-system-architecture)
19. [Resume Summary](#19-resume-summary)

---

## 1. Project Overview

SupplyMind is a multi-agent AI system for warehouse inventory management.

**Core flow:**
```
Stock drops below threshold
        │
        ▼
InventoryMonitor Agent detects it
        │
        ▼
Supervisor hands it to VendorAdvisor
        │
        ▼
VendorAdvisor compares vendors, computes quantity
        │
        ▼
Procurement report generated
```

**Two databases running in parallel:**
```
SQLite (supplymind.db)     ChromaDB (chroma_db/)
──────────────────────     ─────────────────────
Structured exact data      Vector embeddings
"give me item id=2"        "find printing supplies"
Used by all tools          Used by search_inventory
```

---

## 2. Database Layer

### Models (`db/models.py`)

**Item** — inventory items
```
id, name, sku, unit, current_stock, threshold, reorder_point
```
- `threshold` — hard line. Below this = alert fires
- `reorder_point` — target stock level after restocking

**Supplier** — vendors
```
id, name, rating (out of 5), lead_time_days
```

**SupplierItem** — which supplier sells what at what price
```
supplier_id, item_id, price_per_unit
```

**ConsumptionLog** — daily usage history
```
item_id, date, units_consumed
```

### Seed Data (`db/seed.py`)

Inserts on first run, skips if already seeded:
- 10 items across categories (paper, electronics, office supplies)
- 3 suppliers: QuickSupply Co (4.5★, 3 days), BulkMart (3.8★, 7 days), FastTrack Ltd (4.2★, 2 days)
- 26 supplier-item pricing entries
- 300 consumption log entries (30 days × 10 items)

---

## 3. Agent Tools

**File:** `tools/inventory.py`

Tools are `@tool` decorated Python functions. The LLM reads their name and docstring to decide when to call them. They are the agent's hands — they fetch data, the LLM reasons about it.

### `check_stock_levels()`
- No arguments
- Returns all items where `current_stock <= threshold`
- Fields: item_id, name, sku, unit, current_stock, threshold, reorder_point, deficit

### `get_consumption_velocity(item_id)`
- Queries last 30 days of ConsumptionLog
- Computes avg daily consumption
- Computes `days_to_stockout = current_stock / avg_daily`
- Assigns urgency: CRITICAL (≤3 days), HIGH (≤7), MEDIUM (≤14), LOW

### `get_supplier_quotes(item_id)`
- Joins SupplierItem + Supplier tables
- Returns all suppliers for the item sorted by price
- Includes composite score: `(price × lead_time_weight) / rating`

### `get_low_stock_summary()` ← written by developer
- Combines check_stock + velocity in one call
- Returns sorted list (CRITICAL first) with all urgency fields
- Saves the agent multiple tool calls

### `get_best_supplier(item_id)` ← written by developer
- Returns single best supplier using composite score
- Includes human-readable reason string
- Used by VendorAdvisor for direct recommendations

### Lead Time Weight Formula
```
≤ 2 days  →  1.0  (no penalty)
≤ 4 days  →  1.1
≤ 7 days  →  1.25
> 7 days  →  1.5  (heavy penalty)
```

### Failure Handling — 3 Layers
```
Layer 1: try/except in every tool → returns error dict instead of crashing
Layer 2: retry loop in run functions → 3 attempts, 2s sleep between
Layer 3: recursion_limit=20 in agent.invoke → stops infinite loops
```

---

## 4. RAG Skill

**File:** `skills/rag.py`

### What It Does
Converts inventory data into text, embeds it into ChromaDB for semantic search.

### Setup (run once at startup)
```python
embed_inventory()
```
Builds text documents from Items and Suppliers tables, upserts them into ChromaDB using `all-MiniLM-L6-v2` embedding model (runs locally via onnxruntime, no API key needed).

### Document Format
```
Items:
"Item: Toner Cartridge. SKU: TNR-002. Unit: units.
 Current stock: 4 units. Restock threshold: 10 units."

Suppliers:
"Supplier: QuickSupply Co. Rating: 4.5/5. Lead time: 3 days.
 Carries: Toner at $45.00/unit, Printer Paper at $12.50/unit..."
```

### `search_inventory(query, n_results=3)` — `@tool`
Agent calls this with natural language:
- `"printing supplies running low"` → finds Toner, Printer Paper
- `"fast supplier for electronics"` → finds FastTrack Ltd

Returns matching items/suppliers with similarity distance scores.

### When ChromaDB vs SQLite
```
SQLite    → you know WHAT you want (have item_id)
ChromaDB  → you know WHAT KIND you want (natural language)
```

---

## 5. Reorder Skill

**File:** `skills/reorder.py`

### `calculate_reorder_quantity(item_id, lead_time_days)` — `@tool`

Answers: **how many units should we order?**

```
Formula:
safety_buffer     = avg_daily_consumption × lead_time_days
quantity_to_order = reorder_point - current_stock + safety_buffer
```

**Example (Toner):**
```
avg_daily    = 0.8 units/day
lead_time    = 3 days
safety_buffer = 0.8 × 3 = 2 units
quantity     = 15 - 4 + 2 = 13 units
```

**Why safety buffer?**
Without it, you'd order just enough to reach reorder_point. But while waiting for delivery, you keep consuming. The buffer covers consumption during the lead time window.

**Why in `skills/` not `tools/`?**
- `tools/` = raw data fetching
- `skills/` = business logic / computation

Skills are portable reusable logic. The A2A layer (Day 3) also calls this same skill.

---

## 6. InventoryMonitor Agent

**File:** `graph/inventory_agent.py`

### What It Does
Scans all inventory, identifies urgent items, produces an alert report.

### How It's Built
```python
llm = ChatAnthropic(model="claude-haiku-4-5-20251001")

tools = [
    check_stock_levels,
    get_consumption_velocity,
    get_supplier_quotes,
    get_low_stock_summary,    # developer wrote
    get_best_supplier,        # developer wrote
    search_inventory,
]

agent = create_react_agent(llm, tools, prompt=system_prompt)
```

### ReAct Loop (what happens inside invoke)
```
[THINK]  I should check stock levels first
[ACT]    call get_low_stock_summary()
[OBSERVE] → 6 items below threshold, 1 CRITICAL

[THINK]  Coffee Pods is CRITICAL, let me get supplier info
[ACT]    call get_best_supplier(item_id=9)
[OBSERVE] → QuickSupply Co, $22/unit, 3 days

[THINK]  Lead time (3 days) > stockout (2.7 days) — flag this
[RESPOND] Formatted alert report
```

### System Prompt Role
MD-style instructions embedded in the agent:
- Which tool to call first
- What order to follow
- Business rules (never recommend supplier with lead_time > days_to_stockout)
- Output format

### Entry Point
```python
def run_inventory_monitor(retries=3) -> str:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Check inventory..."}]},
        config={"recursion_limit": 20}
    )
    return result["messages"][-1].content
```

---

## 7. VendorAdvisor Agent

**File:** `graph/vendor_agent.py`

### What It Does
Takes a specific flagged item and produces a complete procurement recommendation.

### Key Difference from InventoryMonitor
```python
# InventoryMonitor — no args, scans everything
def run_inventory_monitor() -> str:

# VendorAdvisor — receives specific item from supervisor
def run_vendor_advisor(item_id: int, urgency: str, days_to_stockout: float) -> str:
```

VendorAdvisor doesn't decide what to look at. The Supervisor tells it which item to handle.

### Tools Available
```python
tools = [
    get_supplier_quotes,        # compare all vendors
    get_best_supplier,          # pick the best one
    calculate_reorder_quantity, # compute how much to order
    search_inventory,           # semantic search if needed
]
```
No `check_stock_levels` — that's InventoryMonitor's job. Each agent has only the tools it needs.

### Output
Complete recommendation including:
- Recommended supplier with reasoning
- Exact quantity to order
- Total cost estimate (quantity × price)
- Lead time vs stockout warning if applicable

---

## 8. Supervisor

**File:** `graph/supervisor.py`

### What It Does
Orchestrates both agents. Routes InventoryMonitor's output to VendorAdvisor.

### Flow
```python
# Step 1: get structured data directly (not via agent)
flagged_items = get_low_stock_summary.invoke({})

# Step 2: filter CRITICAL and HIGH only
urgent_items = [i for i in flagged_items if i["urgency"] in ("CRITICAL", "HIGH")]

# Step 3: agent-to-agent handoff
for item in urgent_items:
    recommendation = run_vendor_advisor(
        item_id=item["item_id"],
        urgency=item["urgency"],
        days_to_stockout=item["days_to_stockout"],
    )

# Step 4: combine into final report
return _build_final_report(recommendations)
```

### Why Call Tool Directly (not via agent)?
Supervisor needs structured data (list of dicts) to loop through.
If it called `run_inventory_monitor()` it would get a text string — unreliable to parse.

### Agent-to-Agent Handoff
```
InventoryMonitor output  →  Supervisor reads it  →  VendorAdvisor input
     (structured dict)          (Python code)         (function args)
```

Neither agent knows the other exists. The Supervisor is the wiring.

---

## 9. MCP Server

**File:** `mcp_server/server.py`

### What MCP Is
Model Context Protocol — a standard that lets any MCP client (Claude Desktop, other agents, apps) connect to your tools without importing your Python code.

```
Without MCP: must import Python, same machine, same language
With MCP:    any client, any machine, any language
```

### Two Types of Tools Exposed

**Raw data tools (fast, no LLM):**
```python
@mcp.tool()
def check_stock() -> list[dict]:     # DB query, instant
def get_quotes(item_id) -> list[dict]: # DB query, instant
def list_suppliers() -> list[dict]:  # DB query, instant
```

**Agent-powered tool (full pipeline):**
```python
@mcp.tool()
def run_inventory_check() -> str:
    return run_supervisor()  # triggers full multi-agent pipeline
```

### How It's Hosted
Runs locally on your machine via stdio transport:
```bash
uv run python mcp_server/server.py
```
Claude Desktop connects to it using `mcp_server/config.json`.

### When to Use Which Tool
```
"what is the stock of Toner?"     → check_stock()         (raw, fast)
"should we reorder this week?"    → run_inventory_check() (agent, smart)
```

---

## 10. Testing

### Structure
```
tests/
├── conftest.py    → shared fixtures
├── test_tools.py  → 15 tool unit tests (Level 1)
└── test_agent.py  → 5 agent mocked tests (Level 2)
```

### Level 1 — Tool Unit Tests
- Use in-memory SQLite DB (never touches real supplymind.db)
- No LLM calls, no API key needed
- Run in ~0.68 seconds
- Tests: correct data returned, error handling, sorting, deduplication

### Level 2 — Agent Mocked Tests
- Mock the LLM with `unittest.mock`
- Tests retry logic, success path, failure path
- No API calls

### conftest.py Fixtures
```python
@pytest.fixture
def seeded_engine():
    # fresh in-memory SQLite DB for each test
    # 2 items: one low, one ok
    # 2 suppliers with known pricing
    # 30 days consumption logs at 1/day
```

### Run Tests
```bash
uv run pytest tests/ -v
```

---

## 11. Failure Handling

3 layers of protection across the entire pipeline.

### Layer 1 — Tool Level (`tools/inventory.py`)
Every tool is wrapped in `try/except`. Instead of crashing, tools return an error dict:
```python
try:
    # normal DB logic
except Exception as e:
    return {"error": f"tool_name failed: {str(e)}"}
```
When a tool returns an error dict, the agent reads it and reasons around it — tries a different approach instead of crashing.

### Layer 2 — Agent Level (`graph/inventory_agent.py`, `graph/vendor_agent.py`)
Retry loop wraps every `agent.invoke()` call:
```python
def run_inventory_monitor(retries=3) -> str:
    for attempt in range(retries):
        try:
            result = agent.invoke(...)
            return result["messages"][-1].content
        except Exception as e:
            if attempt < retries - 1:
                print(f"[Attempt {attempt + 1} failed] {e}. Retrying in 2s...")
                time.sleep(2)
            else:
                return f"Agent failed after {retries} attempts: {str(e)}"
```
Handles: API timeouts, rate limits, network drops.

### Layer 3 — LangGraph Level
```python
config={"recursion_limit": 20}
```
Passed into `agent.invoke()`. LangGraph counts every step in the ReAct loop. If the agent calls more than 20 tools without finishing, LangGraph force-stops it — which Layer 2 then catches and retries.

### Summary
```
Tool crashes      → returns error dict  → agent reasons around it
API timeout       → retry (3 attempts, 2s sleep between)
Agent loops forever → recursion_limit=20 → force stop → retry
```

---

## 12. Evaluation

**File:** `evaluation/eval.py`

Uses **DeepEval** — industry standard open source LLM evaluation framework.
Pattern: **LLM-as-a-Judge** — Claude Haiku evaluates Claude's output.

### How to Run
```bash
# normal run
uv run python main.py

# run with evaluation
uv run python main.py --evaluate
```

### ClaudeJudge
DeepEval defaults to OpenAI. We wrap Claude Haiku as a custom judge:
```python
class ClaudeJudge(DeepEvalBaseLLM):
    def generate(self, prompt: str) -> str:
        response = Anthropic().messages.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

### Retrieval Context (Ground Truth)
Real DB data pulled before evaluation runs:
```python
context = [
    "Coffee Pods (SKU: COF-009): stock=5, threshold=15",
    "QuickSupply Co: rating=4.5, lead_time=3 days, price=22.0",
    ...
]
```
Faithfulness metric checks agent output against this context.

### 3 GEval Metrics

**Metric 1 — Answer Relevancy**
```
Verified against: Input question
Checks: Did the agent answer what was asked?
Fails if: Output is off-topic or vague
```

**Metric 2 — Faithfulness**
```
Verified against: Retrieval context (real DB data)
Checks: Did agent hallucinate prices or supplier names?
Fails if: Output contradicts the DB context
```

**Metric 3 — Business Rules Compliance**
```
Verified against: Domain criteria we defined
Checks:
  - CRITICAL items flagged correctly
  - Lead time > stockout warned
  - Every item has supplier + price + quantity
  - CRITICAL items appear before HIGH
Fails if: Any rule is violated
```

### What GEval Is
GEval does NOT compare against a pre-computed expected answer.
Claude Haiku reads the output and judges it against criteria — like a human reviewer would.

```
Traditional test:  expected == actual  (exact match)
GEval:             Claude reads output and scores criteria (opinion)
```

For exact numerical verification, use pytest unit tests.
For qualitative output quality, use GEval.

### Sample Output
```
Answer Relevancy [GEval]:          100.00% pass rate
Faithfulness [GEval]:              100.00% pass rate
Business Rules Compliance [GEval]: 100.00% pass rate

✓ Evaluation completed! (time taken: 19.7s)
  Pass Rate: 100.0% | Passed: 1 | Failed: 0
```

---

## 13. Key Concepts Explained

### ReAct = Reason + Act
```
Agent alternates between:
  THINK  → what should I do next?
  ACT    → call a tool
  OBSERVE → read the tool result
  THINK  → what does this mean?
  ...repeat until done
```

### @tool vs @mcp.tool()
```
@tool          → LangChain tool, called by agents internally
@mcp.tool()    → MCP tool, called by external clients
```
Same idea, different audience.

### MD Skills vs Python Skills
```
MD Skills      → instructions in system prompt (how to think)
Python Skills  → executable code with @tool (what to do)
```

### SQLite vs ChromaDB
```
SQLite    → exact lookup by ID or filter
ChromaDB  → semantic search by meaning
```

### Agent-to-Agent Handoff (Day 2)
```
Python function call:
  run_vendor_advisor(item_id=2, urgency="HIGH", days_to_stockout=5.0)
One agent's output becomes another's input via the Supervisor.
```

### A2A Protocol (Day 3)
```
HTTP request instead of Python call:
  POST /agents/vendor-advisor
  {"item_id": 2, "urgency": "HIGH"}
Agents can be on different machines, different languages.
```

---

## 14. A2A Protocol

### What It Is
A2A (Agent-to-Agent) is an HTTP-based communication pattern where agents talk to each other as independent services instead of direct Python function calls.

### Before A2A (Day 2)
```
Supervisor → run_vendor_advisor()   # direct Python function call
                                    # both agents in same process
```

### After A2A (Day 3)
```
Supervisor (Process 1)
    │
    │  POST http://localhost:8001/recommend
    │  {"item_id": 2, "urgency": "HIGH", "days_to_stockout": 5.0}
    ▼
VendorAdvisor Server (Process 2)
    │
    │  runs agent, returns result
    ▼
    {"recommendation": "Order 500 units from QuickSupply Co..."}
```

### Files
```
a2a/server.py   → FastAPI app exposing VendorAdvisor at POST /recommend
a2a/client.py   → httpx client used by Supervisor to call the server
```

### server.py
```python
@app.post("/recommend")
def recommend(req: RecommendRequest) -> RecommendResponse:
    result = run_vendor_advisor(
        item_id=req.item_id,
        urgency=req.urgency,
        days_to_stockout=req.days_to_stockout,
    )
    return RecommendResponse(recommendation=result)
```

### client.py
```python
def call_vendor_advisor(item_id, urgency, days_to_stockout) -> str:
    response = httpx.post("http://localhost:8001/recommend", json={...})
    return response.json()["recommendation"]
```

### Why A2A matters
```
Day 2 (Python call)   → tightly coupled, same codebase, same machine
Day 3 (A2A HTTP)      → loosely coupled, independent services
                         VendorAdvisor can run on a different server
                         Multiple supervisors can call it simultaneously
```

### Run the A2A server
```bash
PYTHONPATH=$(pwd) uv run uvicorn a2a.server:app --port 8001 --reload
```

---

## 15. PO Draft Tool

### What It Does
`generate_po_draft()` is a `@tool` that takes vendor recommendation details and formats them into a structured Purchase Order document.

### File
```
tools/po.py
```

### Inputs
```python
item_name: str        # name of the inventory item
sku: str              # stock keeping unit code
supplier_name: str    # chosen supplier
quantity: int         # units to order
price_per_unit: float # cost per unit
lead_time_days: int   # delivery time
urgency: str          # CRITICAL or HIGH
```

### What It Generates
```
========================================
PURCHASE ORDER — PO-20260503-COF-009
========================================
Date        : 2026-05-03
Urgency     : CRITICAL

ITEM
  Name      : Coffee Pods
  SKU       : COF-009
  Quantity  : 31 units

SUPPLIER
  Name      : QuickSupply Co
  Unit Price: $22.00
  Total Cost: $682.00
  Lead Time : 3 days
  Est. Arrival: 2026-05-06

========================================
STATUS: DRAFT — Awaiting Approval
========================================
```

### Who Calls It
VendorAdvisor agent calls it as the final step after:
1. `get_supplier_quotes()` — find all suppliers
2. `get_best_supplier()` — pick the best one
3. `calculate_reorder_quantity()` — how many to order
4. `generate_po_draft()` — format the PO

---

## 16. FastAPI Backend

### What It Does
Acts as the bridge between the React frontend and the agent pipeline.

### File
```
api/server.py
```

### Endpoints
```
GET  /api/stock    → all inventory items with CRITICAL/HIGH/OK status
GET  /api/flagged  → only CRITICAL and HIGH urgency items
POST /api/analyze  → runs full multi-agent pipeline, returns structured JSON
```

### /api/analyze response
```json
{
  "critical": [
    {
      "item_name": "Coffee Pods",
      "sku": "COF-009",
      "urgency": "CRITICAL",
      "days_to_stockout": 2.7,
      "recommendation": "..."
    }
  ],
  "high": [...],
  "total": 6
}
```

### CORS
Configured to allow requests from React dev server at `http://localhost:5173`.

### Run
```bash
PYTHONPATH=$(pwd) uv run uvicorn api.server:app --port 8000 --reload
```

---

## 17. React Frontend

### What It Does
A white and blue enterprise-style dashboard that visualises inventory data and triggers the AI agent pipeline.

### File
```
frontend/src/App.jsx
```

### Pages
```
Overview   → KPI cards + flagged items horizontal scroll + full inventory table
Analysis   → Run Analysis button + structured procurement report cards
About      → Project description, agent breakdown, architecture, tech stack
```

### Key Features
- KPI cards: Total SKUs, Critical, High Priority, Healthy counts
- Flagged items as horizontal scrollable cards (color coded)
- Full inventory table with status badges
- Run Analysis button triggers POST /api/analyze
- Spinner + pulsing step indicators while agents are running
- Procurement report rendered as structured UI cards (not raw text)
  - Markdown parsed into sections: Item Details, Supplier, Order Details, Reasoning
  - Alert banner for CRITICAL lead time risk warnings
  - KV grid cards for each data point

### Run
```bash
cd frontend && npm run dev   # runs at http://localhost:5173
```

### Tech
```
React 18 + Vite   → frontend framework and dev server
fetch API         → calls FastAPI backend at localhost:8000
inline styles     → no CSS framework dependency
```

---

## 18. Full System Architecture

### All components and how they connect

```
Browser (localhost:5173)
    │
    │  HTTP fetch
    ▼
FastAPI Backend (localhost:8000)          api/server.py
    │  GET /api/stock
    │  GET /api/flagged   → SQLite DB (direct query)
    │
    │  POST /api/analyze  → get_recommendations()
    ▼
Supervisor (graph/supervisor.py)
    │
    │  get_low_stock_summary() → SQLite (direct tool call)
    │
    │  POST /recommend (A2A HTTP)
    ▼
VendorAdvisor A2A Server (localhost:8001)   a2a/server.py
    │
    │  run_vendor_advisor()
    ▼
VendorAdvisor Agent (graph/vendor_agent.py)
    ├── get_supplier_quotes()        → SQLite
    ├── get_best_supplier()          → SQLite
    ├── calculate_reorder_quantity() → SQLite
    ├── search_inventory()           → ChromaDB (RAG)
    └── generate_po_draft()          → formats PO document

MCP Server (stdio)                          mcp_server/server.py
    ├── check_stock()                → SQLite
    ├── get_quotes()                 → SQLite
    ├── list_suppliers()             → SQLite
    └── run_inventory_check()        → full agent pipeline
    (called by Claude Desktop / Cursor IDE)
```

### 3 Servers running in production
```
Port 8000  → FastAPI backend    (React UI calls this)
Port 8001  → A2A server         (Supervisor calls this internally)
Port 5173  → React dev server   (browser)
stdio      → MCP server         (Claude Desktop / Cursor)
```

---

## 19. Resume Summary

### What Was Built
SupplyMind is an AI-powered inventory management system with a multi-agent architecture. When stock drops below threshold the system detects stockout risk, compares suppliers, computes reorder quantities with safety buffers, and generates purchase orders — fully automated.

### Agents (3)
```
InventoryMonitor  → detects stockout risk, classifies CRITICAL/HIGH
VendorAdvisor     → picks supplier, computes quantity, drafts PO
Supervisor        → orchestrates both agents
```

### Tools (8 LangChain @tool + 4 MCP tools)
```
check_stock_levels, get_consumption_velocity, get_supplier_quotes,
get_low_stock_summary, get_best_supplier, calculate_reorder_quantity,
search_inventory, generate_po_draft
```

### Key Technical Concepts Used
```
ReAct agent loop          → Reason + Act pattern via LangGraph
RAG pipeline              → dual retrieval: SQL (exact) + ChromaDB (semantic)
Multi-agent orchestration → Supervisor pattern
A2A protocol              → HTTP-based agent-to-agent communication
MCP server                → external tool exposure via Model Context Protocol
LLM-as-Judge evaluation   → DeepEval GEval with Claude Haiku as judge
Failure handling          → 3 layers: tool try/except, agent retry, recursion_limit
```

### Evaluation Results
```
Answer Relevancy:          100% pass rate
Faithfulness:              100% pass rate
Business Rules Compliance: 100% pass rate
```

### Resume Bullets
**Bullet 1 — RAG:**
Developed a RAG-based inventory intelligence pipeline achieving 100% pass rate across Answer Relevancy, Faithfulness, and Business Rules Compliance metrics, by implementing a dual-retrieval system combining structured SQL queries with ChromaDB semantic vector search, validated using an LLM-as-Judge evaluation framework powered by Claude Haiku.

**Bullet 2 — Agents:**
Created a multi-agent workflow with ReAct reasoning, supervisor orchestration, and agent-to-agent (A2A) communication, reducing inventory procurement decision time by automating vendor selection, reorder quantity forecasting, and purchase order generation across a 3-supplier, 10-SKU system.
