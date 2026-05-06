import { useState, useEffect } from "react";
import "./App.css";

const API = "http://localhost:8000";
const clr = { CRITICAL: "#dc2626", HIGH: "#ea580c", OK: "#16a34a" };
const clrBg = { CRITICAL: "#fef2f2", HIGH: "#fff7ed", OK: "#f0fdf4" };

const NAV = [
  { id: "overview", label: "Overview", icon: "⊞" },
  { id: "analysis", label: "Analysis", icon: "✦" },
  { id: "about",    label: "About",    icon: "ℹ" },
];

function Badge({ status }) {
  return (
    <span style={{ ...s.badge, color: clr[status], background: clrBg[status], border: `1px solid ${clr[status]}33` }}>
      {status}
    </span>
  );
}

// ── Markdown parser ────────────────────────────────

function parseKV(lines) {
  return lines
    .filter(l => l.trim().startsWith("-"))
    .map(l => {
      const m = l.match(/\*\*(.+?)\*\*[:\s]+(.+)/);
      return m ? { key: m[1].replace(/:$/, ""), value: m[2].trim() } : null;
    })
    .filter(Boolean);
}

function parseSections(text) {
  const sections = {};
  let current = "intro";
  const lines = text.split("\n");
  const buf = [];
  for (const line of lines) {
    if (line.startsWith("### ")) {
      sections[current] = [...buf];
      buf.length = 0;
      current = line.replace(/^###\s+\*?\*?/, "").replace(/\*?\*?$/, "").trim();
    } else {
      buf.push(line);
    }
  }
  sections[current] = [...buf];
  return sections;
}

function KVGrid({ lines }) {
  const pairs = parseKV(lines);
  if (!pairs.length) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: "0.5rem" }}>
      {pairs.map(({ key, value }) => (
        <div key={key} style={s.kvCard}>
          <div style={s.kvKey}>{key}</div>
          <div style={s.kvVal}>{value}</div>
        </div>
      ))}
    </div>
  );
}

function RecommendationCard({ item }) {
  const sections = parseSections(item.recommendation);
  const alertLine = Object.values(sections).flat()
    .find(l => l.includes("EXCEEDS") || l.includes("URGENT"));
  const sectionKeys = Object.keys(sections).filter(k =>
    k !== "intro" && !k.includes("CRITICAL") && !k.includes("PROCUREMENT")
  );
  return (
    <div style={{ ...s.recCard, borderLeft: `4px solid ${clr[item.urgency]}` }}>
      <div style={s.recHeader}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <Badge status={item.urgency} />
          <span style={s.recTitle}>{item.item_name}</span>
          <span style={s.recSku}>{item.sku}</span>
        </div>
        <span style={{ fontSize: "0.8rem", color: "#64748b" }}>⏱ {item.days_to_stockout ?? "N/A"} days left</span>
      </div>
      {alertLine && (
        <div style={s.alertBanner}>
          ⚠ {alertLine.replace(/\*\*/g, "").replace(/^[-–]\s*/, "").trim()}
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "0.75rem" }}>
        {sectionKeys.map(key => {
          const lines = sections[key];
          const kvPairs = parseKV(lines);
          const textLines = lines.filter(l => l.trim() && !l.trim().startsWith("-") && !l.startsWith("#") && !l.startsWith("---"));
          return (
            <div key={key}>
              <div style={s.secTitle}>{key.replace(/\*\*/g, "")}</div>
              {kvPairs.length > 0 && <KVGrid lines={lines} />}
              {textLines.length > 0 && (
                <p style={{ fontSize: "0.85rem", color: "#475569", lineHeight: 1.7, marginTop: kvPairs.length ? "0.5rem" : 0 }}>
                  {textLines.join(" ").replace(/\*\*/g, "")}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Sidebar ────────────────────────────────────────

function Sidebar({ page, setPage, flagged }) {
  const critical = flagged.filter(i => i.urgency === "CRITICAL").length;
  const high = flagged.filter(i => i.urgency === "HIGH").length;
  return (
    <aside style={s.sidebar}>
      <div style={s.logo}>
        <div style={s.logoIcon}>S</div>
        <div>
          <div style={s.logoTitle}>SupplyMind</div>
          <div style={s.logoSub}>Inventory POS</div>
        </div>
      </div>
      <div style={s.navLabel}>MENU</div>
      {NAV.map(n => (
        <button key={n.id} onClick={() => setPage(n.id)}
          style={{ ...s.navBtn, ...(page === n.id ? s.navActive : {}) }}>
          <span>{n.icon}</span> {n.label}
          {n.id === "overview" && flagged.length > 0 &&
            <span style={s.navBadge}>{flagged.length}</span>}
        </button>
      ))}
      <div style={{ flex: 1 }} />
      <div style={s.navLabel}>STOCK ALERTS</div>
      <div style={s.statRow}><span style={{ color: clr.CRITICAL }}>● Critical</span><strong style={{ color: "#1e293b" }}>{critical}</strong></div>
      <div style={s.statRow}><span style={{ color: clr.HIGH }}>● High</span><strong style={{ color: "#1e293b" }}>{high}</strong></div>
      <div style={s.sideFooter}>Powered by Claude AI</div>
    </aside>
  );
}

// ── Overview Page (Dashboard + Inventory + Alerts) ─

function Overview({ stock, flagged }) {
  const counts = { CRITICAL: 0, HIGH: 0, OK: 0 };
  stock.forEach(i => counts[i.status]++);
  const urgent = flagged.filter(i => i.urgency === "CRITICAL");
  const high   = flagged.filter(i => i.urgency === "HIGH");

  return (
    <div style={s.page}>
      <div style={s.pageHead}>
        <div>
          <div style={s.pageTitle}>Inventory Overview</div>
          <div style={s.pageSub}>{new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</div>
        </div>
        <span style={s.onlinePill}><span style={{ ...s.dot, background: "#16a34a" }} /> System Online</span>
      </div>

      {/* KPI row */}
      <div style={s.kpiRow}>
        {[
          { label: "Total SKUs",    value: stock.length,    color: "#2563eb", bg: "#eff6ff" },
          { label: "Critical",      value: counts.CRITICAL, color: clr.CRITICAL, bg: clrBg.CRITICAL },
          { label: "High Priority", value: counts.HIGH,     color: clr.HIGH,     bg: clrBg.HIGH },
          { label: "Healthy",       value: counts.OK,       color: clr.OK,       bg: clrBg.OK },
        ].map(k => (
          <div key={k.label} style={{ ...s.kpiCard, background: k.bg, borderColor: k.color + "33" }}>
            <div style={{ ...s.kpiVal, color: k.color }}>{k.value}</div>
            <div style={s.kpiLbl}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* Alerts row */}
      {flagged.length > 0 && (
        <div style={s.panel}>
          <div style={s.panelTitle}>Flagged Items — Needs Attention ({flagged.length})</div>
          <div style={s.flagRow}>
            {[...urgent, ...high].map(item => (
              <div key={item.item_id} style={{ ...s.flagCard, borderTop: `3px solid ${clr[item.urgency]}`, background: clrBg[item.urgency] }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <Badge status={item.urgency} />
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>{item.days_to_stockout ?? "N/A"}d left</span>
                </div>
                <div style={{ fontWeight: 600, fontSize: "0.88rem", color: "#1e293b", marginBottom: 2 }}>{item.name}</div>
                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>{item.sku} · {item.current_stock} units</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stock table */}
      <div style={s.panel}>
        <div style={s.panelTitle}>All Inventory</div>
        <table style={s.table}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {["Item", "SKU", "Unit", "Current Stock", "Threshold", "Status"].map(h => (
                <th key={h} style={s.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stock.map(item => (
              <tr key={item.id} style={s.tr}>
                <td style={{ ...s.td, fontWeight: 500, color: "#1e293b" }}>{item.name}</td>
                <td style={{ ...s.td, fontFamily: "monospace", color: "#64748b" }}>{item.sku}</td>
                <td style={s.td}>{item.unit}</td>
                <td style={{ ...s.td, fontWeight: 600 }}>{item.current_stock}</td>
                <td style={s.td}>{item.threshold}</td>
                <td style={s.td}><Badge status={item.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Analysis Page ──────────────────────────────────

function Analysis() {
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true); setResult(null);
    const res = await fetch(`${API}/api/analyze`, { method: "POST" });
    setResult(await res.json());
    setLoading(false);
  };

  return (
    <div style={s.page}>
      <div style={s.pageHead}>
        <div>
          <div style={s.pageTitle}>Procurement Analysis</div>
          <div style={s.pageSub}>AI-powered vendor recommendations and purchase orders</div>
        </div>
        <button onClick={run} disabled={loading} style={s.runBtn}>
          {loading ? "Running..." : "▶ Run Analysis"}
        </button>
      </div>

      {!result && !loading && (
        <div style={s.emptyState}>
          <div style={{ fontSize: "2.5rem" }}>✦</div>
          <div style={{ fontWeight: 600, fontSize: "1rem", color: "#1e293b" }}>No analysis yet</div>
          <div style={{ fontSize: "0.85rem", color: "#64748b" }}>Click Run Analysis to generate procurement recommendations</div>
        </div>
      )}

      {loading && (
        <div style={s.emptyState}>
          <div className="spinner" />
          <div style={{ fontWeight: 600, color: "#1e293b", marginTop: "0.5rem" }}>Analysis in progress...</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginTop: "0.75rem" }}>
            {["Scanning inventory levels", "Comparing vendors via A2A", "Generating purchase orders"].map((step, i) => (
              <div key={i} className="step" style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.82rem", color: "#64748b" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#2563eb", display: "inline-block" }} />
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {result && (
        <>
          <div style={{ ...s.kpiRow, gridTemplateColumns: "repeat(3, 1fr)" }}>
            {[
              { label: "Items Requiring Action", value: result.total,            color: "#2563eb", bg: "#eff6ff" },
              { label: "Critical Orders",        value: result.critical.length,  color: clr.CRITICAL, bg: clrBg.CRITICAL },
              { label: "High Priority Orders",   value: result.high.length,      color: clr.HIGH,     bg: clrBg.HIGH },
            ].map(k => (
              <div key={k.label} style={{ ...s.kpiCard, background: k.bg, borderColor: k.color + "33" }}>
                <div style={{ ...s.kpiVal, color: k.color }}>{k.value}</div>
                <div style={s.kpiLbl}>{k.label}</div>
              </div>
            ))}
          </div>
          {[...result.critical, ...result.high].map((item, i) => (
            <RecommendationCard key={i} item={item} />
          ))}
          {result.total === 0 && (
            <div style={s.emptyState}>
              <div style={{ fontSize: "2rem", color: clr.OK }}>✓</div>
              <div style={{ fontWeight: 600, color: "#1e293b" }}>All inventory levels are healthy</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── About Page ────────────────────────────────────

function About() {
  const stack = [
    { name: "LangGraph",           role: "Agent orchestration & ReAct loop" },
    { name: "Claude (Anthropic)",  role: "LLM powering all agents" },
    { name: "ChromaDB",            role: "Vector store for semantic search (RAG)" },
    { name: "SQLite + SQLAlchemy", role: "Inventory & supplier database" },
    { name: "FastAPI",             role: "Backend API + A2A server" },
    { name: "React + Vite",        role: "This dashboard" },
    { name: "MCP",                 role: "Model Context Protocol server" },
    { name: "DeepEval",            role: "LLM-as-Judge evaluation framework" },
  ];

  const agents = [
    { name: "InventoryMonitor", color: "#2563eb", desc: "Scans all stock levels, calculates days to stockout, classifies urgency as CRITICAL or HIGH." },
    { name: "VendorAdvisor",    color: "#7c3aed", desc: "Fetches supplier quotes, picks the best vendor by price/rating/lead time, computes reorder quantity and generates a PO draft." },
    { name: "Supervisor",       color: "#0891b2", desc: "Orchestrates both agents. Calls InventoryMonitor first, then routes each flagged item to VendorAdvisor via A2A HTTP." },
  ];

  return (
    <div style={s.page}>
      <div style={s.pageHead}>
        <div>
          <div style={s.pageTitle}>About SupplyMind</div>
          <div style={s.pageSub}>AI-powered inventory management system</div>
        </div>
      </div>

      {/* What it does */}
      <div style={s.panel}>
        <div style={s.panelTitle}>What is SupplyMind?</div>
        <p style={s.aboutText}>
          SupplyMind is an AI-powered inventory management system that monitors stock levels,
          identifies critical shortages, and automatically generates procurement recommendations
          with purchase orders — all powered by Claude AI agents.
        </p>
        <p style={{ ...s.aboutText, marginTop: "0.75rem" }}>
          When stock drops below threshold, the system detects which items are at risk,
          compares available vendors by price, lead time, and rating, computes exact reorder
          quantities with safety buffers, and generates a complete procurement report.
        </p>
      </div>

      {/* Agents */}
      <div style={s.panel}>
        <div style={s.panelTitle}>AI Agents</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
          {agents.map(a => (
            <div key={a.name} style={{ ...s.kvCard, borderTop: `3px solid ${a.color}` }}>
              <div style={{ fontWeight: 700, color: a.color, marginBottom: "0.4rem" }}>{a.name}</div>
              <div style={{ fontSize: "0.83rem", color: "#475569", lineHeight: 1.6 }}>{a.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Architecture */}
      <div style={s.panel}>
        <div style={s.panelTitle}>Architecture</div>
        <div style={s.archBox}>
          <code style={s.arch}>
{`React UI  →  FastAPI (port 8000)  →  Supervisor
                                          │
                                          │  A2A HTTP (port 8001)
                                          ▼
                                    VendorAdvisor Server
                                          │
                                          ├── get_supplier_quotes()
                                          ├── get_best_supplier()
                                          ├── calculate_reorder_quantity()
                                          └── generate_po_draft()

MCP Server (port stdio) — exposes tools to Claude Desktop / Cursor`}
          </code>
        </div>
      </div>

      {/* Tech stack */}
      <div style={s.panel}>
        <div style={s.panelTitle}>Tech Stack</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "0.6rem" }}>
          {stack.map(t => (
            <div key={t.name} style={s.kvCard}>
              <div style={{ fontWeight: 600, color: "#1e293b", fontSize: "0.88rem" }}>{t.name}</div>
              <div style={{ fontSize: "0.78rem", color: "#64748b", marginTop: 2 }}>{t.role}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── App root ───────────────────────────────────────

export default function App() {
  const [page, setPage]     = useState("overview");
  const [stock, setStock]   = useState([]);
  const [flagged, setFlagged] = useState([]);

  useEffect(() => {
    fetch(`${API}/api/stock`).then(r => r.json()).then(setStock);
    fetch(`${API}/api/flagged`).then(r => r.json()).then(setFlagged);
  }, []);

  return (
    <div style={s.root}>
      <Sidebar page={page} setPage={setPage} flagged={flagged} />
      <main style={s.main}>
        {page === "overview" && <Overview stock={stock} flagged={flagged} />}
        {page === "analysis" && <Analysis />}
        {page === "about"    && <About />}
      </main>
    </div>
  );
}

// ── Styles ─────────────────────────────────────────

const s = {
  root:       { display: "flex", height: "100vh", width: "100vw", background: "#f1f5f9", color: "#334155", fontFamily: "'Inter',sans-serif", overflow: "hidden" },
  sidebar:    { width: 220, minWidth: 220, background: "#fff", borderRight: "1px solid #e2e8f0", display: "flex", flexDirection: "column", padding: "1.25rem 0.75rem", gap: "0.25rem" },
  logo:       { display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.5rem", paddingLeft: "0.25rem" },
  logoIcon:   { width: 34, height: 34, background: "#2563eb", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "1rem", color: "#fff", flexShrink: 0 },
  logoTitle:  { fontWeight: 700, fontSize: "0.95rem", color: "#1e293b" },
  logoSub:    { fontSize: "0.65rem", color: "#94a3b8" },
  navLabel:   { fontSize: "0.6rem", color: "#94a3b8", letterSpacing: 1.5, padding: "0.6rem 0.5rem 0.2rem" },
  navBtn:     { display: "flex", alignItems: "center", gap: "0.5rem", width: "100%", padding: "0.55rem 0.75rem", background: "none", border: "none", color: "#64748b", borderRadius: 7, cursor: "pointer", fontSize: "0.88rem", textAlign: "left" },
  navActive:  { background: "#eff6ff", color: "#2563eb", fontWeight: 600 },
  navBadge:   { marginLeft: "auto", background: "#dc2626", color: "#fff", borderRadius: 10, padding: "1px 6px", fontSize: "0.65rem", fontWeight: 700 },
  statRow:    { display: "flex", justifyContent: "space-between", padding: "0.3rem 0.75rem", fontSize: "0.8rem", color: "#64748b" },
  sideFooter: { fontSize: "0.62rem", color: "#cbd5e1", textAlign: "center", padding: "0.75rem 0 0.25rem" },
  main:       { flex: 1, overflowY: "auto" },
  page:       { padding: "1.75rem 2rem", display: "flex", flexDirection: "column", gap: "1.25rem" },
  pageHead:   { display: "flex", justifyContent: "space-between", alignItems: "center" },
  pageTitle:  { fontSize: "1.4rem", fontWeight: 700, color: "#1e293b" },
  pageSub:    { fontSize: "0.8rem", color: "#94a3b8", marginTop: 2 },
  onlinePill: { display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", color: "#64748b", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 20, padding: "4px 12px" },
  dot:        { width: 8, height: 8, borderRadius: "50%", display: "inline-block" },
  kpiRow:     { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem" },
  kpiCard:    { border: "1px solid #e2e8f0", borderRadius: 10, padding: "1.1rem 1.25rem" },
  kpiVal:     { fontSize: "2rem", fontWeight: 700 },
  kpiLbl:     { fontSize: "0.75rem", color: "#64748b", marginTop: 2 },
  panel:      { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "1.25rem" },
  panelTitle: { fontSize: "0.78rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, marginBottom: "1rem" },
  table:      { width: "100%", borderCollapse: "collapse", whiteSpace: "nowrap" },
  th:         { textAlign: "left", padding: "9px 16px", fontSize: "0.72rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, borderBottom: "1px solid #f1f5f9" },
  tr:         { borderBottom: "1px solid #f8fafc" },
  td:         { padding: "11px 16px", fontSize: "0.88rem", color: "#475569" },
  badge:      { padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 700, whiteSpace: "nowrap" },
  flagRow:    { display: "flex", gap: "0.75rem", overflowX: "auto", paddingBottom: "0.25rem" },
  flagCard:   { border: "1px solid #e2e8f0", borderRadius: 8, padding: "0.85rem", minWidth: 175, flexShrink: 0 },
  runBtn:     { padding: "10px 22px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontWeight: 600, cursor: "pointer", fontSize: "0.9rem" },
  emptyState: { display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "0.5rem", color: "#94a3b8", padding: "4rem 0", background: "#fff", borderRadius: 10, border: "1px solid #e2e8f0" },
  recCard:    { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 10, padding: "1.25rem" },
  recHeader:  { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" },
  recTitle:   { fontWeight: 700, fontSize: "1rem", color: "#1e293b" },
  recSku:     { fontFamily: "monospace", color: "#94a3b8", fontSize: "0.8rem" },
  alertBanner:{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 6, padding: "0.6rem 0.9rem", fontSize: "0.82rem", color: "#991b1b", lineHeight: 1.5 },
  secTitle:   { fontSize: "0.68rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, marginBottom: "0.5rem" },
  kvCard:     { background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, padding: "0.65rem 0.85rem" },
  kvKey:      { fontSize: "0.68rem", color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 3 },
  kvVal:      { fontSize: "0.9rem", fontWeight: 600, color: "#1e293b" },
  aboutText:  { fontSize: "0.9rem", color: "#475569", lineHeight: 1.75 },
  archBox:    { background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "1.25rem", overflowX: "auto" },
  arch:       { fontSize: "0.8rem", color: "#334155", lineHeight: 1.8, whiteSpace: "pre", fontFamily: "monospace" },
};
