"""
RSVC Technology Selection & Portfolio Dashboard
================================================
Streamlit application for evaluating Manthan technologies
using the RuTAGe NEST/VRL framework.

Revenue formula:
    Final Revenue = Base Revenue × (VRL% / 100)

Run:
    pip install streamlit pandas openpyxl plotly
    streamlit run rsvc_app.py
"""

import re
import itertools
import io

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RSVC Dashboard",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal, clean CSS — no clutter, clear hierarchy
st.markdown("""
<style>
    /* Typography */
    [data-testid="stAppViewContainer"] { background: #F9F7F3; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* KPI tiles */
    .kpi-tile {
        background: #ffffff;
        border: 1px solid #E5E0D8;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 0;
    }
    .kpi-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: #888070;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        line-height: 1.1;
    }
    .kpi-sub { font-size: 11px; color: #888070; margin-top: 2px; }
    .kv-green  { color: #2A5C3F; }
    .kv-amber  { color: #8B6914; }
    .kv-red    { color: #8B2020; }
    .kv-blue   { color: #1A3D5C; }
    .kv-gray   { color: #555050; }

    /* Section heads */
    .sec-head {
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: #3D3929;
        border-bottom: 2px solid #2A5C3F;
        padding-bottom: 4px;
        margin-bottom: 12px;
    }

    /* Formula box */
    .formula-box {
        background: #1C1A15;
        color: #F2CC68;
        font-family: 'JetBrains Mono', 'Courier New', monospace;
        font-size: 12px;
        padding: 12px 16px;
        border-radius: 6px;
        line-height: 1.8;
        margin: 8px 0 14px;
    }

    /* Callout */
    .callout {
        background: #FBF0CC;
        border-left: 3px solid #B8891A;
        padding: 10px 14px;
        border-radius: 0 6px 6px 0;
        font-size: 12px;
        margin: 10px 0;
        color: #3D2E10;
    }
    .callout-green {
        background: #E8F5EE;
        border-left: 3px solid #2A5C3F;
        color: #1A3D28;
    }
    .callout-red {
        background: #FDE8E8;
        border-left: 3px solid #8B2020;
        color: #3D1010;
    }

    /* Sidebar */
    [data-testid="stSidebar"] { background: #F1EDE5; }
    [data-testid="stSidebar"] .block-container { padding-top: 1rem; }

    /* Tables */
    .dataframe thead tr th {
        background: #F1EDE5 !important;
        font-size: 11px !important;
        text-transform: uppercase;
        color: #555050 !important;
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────

OPEX_BASE = 55_000  # Scenario 1: FPC absorbs staff; only incremental RSVC costs
PV_FACTOR = 3.791   # 10% discount, 5 years

TRACK_SHORT = {
    "Agricultural services with technologies": "Agri-Services",
    "RuTAGe Technologies": "RuTAGe",
    "Renewable energy": "Renewable",
    "WASH": "WASH",
    "Capacity building and research of TIER- 2&3 colleges through RSVCs": "Capacity Build",
    "Assistive technologies": "Assistive",
    "Livelihood/Entrepreneurship": "Livelihood",
    "Edtech/Education": "Edtech",
    "Affordable Housing": "Housing",
    "Fintech": "Fintech",
    "Any other solutions": "Other",
    "Not  Define": "Undefined",
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA PARSING
# ─────────────────────────────────────────────────────────────────────────────

def parse_cost(val) -> float | None:
    """Extract a numeric cost value from messy text fields."""
    if val is None or str(val).strip() in ("", "nan", "None", "Not Defined"):
        return None
    s = re.sub(r"[₹,]", "", str(val).lower())
    nums = re.findall(r"\d+\.?\d*", s)
    if not nums:
        return None
    n = float(nums[0])
    if "lakh" in s or "lac" in s:
        n *= 100_000
    elif "crore" in s or "cr " in s:
        n *= 10_000_000
    # Sanity cap — anything > ₹5 Cr is almost certainly a parsing error
    return n if n < 5e7 else None


def assign_revenue_model(name: str, track: str, desc: str) -> str:
    """Rule-based revenue model assignment from technology metadata."""
    n = (name or "").lower()
    t = (track or "").lower()
    d = (desc or "").lower()[:300]

    r3_kw = [
        "solar", "biogas", "energy platform", "monitoring system",
        "p2p", "advisory", "saas", "subscription", "water supply",
        "satellite", "smart meter", "iot", "digital platform",
    ]
    r4_kw = [
        "rope making", "puffed rice", "sutli", "coir spin",
        "walnut butter", "food dehydrat", "dried food",
    ]
    r1_kw = [
        "processor", "decortication", "shearing", "reaper",
        "solar dryer", "mango seed", "embryo transfer",
    ]

    if any(k in n + " " + d for k in r3_kw):
        return "R3"
    if any(k in n + " " + d for k in r4_kw):
        return "R4"
    if any(k in n + " " + d for k in r1_kw):
        return "R1"
    if "renewable" in t or "wash" in t:
        return "R3"
    return "R2"


def proxy_vrl_scores(name: str, track: str, desc: str,
                     capex: float | None, priority: str, lab: str) -> list[int]:
    """
    Compute proxy VRL scores (1–5) for all 12 NEST parameters
    from available Manthan metadata.

    Returns: [E1, E2, E3, N1, N2, N3, S1, S2, S3, T1, T2, T3]
    """
    n = (name or "").lower()
    t = (track or "").lower()
    d = (desc or "").lower()[:500]
    l = (lab or "").lower()
    p = (priority or "").lower()

    # Economy
    e1 = 4 if p == "high" else (3 if p == "medium" else 2)
    if "rutag" in l:
        e1 = min(5, e1 + 1)
    e2 = 3 if any(k in d for k in ["income", "revenue stream", "market linkage", "productivity", "earn"]) else 2
    if capex is None:
        e3 = 2
    elif capex <= 25_000:
        e3 = 5
    elif capex <= 75_000:
        e3 = 4
    elif capex <= 200_000:
        e3 = 3
    elif capex <= 500_000:
        e3 = 2
    else:
        e3 = 1

    # Nature
    n1 = 4 if any(k in n + " " + t + " " + d for k in ["solar", "renewable", "biomass", "eco", "low carbon", "ghg"]) else 2
    n2 = 3 if any(k in d for k in ["reuse", "recycl", "modular", "circular"]) else 2
    n3 = 3 if any(k in d for k in ["locally", "local material", "decentrali", "community-based"]) else 2

    # Society
    s1 = 3 if any(k in d for k in ["employment", "shg", "women", "artisan", "skill", "income generation"]) else 2
    s2 = 3 if any(k in d for k in ["community", "fpo", "cooperative", "traditional"]) else 2
    s3 = 3 if any(k in d for k in ["drudgery", "health", "nutrition", "sanitation", "ease"]) else 2

    # Technology
    t1 = 3 if any(k in d for k in ["easy to operate", "simple", "minimal training", "user-friendly"]) else 2
    t2 = 4 if any(k in d for k in ["no power", "off-grid", "manual", "hand-operated"]) else (3 if capex and capex <= 50_000 else 2)
    if any(k in d for k in ["requires internet", "continuous grid", "high bandwidth"]):
        t2 = 1
    t3 = 4 if any(k in d for k in ["certified", "mnre", "bis", "iso", "approved"]) else (3 if any(k in d for k in ["patent", "validated by iit"]) else 2)

    return [e1, e2, e3, n1, n2, n3, s1, s2, s3, t1, t2, t3]


# ─────────────────────────────────────────────────────────────────────────────
# REVENUE COMPUTATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_base_revenue(row: pd.Series, params: dict) -> float:
    """
    Compute Base Revenue for each technology using its assigned model.

    Model definitions:
        R1 (Fee-for-Service):  Operating days × Throughput × Utilization% × Fee/unit
        R2 (Machine Rental):   Active months × N machines × max(CapEx×1.5%/12, ₹500) × 12
        R3 (Subscription):     Subscriber HHs × Monthly fee × 12 × Collection%
        R4 (Product Sale):     Estimated from CapEx as proxy (field data required)
    """
    model = row.get("model", "R2")
    capex = row.get("capex") or 0

    if model == "R1":
        throughput_day_kg = 400          # default; should be field-verified
        fee_per_kg = params["r1_fee"]
        return 220 * throughput_day_kg * params["utilization"] * fee_per_kg

    if model == "R2":
        rate_per_month = max(capex * 0.015 / 12, 500)
        return 10 * params["n_machines"] * rate_per_month * 12

    if model == "R3":
        hh_cap = min(40, params["village_hh"] * 0.40)
        return hh_cap * params["r3_fee"] * 12 * params["collection_rate"]

    if model == "R4":
        # Estimate only — replace with actual production × mandi price
        return capex * 1.5 if capex < 200_000 else 75_000

    return 0.0


def compute_vrl_adjusted_revenue(base_rev: float, vrl_pct: float) -> float:
    """
    Final Revenue = Base Revenue × (VRL% / 100)

    This is the core adjustment formula requested. A technology with
    VRL% = 55% earns only 55% of its theoretical base revenue, reflecting
    the deployment uncertainty embedded in the VRL proxy score.
    """
    return base_rev * (vrl_pct / 100)


def compute_actual_opex(row: pd.Series, use_t2: bool) -> float:
    """
    Actual OpEx = Base RSVC OpEx + Tech OpEx × T2 infrastructure multiplier.

    T2 multiplier reflects hidden maintenance costs from infrastructure dependency:
        T2=5 → 0.70× (fully local, below baseline)
        T2=4 → 0.85×
        T2=3 → 1.00× (standard)
        T2=2 → 1.35× (external technician calls)
        T2=1 → 1.80× (continuous external support)
    """
    T2 = int(row.get("T2", 2))
    t2_mult_map = {5: 0.70, 4: 0.85, 3: 1.00, 2: 1.35, 1: 1.80}
    t2_mult = t2_mult_map.get(T2, 1.35) if use_t2 else 1.00

    run_cost = row.get("run_cost") or 0
    tech_opex = min(run_cost, 500_000) if run_cost else ((row.get("capex") or 50_000) * 0.10)
    return OPEX_BASE + tech_opex * t2_mult


def compute_bcr(final_rev: float, capex: float, actual_opex: float) -> float:
    """BCR = PV(Revenue) / [CapEx + PV(OpEx)]   at 10% discount, 5-year horizon."""
    if final_rev <= 0 or capex <= 0:
        return 0.0
    return (final_rev * PV_FACTOR) / (capex + actual_opex * PV_FACTOR)


def compute_portfolio_score(row: pd.Series) -> float:
    """
    Normalized composite score (0–10) for portfolio ranking.

    Weights (all components normalized to 0–10 first):
        C1: Financial return (BCR-based)  → 30%
        C2: Village suitability (VRL%)    → 30%
        C3: Social impact (S1+S2+S3)      → 25%
        C4: Operational readiness (T1)    → 15%
    """
    c1 = min(row.get("bcr", 0) / 2.0, 1.0) * 10
    c2 = row.get("vrl_pct", 0) / 10
    c3 = (int(row.get("S1", 2)) + int(row.get("S2", 2)) + int(row.get("S3", 2))) / 15 * 10
    c4 = int(row.get("T1", 2)) / 5 * 10
    return round(0.30 * c1 + 0.30 * c2 + 0.25 * c3 + 0.15 * c4, 2)


def full_compute(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Run the complete computation pipeline on a dataframe of technologies."""
    out = df.copy()

    # VRL scores → individual columns
    score_cols = ["E1","E2","E3","N1","N2","N3","S1","S2","S3","T1","T2","T3"]
    for i, col in enumerate(score_cols):
        out[col] = out.apply(lambda r: int(r.get("vrl_scores", [2]*12)[i]) if isinstance(r.get("vrl_scores"), list) else 2, axis=1)

    out["vrl_total"] = out[score_cols].sum(axis=1)
    out["vrl_pct"]   = (out["vrl_total"] / 60 * 100).round(0).astype(int)
    out["vrl_tier"]  = out["vrl_pct"].apply(lambda v: "VRL 3" if v >= 80 else ("VRL 2" if v >= 50 else "VRL 1"))

    out["base_rev"]  = out.apply(lambda r: compute_base_revenue(r, params), axis=1).round(0)
    out["final_rev"] = out.apply(lambda r: compute_vrl_adjusted_revenue(r["base_rev"], r["vrl_pct"]), axis=1).round(0)
    out["actual_opex"] = out.apply(lambda r: compute_actual_opex(r, params["use_t2"]), axis=1).round(0)
    out["net_surplus"]  = (out["final_rev"] - out["actual_opex"]).round(0)
    out["bcr"]          = out.apply(lambda r: round(compute_bcr(r["final_rev"], r.get("capex") or 0, r["actual_opex"]), 2), axis=1)
    out["ps"]           = out.apply(compute_portfolio_score, axis=1)

    return out


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading dataset…")
def load_excel(file_bytes: bytes) -> pd.DataFrame:
    """Parse uploaded Excel file into a clean dataframe."""
    wb = pd.ExcelFile(io.BytesIO(file_bytes))
    df = wb.parse(wb.sheet_names[0], header=None)

    # Find the header row (contains 'S.no' or 'Name')
    header_row = 0
    for i, row in df.iterrows():
        if any(str(v).strip().lower() in ("s.no", "name", "track") for v in row.values if v):
            header_row = i
            break
    df.columns = df.iloc[header_row]
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]

    # Flexible column detection
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if "s.no" in cl or col == "sno":
            col_map["sno"] = col
        elif cl == "name":
            col_map["name"] = col
        elif "track" in cl:
            col_map["track"] = col
        elif "priority" in cl:
            col_map["priority"] = col
        elif "cost per unit" in cl or "capex" in cl:
            col_map["capex_raw"] = col
        elif "running cost" in cl or "average running" in cl:
            col_map["run_raw"] = col
        elif "description" in cl:
            col_map["desc"] = col
        elif "incubat" in cl or "lab" in cl or "institute" in cl:
            col_map["lab"] = col

    records = []
    for _, row in df.iterrows():
        sno      = row.get(col_map.get("sno", ""), "")
        name     = str(row.get(col_map.get("name", ""), "") or "").strip()
        track    = str(row.get(col_map.get("track", ""), "") or "").strip()
        priority = str(row.get(col_map.get("priority", ""), "") or "Low").strip()
        capex_r  = row.get(col_map.get("capex_raw", ""), None)
        run_r    = row.get(col_map.get("run_raw", ""), None)
        desc     = str(row.get(col_map.get("desc", ""), "") or "").strip()
        lab      = str(row.get(col_map.get("lab", ""), "") or "").strip()

        if not name or name == "nan":
            continue

        capex    = parse_cost(capex_r)
        run_cost = parse_cost(run_r)
        model    = assign_revenue_model(name, track, desc)
        scores   = proxy_vrl_scores(name, track, desc, capex, priority, lab)

        records.append({
            "sno": sno, "name": name[:60], "track": track,
            "track_short": TRACK_SHORT.get(track, track[:18]),
            "lab": lab[:45], "priority": priority,
            "capex": capex, "capex_raw": str(capex_r or "")[:35],
            "run_cost": run_cost, "run_raw": str(run_r or "")[:40],
            "model": model, "vrl_scores": scores,
            "desc": desc[:250],
        })

    out = pd.DataFrame(records).drop_duplicates(subset=["sno"], keep="first")
    out["priority"] = out["priority"].str.strip().str.capitalize()
    out.loc[~out["priority"].isin(["High", "Medium", "Low"]), "priority"] = "Low"
    return out.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO OPTIMIZER
# ─────────────────────────────────────────────────────────────────────────────

def optimize_portfolio(df: pd.DataFrame, size: int, max_capex: float,
                       max_opex: float, objective: str) -> list[dict]:
    """
    Exhaustive C(n, size) search for the best portfolio combination.

    Returns top-10 feasible combinations sorted by chosen objective.
    """
    eligible = df[df["capex"].notna() & (df["capex"] <= max_capex)].copy()
    if len(eligible) < size:
        return []

    results = []
    for combo in itertools.combinations(eligible.index, size):
        subset = eligible.loc[list(combo)]
        total_cap  = subset["capex"].sum()
        total_opex = subset["actual_opex"].sum()
        if total_cap > max_capex or total_opex > max_opex:
            continue
        total_surplus = subset["net_surplus"].sum()
        avg_vrl = subset["vrl_pct"].mean()
        avg_ps  = subset["ps"].mean()
        score   = {"surplus": total_surplus, "vrl": avg_vrl, "ps": avg_ps}.get(objective, avg_ps)
        results.append({
            "indices": list(combo),
            "names": list(subset["name"]),
            "total_capex": total_cap,
            "total_opex": total_opex,
            "total_surplus": total_surplus,
            "avg_vrl": round(avg_vrl, 1),
            "avg_ps": round(avg_ps, 2),
            "score": score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:10]


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fmt_inr(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    v = float(val)
    if abs(v) >= 1e7:
        return f"₹{v/1e7:.1f} Cr"
    if abs(v) >= 1e5:
        return f"₹{v/1e5:.1f}L"
    if abs(v) >= 1e3:
        return f"₹{v/1e3:.0f}K"
    return f"₹{v:.0f}"


def fmt_signed(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    v = float(val)
    prefix = "+" if v > 0 else ""
    return prefix + fmt_inr(v)


def kpi_html(label: str, value: str, sub: str = "", color_class: str = "kv-gray") -> str:
    return f"""
    <div class="kpi-tile">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {color_class}">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>"""


def surplus_color(v: float) -> str:
    if v > 5_000:
        return "🟢"
    if v > -30_000:
        return "🟡"
    return "🔴"


def vrl_color(v: float) -> str:
    if v >= 80:
        return "🟢"
    if v >= 50:
        return "🟡"
    return "🔴"


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple[dict, dict]:
    """Render sidebar controls. Returns (params, filters)."""
    with st.sidebar:
        st.markdown("### 🌾 RSVC Dashboard")
        st.caption("RuTAGe Smart Village Centre · Technology Selection System")
        st.divider()

        # ── Upload ──────────────────────────────────────────────────
        st.markdown("**📂 Dataset**")
        uploaded = st.file_uploader(
            "Upload Excel (.xlsx)", type=["xlsx", "xls"],
            help="Must follow the standard Manthan export format.",
            label_visibility="collapsed",
        )

        st.divider()

        # ── Filters ─────────────────────────────────────────────────
        st.markdown("**🔍 Filters**")
        search = st.text_input("Search name / track / lab", placeholder="e.g. solar, biogas, RuTAG…")

        col_p, col_m = st.columns(2)
        with col_p:
            priority_f = st.selectbox("Priority", ["All", "High", "Medium", "Low"], label_visibility="visible")
        with col_m:
            model_f = st.selectbox("Model", ["All", "R1", "R2", "R3", "R4"], label_visibility="visible")

        st.divider()

        # ── Budget ──────────────────────────────────────────────────
        st.markdown("**💰 Budget Constraints**")
        max_capex_L = st.slider("Max CapEx (₹ Lakhs)", 0.5, 20.0, 5.0, 0.5)
        max_opex_L  = st.slider("Max Annual OpEx (₹ Lakhs)", 0.5, 10.0, 3.0, 0.5)
        min_vrl_pct = st.slider("Min VRL% threshold", 30, 75, 45, 5)

        st.divider()

        # ── Revenue assumptions ─────────────────────────────────────
        st.markdown("**📊 Revenue Assumptions**")
        utilization    = st.slider("R1 Utilisation %", 20, 80, 55, 5) / 100
        r1_fee         = st.slider("R1 Fee / kg (₹)", 1.0, 8.0, 2.5, 0.5)
        n_machines     = st.slider("R2 Machines rented", 1, 5, 1)
        village_hh     = st.slider("Village households", 100, 800, 250, 50)
        r3_fee         = st.slider("R3 Monthly fee / HH (₹)", 100, 600, 280, 25)
        collection_rate = st.slider("R3 Collection %", 50, 95, 80, 5) / 100

        st.divider()

        # ── VRL Modifiers ───────────────────────────────────────────
        st.markdown("**⚙️ VRL Modifiers**")
        use_t2 = st.checkbox("T2 OpEx multiplier (infra dependency)", value=True)
        st.caption("Final Revenue = Base Revenue × (VRL% ÷ 100)")

    params = {
        "utilization": utilization,
        "r1_fee": r1_fee,
        "n_machines": n_machines,
        "village_hh": village_hh,
        "r3_fee": r3_fee,
        "collection_rate": collection_rate,
        "use_t2": use_t2,
        "max_capex": max_capex_L * 100_000,
        "max_opex": max_opex_L * 100_000,
        "min_vrl": min_vrl_pct,
    }
    filters = {
        "search": search.lower().strip(),
        "priority": priority_f,
        "model": model_f,
    }
    return params, filters, uploaded


# ─────────────────────────────────────────────────────────────────────────────
# TAB: OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

def tab_overview(df: pd.DataFrame):
    st.markdown('<div class="sec-head">Portfolio Overview</div>', unsafe_allow_html=True)

    total = len(df)
    vrl2_plus  = int((df["vrl_pct"] >= 50).sum())
    pos_surplus = int((df["net_surplus"] > 0).sum())
    avg_ps = df["ps"].mean()
    total_rev = df["final_rev"].sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.markdown(kpi_html("Technologies", str(total), "in filtered set", "kv-blue"), unsafe_allow_html=True)
    col2.markdown(kpi_html("VRL 2+ (≥50%)", str(vrl2_plus), f"{vrl2_plus/max(total,1)*100:.0f}% of set", "kv-green"), unsafe_allow_html=True)
    col3.markdown(kpi_html("Adj. Revenue", fmt_inr(total_rev), "VRL-weighted total/yr", "kv-amber"), unsafe_allow_html=True)
    col4.markdown(kpi_html("Positive Surplus", str(pos_surplus), "self-sustaining techs", "kv-green" if pos_surplus > 0 else "kv-red"), unsafe_allow_html=True)
    col5.markdown(kpi_html("Avg Portfolio Score", f"{avg_ps:.1f}", "out of 10.0", "kv-blue"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_l, col_r = st.columns(2)

    with col_l:
        # Priority × Model heatmap
        st.markdown('<div class="sec-head">Revenue Model by Priority</div>', unsafe_allow_html=True)
        heat = df.groupby(["priority", "model"]).size().unstack(fill_value=0)
        for p in ["High", "Medium", "Low"]:
            if p not in heat.index:
                heat.loc[p] = 0
        for m in ["R1", "R2", "R3", "R4"]:
            if m not in heat.columns:
                heat[m] = 0
        heat = heat.loc[["High", "Medium", "Low"], ["R1", "R2", "R3", "R4"]]
        fig_heat = go.Figure(data=go.Heatmap(
            z=heat.values, x=heat.columns.tolist(), y=heat.index.tolist(),
            colorscale=[[0, "#F9F7F3"], [0.3, "#C8DDD0"], [1, "#2A5C3F"]],
            text=heat.values, texttemplate="%{text}", showscale=False,
        ))
        fig_heat.update_layout(
            height=220, margin=dict(l=40, r=10, t=10, b=30),
            font=dict(family="sans-serif", size=12),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    with col_r:
        # VRL distribution
        st.markdown('<div class="sec-head">VRL Score Distribution</div>', unsafe_allow_html=True)
        bins = [0, 40, 50, 65, 80, 101]
        labels = ["<40%", "40–49%", "50–64%", "65–79%", "≥80%"]
        colors = ["#8B2020", "#C45020", "#B8891A", "#567A62", "#2A5C3F"]
        counts = pd.cut(df["vrl_pct"], bins=bins, labels=labels, right=False).value_counts().reindex(labels, fill_value=0)
        fig_vrl = go.Figure(go.Bar(
            x=counts.index.tolist(), y=counts.values.tolist(),
            marker_color=colors, text=counts.values, textposition="outside",
        ))
        fig_vrl.update_layout(
            height=220, margin=dict(l=10, r=10, t=10, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#E5E0D8"),
            xaxis=dict(showgrid=False), showlegend=False, font=dict(size=12),
        )
        st.plotly_chart(fig_vrl, use_container_width=True)

    # Surplus vs BCR scatter
    st.markdown('<div class="sec-head">Surplus vs BCR (bubble = VRL%)</div>', unsafe_allow_html=True)
    plot_df = df[df["capex"].notna()].copy()
    plot_df["label"] = plot_df["name"].str[:30]
    plot_df["surplus_fmt"] = plot_df["net_surplus"].apply(fmt_signed)

    fig_scatter = px.scatter(
        plot_df, x="bcr", y="net_surplus",
        size="vrl_pct", color="model",
        hover_name="label",
        hover_data={"surplus_fmt": True, "vrl_pct": True, "capex": True, "bcr": True, "model": True},
        color_discrete_map={"R1": "#1A3D5C", "R2": "#2A5C3F", "R3": "#6A3A7A", "R4": "#8B6914"},
        size_max=25, height=320,
    )
    fig_scatter.add_hline(y=0, line_dash="dash", line_color="#C45020", line_width=1.5,
                          annotation_text="Break-even", annotation_position="top left")
    fig_scatter.add_vline(x=1.0, line_dash="dash", line_color="#2A5C3F", line_width=1.5,
                          annotation_text="BCR = 1.0", annotation_position="top right")
    fig_scatter.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title="Net Surplus ₹/yr", xaxis_title="BCR (5yr 10%)",
        yaxis=dict(gridcolor="#E5E0D8"), xaxis=dict(gridcolor="#E5E0D8"),
        legend=dict(title="Model", orientation="h", y=1.02),
        font=dict(size=11),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB: TECHNOLOGIES
# ─────────────────────────────────────────────────────────────────────────────

def tab_technologies(df: pd.DataFrame):
    st.markdown('<div class="sec-head">Technology Explorer</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="callout">
    <b>Final Revenue = Base Revenue × (VRL% ÷ 100)</b> — applied to every row.
    A technology with VRL% = 55% earns 55% of its theoretical base revenue,
    reflecting deployment uncertainty. All surplus and BCR figures use this adjusted value.
    </div>""", unsafe_allow_html=True)

    col_sort, col_dl = st.columns([3, 1])
    with col_sort:
        sort_by = st.selectbox(
            "Sort by",
            ["ps", "net_surplus", "final_rev", "bcr", "vrl_pct", "capex"],
            format_func=lambda x: {
                "ps": "Portfolio Score ↓",
                "net_surplus": "Net Surplus ↓",
                "final_rev": "Adjusted Revenue ↓",
                "bcr": "BCR ↓",
                "vrl_pct": "VRL% ↓",
                "capex": "CapEx ↑ (low to high)",
            }.get(x, x),
        )
    with col_dl:
        csv_bytes = df.to_csv(index=False).encode()
        st.download_button("⬇ Export CSV", csv_bytes, "rsvc_technologies.csv", "text/csv")

    ascending = sort_by == "capex"
    display = df.sort_values(sort_by, ascending=ascending).head(100).copy()

    # Build display dataframe
    display["CapEx"]        = display["capex"].apply(fmt_inr)
    display["VRL%"]         = display["vrl_pct"].apply(lambda v: f"{vrl_color(v)} {v}%")
    display["Base Rev/yr"]  = display["base_rev"].apply(fmt_inr)
    display["Final Rev/yr"] = display["final_rev"].apply(fmt_inr)
    display["OpEx/yr"]      = display["actual_opex"].apply(fmt_inr)
    display["Net Surplus"]  = display.apply(lambda r: f"{surplus_color(r['net_surplus'])} {fmt_signed(r['net_surplus'])}", axis=1)
    display["BCR"]          = display["bcr"].apply(lambda v: f"{v:.2f}×")
    display["PS"]           = display["ps"]
    display["Modifiers"]    = display.apply(lambda r: f"T2:{r.get('T2',2)}", axis=1)

    cols_show = ["sno", "name", "track_short", "priority", "model",
                 "CapEx", "VRL%", "Base Rev/yr", "Final Rev/yr",
                 "OpEx/yr", "Net Surplus", "BCR", "PS"]

    st.dataframe(
        display[cols_show].rename(columns={
            "sno": "S.No", "name": "Technology",
            "track_short": "Track", "priority": "Priority", "model": "Model",
        }),
        use_container_width=True, height=480, hide_index=True,
    )

    # Revenue formula explainer
    st.markdown('<div class="sec-head" style="margin-top:20px">Revenue Formula Reference</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="formula-box">
R1 (Fee-for-Service):
  Base Rev = 220d × Throughput × Util% × Fee/kg
  Final Rev = Base Rev × (VRL% / 100)

R2 (Machine Rental):
  Base Rev = 10mo × N_machines
             × max(CapEx×1.5%/12, ₹500) × 12
  Final Rev = Base Rev × (VRL% / 100)
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="formula-box">
R3 (Subscription):
  Base Rev = min(40, HH×40%) × Fee/mo
             × 12 × Collection%
  Final Rev = Base Rev × (VRL% / 100)

R4 (Product Sale):
  Base Rev = CapEx × 1.5  [proxy estimate]
  Final Rev = Base Rev × (VRL% / 100)
        </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div class="callout">
    <b>Why VRL% as the revenue multiplier?</b>
    The proxy VRL score is a supply-side estimate — it captures how well a technology's
    documented characteristics match village deployment requirements. A score of 55% reflects
    significant deployment uncertainty: unclear community ownership track record, infrastructure
    gaps, or limited evidence of village-level use. Multiplying base revenue by VRL%
    means a technology must earn its revenue projection by demonstrating actual
    village readiness — it cannot be assumed.
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB: VRL BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────

def tab_vrl(df: pd.DataFrame):
    st.markdown('<div class="sec-head">VRL NEST Score Breakdown</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="callout">
    These are <b>proxy supply-side scores</b> derived from Manthan metadata — description
    keywords, CapEx level, priority, and lab origin. They should be replaced with
    demand-side field assessments before deployment decisions. Score = 1–5; 2 is the
    default where no evidence is available.
    </div>""", unsafe_allow_html=True)

    score_cols = ["E1","E2","E3","N1","N2","N3","S1","S2","S3","T1","T2","T3"]
    dim_names  = ["Village Readiness","Market Potential","Cost-Benefit",
                  "Sustainability","Circular Econ","Decentralisation",
                  "Livelihoods","Social Cohesion","Wellbeing",
                  "Ease of Ops","Infra Support","Regulatory"]

    # NEST radar — average across all filtered techs
    avgs = [df[c].mean() for c in score_cols]
    fig_radar = go.Figure(go.Scatterpolar(
        r=avgs + [avgs[0]],
        theta=dim_names + [dim_names[0]],
        fill="toself",
        fillcolor="rgba(42,92,63,0.15)",
        line=dict(color="#2A5C3F", width=2),
        name="Avg NEST Score",
    ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, 5], tickvals=[1,2,3,4,5], gridcolor="#E5E0D8"),
            angularaxis=dict(gridcolor="#E5E0D8"),
            bgcolor="rgba(0,0,0,0)",
        ),
        height=380,
        margin=dict(l=70, r=70, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False, font=dict(size=11),
    )
    col_rad, col_bar = st.columns(2)
    with col_rad:
        st.markdown("**Average NEST Radar — all filtered technologies**")
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_bar:
        st.markdown("**Dimension Average Scores**")
        dim_sums = {
            "Economy": df[["E1","E2","E3"]].mean(axis=1).mean(),
            "Nature":  df[["N1","N2","N3"]].mean(axis=1).mean(),
            "Society": df[["S1","S2","S3"]].mean(axis=1).mean(),
            "Technology": df[["T1","T2","T3"]].mean(axis=1).mean(),
        }
        fig_bar = go.Figure(go.Bar(
            x=list(dim_sums.keys()), y=[round(v, 2) for v in dim_sums.values()],
            marker_color=["#B8891A", "#2A5C3F", "#1A3D5C", "#6A3A7A"],
            text=[f"{v:.2f}" for v in dim_sums.values()], textposition="outside",
        ))
        fig_bar.add_hline(y=3.0, line_dash="dot", line_color="#C45020",
                          annotation_text="Moderate suitability threshold",
                          annotation_position="top left", line_width=1.5)
        fig_bar.update_layout(
            height=380, margin=dict(l=10, r=10, t=20, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(range=[0, 5.5], gridcolor="#E5E0D8"), xaxis=dict(showgrid=False),
            font=dict(size=12),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Heatmap table of scores
    st.markdown('<div class="sec-head" style="margin-top:8px">Full NEST Score Table</div>', unsafe_allow_html=True)
    top = df.sort_values("ps", ascending=False).head(30)
    heat_df = top.set_index("name")[score_cols]

    fig_hm = go.Figure(go.Heatmap(
        z=heat_df.values, x=score_cols, y=[n[:35] for n in heat_df.index.tolist()],
        colorscale=[[0,"#8B2020"],[0.2,"#C45020"],[0.4,"#B8891A"],
                    [0.6,"#C8DDD0"],[1,"#2A5C3F"]],
        zmin=1, zmax=5,
        text=heat_df.values, texttemplate="%{text}", showscale=True,
        colorbar=dict(title="Score", len=0.8),
    ))
    fig_hm.update_layout(
        height=min(600, 30 + len(top) * 20),
        margin=dict(l=200, r=60, t=10, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=10),
    )
    st.plotly_chart(fig_hm, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB: PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────

def tab_portfolio(df: pd.DataFrame, params: dict):
    st.markdown('<div class="sec-head">Portfolio Selection</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="callout">
    The optimizer evaluates every possible combination of N technologies from the eligible
    pool (CapEx ≤ budget, VRL ≥ threshold). It then selects the combination that maximizes
    your chosen objective. All revenue figures use the
    <b>Final Revenue = Base Revenue × (VRL% ÷ 100)</b> formula.
    </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        pf_size = st.selectbox("Portfolio size", [2, 3, 4, 5], index=1)
    with c2:
        pf_obj  = st.selectbox("Maximize", ["ps", "surplus", "vrl"],
                               format_func=lambda x: {"ps":"Portfolio Score","surplus":"Net Surplus","vrl":"VRL Feasibility"}[x])
    with c3:
        run_btn = st.button("⚡ Run Optimizer", type="primary", use_container_width=True)

    # Manual selection
    st.markdown("**Manual Portfolio Builder**")
    available = df[df["capex"].notna()].sort_values("ps", ascending=False)
    manual_names = st.multiselect(
        f"Select up to {pf_size} technologies",
        options=available["name"].tolist(),
        max_selections=pf_size,
        help="Start typing to search. Selected technologies form your manual portfolio.",
    )

    if manual_names:
        manual_df = available[available["name"].isin(manual_names)]
        _render_portfolio_summary(manual_df, params, "Manual Portfolio")

    st.divider()

    # Auto-optimize
    if run_btn:
        with st.spinner(f"Evaluating all C(n, {pf_size}) combinations…"):
            results = optimize_portfolio(df, pf_size, params["max_capex"], params["max_opex"], pf_obj)

        if not results:
            st.markdown("""
            <div class="callout callout-red">
            No feasible combination found. Try: increasing the CapEx or OpEx ceiling,
            lowering the VRL threshold, or reducing the portfolio size.
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"**Top {len(results)} portfolios found — {pf_obj.capitalize()} objective**")
            best = results[0]
            best_df = df.loc[best["indices"]]
            _render_portfolio_summary(best_df, params, "🏆 Optimal Portfolio")

            st.markdown('<div class="sec-head" style="margin-top:16px">All Feasible Combinations (Top 10)</div>', unsafe_allow_html=True)
            for i, r in enumerate(results):
                tag = "🏆 Best" if i == 0 else f"#{i+1}"
                with st.expander(f"{tag} · {' + '.join([n[:25] for n in r['names']])}"):
                    cc1, cc2, cc3, cc4 = st.columns(4)
                    cc1.metric("Total CapEx", fmt_inr(r["total_capex"]))
                    cc2.metric("Net Surplus/yr", fmt_signed(r["total_surplus"]),
                               delta_color="normal" if r["total_surplus"] > 0 else "inverse")
                    cc3.metric("Avg VRL%", f"{r['avg_vrl']:.0f}%")
                    cc4.metric("Avg Portfolio Score", f"{r['avg_ps']:.2f}")


def _render_portfolio_summary(pf_df: pd.DataFrame, params: dict, title: str):
    """Render a portfolio summary block with KPIs, table, and 5-year projection."""
    total_cap   = pf_df["capex"].sum()
    total_opex  = pf_df["actual_opex"].sum()
    total_surp  = pf_df["net_surplus"].sum()
    avg_vrl     = pf_df["vrl_pct"].mean()
    pvf         = PV_FACTOR
    total_rev   = pf_df["final_rev"].sum()
    port_bcr    = (total_rev * pvf) / (total_cap + total_opex * pvf) if total_cap > 0 else 0

    st.markdown(f"**{title}**")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total CapEx", fmt_inr(total_cap),
              delta=f"{fmt_inr(params['max_capex'] - total_cap)} remaining" if total_cap <= params['max_capex'] else "OVER BUDGET",
              delta_color="normal" if total_cap <= params['max_capex'] else "inverse")
    k2.metric("Total OpEx/yr", fmt_inr(total_opex))
    k3.metric("Portfolio Revenue/yr", fmt_inr(total_rev))
    k4.metric("Net Surplus/yr", fmt_signed(total_surp),
              delta_color="normal" if total_surp > 0 else "inverse")
    k5.metric("Portfolio BCR", f"{port_bcr:.2f}×",
              delta="Viable" if port_bcr >= 1.0 else "Below 1.0",
              delta_color="normal" if port_bcr >= 1.0 else "inverse")

    if total_cap > params["max_capex"]:
        st.markdown('<div class="callout callout-red">⚠ Portfolio exceeds CapEx budget.</div>', unsafe_allow_html=True)
    elif total_surp > 0:
        st.markdown('<div class="callout callout-green">✓ Portfolio generates a positive net surplus under Scenario 1 (FPC-embedded) OpEx.</div>', unsafe_allow_html=True)
    else:
        st.markdown("""<div class="callout">
        Portfolio has a net deficit. This is typical for Year 1. An anchor technology with
        high revenue should cross-subsidise lower-return technologies.
        </div>""", unsafe_allow_html=True)

    # Technology table
    disp = pf_df[["name", "model", "capex", "vrl_pct", "base_rev",
                   "final_rev", "actual_opex", "net_surplus", "bcr"]].copy()
    disp.columns = ["Technology", "Model", "CapEx", "VRL%",
                    "Base Rev/yr", "Final Rev/yr", "OpEx/yr", "Surplus/yr", "BCR"]
    for col in ["CapEx", "Base Rev/yr", "Final Rev/yr", "OpEx/yr", "Surplus/yr"]:
        disp[col] = disp[col].apply(fmt_inr)
    disp["BCR"] = disp["BCR"].apply(lambda v: f"{v:.2f}×")
    disp["VRL%"] = disp["VRL%"].apply(lambda v: f"{v}%")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # 5-year projection chart
    growth_rates = pf_df["ps"].apply(lambda ps: 0.08 if ps >= 7 else (0.05 if ps >= 5 else 0.02))
    years = list(range(1, 6))
    yr_rev  = []
    yr_surp = []
    for yr in years:
        rev = sum(r * ((1 + g) ** (yr - 1)) for r, g in zip(pf_df["final_rev"], growth_rates))
        yr_rev.append(rev)
        yr_surp.append(rev - total_opex)

    fig_proj = go.Figure()
    fig_proj.add_trace(go.Bar(
        name="Portfolio Revenue", x=years, y=yr_rev,
        marker_color="#C8DDD0", text=[fmt_inr(v) for v in yr_rev], textposition="outside",
    ))
    fig_proj.add_trace(go.Scatter(
        name="Net Surplus", x=years, y=yr_surp,
        line=dict(color="#2A5C3F", width=2.5), mode="lines+markers",
    ))
    fig_proj.add_hline(y=0, line_dash="dot", line_color="#C45020", line_width=1.5)
    fig_proj.update_layout(
        height=280, barmode="group",
        xaxis_title="Year", yaxis_title="₹/yr",
        margin=dict(l=10, r=10, t=20, b=30),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#E5E0D8"), xaxis=dict(showgrid=False),
        legend=dict(orientation="h", y=1.05), font=dict(size=11),
    )
    st.plotly_chart(fig_proj, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB: FEASIBILITY
# ─────────────────────────────────────────────────────────────────────────────

def tab_feasibility(df: pd.DataFrame, params: dict):
    st.markdown('<div class="sec-head">Feasibility Analysis</div>', unsafe_allow_html=True)

    # Three-scenario OpEx analysis
    st.markdown("**Three OpEx Scenarios — Impact on Portfolio Viability**")

    scenarios = {
        "Scenario 1: Embedded (FPC absorbs staff)": 55_000,
        "Scenario 2: Part-staffed (1 technician ₹8K/mo)": 55_000 + 96_000,
        "Scenario 3: Standalone (full market rate)": 55_000 + 312_000 + 36_000,
    }

    sc_cols = st.columns(3)
    for i, (label, opex) in enumerate(scenarios.items()):
        with sc_cols[i]:
            surp_col = df["final_rev"] - opex - (df["actual_opex"] - 55_000)
            pos = int((surp_col > 0).sum())
            margin_pct = (df["final_rev"] / opex).median() * 100
            viable = pos / max(len(df), 1) * 100
            color = "kv-green" if viable > 50 else ("kv-amber" if viable > 20 else "kv-red")
            st.markdown(kpi_html(
                label.split(":")[0],
                f"{pos} viable",
                f"{viable:.0f}% · Median coverage {margin_pct:.0f}%",
                color,
            ), unsafe_allow_html=True)

    st.divider()

    # Feasibility matrix: CapEx vs Surplus
    st.markdown("**Feasibility Matrix: CapEx × Surplus**")
    feas_df = df[df["capex"].notna()].copy()
    feas_df["cap_slab"] = pd.cut(
        feas_df["capex"],
        bins=[0, 25_000, 75_000, 200_000, 500_000, float("inf")],
        labels=["<₹25K", "₹25–75K", "₹75K–₹2L", "₹2L–₹5L", ">₹5L"],
    )
    feas_df["surp_slab"] = pd.cut(
        feas_df["net_surplus"],
        bins=[-float("inf"), -100_000, -50_000, 0, float("inf")],
        labels=["<−₹1L", "−₹1L to −₹50K", "−₹50K to 0", "Positive"],
    )
    matrix = feas_df.groupby(["cap_slab", "surp_slab"], observed=True).size().unstack(fill_value=0)

    fig_mat = go.Figure(go.Heatmap(
        z=matrix.values,
        x=matrix.columns.astype(str).tolist(),
        y=matrix.index.astype(str).tolist(),
        colorscale=[[0, "#F9F7F3"], [0.5, "#C8DDD0"], [1, "#2A5C3F"]],
        text=matrix.values, texttemplate="%{text}", showscale=False,
    ))
    fig_mat.update_layout(
        height=260,
        xaxis_title="Net Surplus Band",
        yaxis_title="CapEx Band",
        margin=dict(l=80, r=20, t=10, b=50),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
    )
    st.plotly_chart(fig_mat, use_container_width=True)

    # Payback period distribution
    st.markdown("**Payback Period (SPP = CapEx ÷ Net Surplus)**")
    spp_df = df[(df["capex"].notna()) & (df["net_surplus"] > 0)].copy()
    spp_df["spp"] = spp_df["capex"] / spp_df["net_surplus"]
    spp_df = spp_df[spp_df["spp"] <= 20]

    if len(spp_df) > 0:
        fig_spp = px.histogram(
            spp_df, x="spp", nbins=15, color="model",
            color_discrete_map={"R1":"#1A3D5C","R2":"#2A5C3F","R3":"#6A3A7A","R4":"#8B6914"},
            labels={"spp": "Simple Payback Period (years)", "count": "Count"},
            height=260,
        )
        fig_spp.add_vline(x=3, line_dash="dash", line_color="#C45020", line_width=1.5,
                          annotation_text="3yr target", annotation_position="top right")
        fig_spp.add_vline(x=5, line_dash="dot", line_color="#888070", line_width=1.2,
                          annotation_text="5yr max", annotation_position="top right")
        fig_spp.update_layout(
            margin=dict(l=10, r=10, t=10, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(gridcolor="#E5E0D8"), xaxis=dict(showgrid=False),
            bargap=0.1, showlegend=True, font=dict(size=11),
        )
        st.plotly_chart(fig_spp, use_container_width=True)
        st.caption(f"Only {len(spp_df)} of {len(df)} technologies have positive surplus; SPP computable for these only.")
    else:
        st.info("No technologies have positive net surplus under current settings. Try increasing utilization or collection rates.")

    # Missing data tracker
    st.markdown('<div class="sec-head" style="margin-top:8px">Missing Variable Tracker</div>', unsafe_allow_html=True)
    miss = {
        "CapEx not parseable":   int(df["capex"].isna().sum()),
        "Run cost missing/zero": int(((df["run_cost"].isna()) | (df["run_cost"] == 0)).sum()),
        "R3 HH data (assumed)":  int((df["model"] == "R3").sum()),
        "R1 throughput (assumed)": int((df["model"] == "R1").sum()),
        "R4 production vol (assumed)": int((df["model"] == "R4").sum()),
    }
    miss_df = pd.DataFrame.from_dict(miss, orient="index", columns=["Count"])
    miss_df["Action Required"] = [
        "Parse manually from description",
        "Estimate as 10% of CapEx/yr",
        "Field survey: count willing-to-pay HHs",
        "Extract throughput from technology description",
        "Get mandi price + raw material cost",
    ]
    st.dataframe(miss_df, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    params, filters, uploaded = render_sidebar()

    # ── Load data ───────────────────────────────────────────────────────────
    if uploaded is not None:
        raw_df = load_excel(uploaded.read())
        st.sidebar.success(f"✓ {len(raw_df)} technologies loaded")
    else:
        st.sidebar.info("Using built-in demo dataset (no upload)")
        # Minimal built-in seed — 12 representative technologies for demo
        seed_data = [
            {"sno":1, "name":"Multi-purpose Processor", "track":"Agricultural services with technologies", "lab":"RuTAG IIT Bombay", "priority":"High", "capex":160000, "capex_raw":"160000", "run_cost":30000, "run_raw":"30000", "model":"R1", "vrl_scores":[5,2,3,4,2,2,3,2,2,2,2,2], "desc":"Versatile processing unit for pulses, oilseeds and cereals. 5 HP motor."},
            {"sno":43,"name":"Sabai Grass Rope Maker",  "track":"RuTAGe Technologies",                     "lab":"RuTAG IIT Kharagpur","priority":"High","capex":88500,"capex_raw":"88500","run_cost":75000,"run_raw":"75000","model":"R4","vrl_scores":[5,2,3,2,2,3,2,2,3,2,2,2],"desc":"Machine for SHG women making rope from locally available Sabai grass."},
            {"sno":70,"name":"Betel Nut Cutter",        "track":"RuTAGe Technologies",                     "lab":"RuTAG IIT Guwahati","priority":"High","capex":15000,"capex_raw":"15000","run_cost":None,"run_raw":"Not Defined","model":"R2","vrl_scores":[5,2,5,2,2,2,3,3,3,2,3,2],"desc":"Low-cost cutter developed for women SHG groups in Assam."},
            {"sno":452,"name":"Prefab Biogas (Sistema.bio)","track":"Renewable energy",                   "lab":"Sistema.bio India","priority":"High","capex":40000,"capex_raw":"40000","run_cost":100,"run_raw":"100","model":"R3","vrl_scores":[4,2,4,4,3,2,2,2,3,2,3,2],"desc":"Sistema.bio prefabricated biogas converts livestock waste to clean energy."},
            {"sno":128,"name":"Aum Voice Box Prosthesis","track":"Assistive technologies",                "lab":"NRDC Villgro","priority":"High","capex":5000,"capex_raw":"5000","run_cost":None,"run_raw":"Not Defined","model":"R2","vrl_scores":[4,3,5,2,2,2,2,2,2,2,3,2],"desc":"Low-cost voice prosthesis for laryngectomy patients. Frugal innovation."},
            {"sno":523,"name":"Walnut Cracker",          "track":"RuTAGe Technologies",                   "lab":"Prof. Zameer Hussain","priority":"High","capex":700,"capex_raw":"700","run_cost":None,"run_raw":"Not Defined","model":"R2","vrl_scores":[4,2,5,4,2,2,3,3,2,2,4,2],"desc":"Manual walnut cracker developed for J&K walnut growers."},
            {"sno":255,"name":"iFPO Digital Platform",  "track":"Agricultural services with technologies","lab":"Karabi Softwares","priority":"Medium","capex":15000,"capex_raw":"15000","run_cost":5000,"run_raw":"5000","model":"R3","vrl_scores":[3,2,5,4,2,2,3,3,2,2,3,2],"desc":"FPO digital integration platform with business plan generation."},
            {"sno":282,"name":"Clean Heating Stove",    "track":"Renewable energy",                       "lab":"Himalayan Rocket Stove","priority":"Medium","capex":20000,"capex_raw":"20000","run_cost":None,"run_raw":"NA","model":"R3","vrl_scores":[3,2,5,4,2,2,2,2,2,2,3,2],"desc":"High-efficiency rocket stove for Himalayan communities."},
            {"sno":86, "name":"Retrofit Vending Cart",  "track":"RuTAGe Technologies",                   "lab":"IIT Madras","priority":"High","capex":32180,"capex_raw":"32180","run_cost":None,"run_raw":"Not Defined","model":"R2","vrl_scores":[4,3,4,4,2,2,2,2,2,2,3,2],"desc":"Eco-friendly vending cart retrofit for fruit and vegetable vendors."},
            {"sno":230,"name":"BEEKIND Apiculture Suite","track":"Agricultural services with technologies","lab":"Buzzworthy Ventures","priority":"High","capex":4500,"capex_raw":"4500","run_cost":None,"run_raw":"Not Defined","model":"R3","vrl_scores":[4,2,5,4,2,2,2,2,2,2,3,2],"desc":"IoT platform for beekeepers with NFC traceability and hive monitoring."},
            {"sno":497,"name":"Seema-Surakshak Fence",  "track":"Agricultural services with technologies","lab":"IIT researchers","priority":"High","capex":1000,"capex_raw":"1000","run_cost":500,"run_raw":"500","model":"R2","vrl_scores":[4,2,5,4,2,2,2,2,2,2,3,2],"desc":"Triboelectric nanogenerator-based smart fencing system."},
            {"sno":525,"name":"Improved Pottery Kiln",  "track":"RuTAGe Technologies",                   "lab":"Prof. M.R. Ravi IIT Delhi","priority":"High","capex":40000,"capex_raw":"40000","run_cost":None,"run_raw":"Nil","model":"R3","vrl_scores":[4,2,4,2,2,2,2,3,2,2,3,2],"desc":"Energy-efficient updraught kiln reducing fuel use for pottery artisans."},
        ]
        raw_df = pd.DataFrame(seed_data)
        raw_df["track_short"] = raw_df["track"].map(TRACK_SHORT).fillna(raw_df["track"].str[:18])
        raw_df["priority"] = raw_df["priority"].str.capitalize()

    # ── Compute metrics ─────────────────────────────────────────────────────
    computed = full_compute(raw_df, params)

    # ── Apply filters ────────────────────────────────────────────────────────
    mask = pd.Series([True] * len(computed), index=computed.index)
    if filters["search"]:
        q = filters["search"]
        mask &= (
            computed["name"].str.lower().str.contains(q, na=False) |
            computed["track"].str.lower().str.contains(q, na=False) |
            computed["lab"].str.lower().str.contains(q, na=False)
        )
    if filters["priority"] != "All":
        mask &= computed["priority"].str.lower() == filters["priority"].lower()
    if filters["model"] != "All":
        mask &= computed["model"] == filters["model"]
    mask &= computed["vrl_pct"] >= params["min_vrl"]
    mask &= computed["capex"].fillna(float("inf")) <= params["max_capex"]

    filtered = computed[mask].reset_index(drop=True)

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown("## 🌾 RSVC Intelligence Dashboard")
    st.caption(
        f"RuTAGe Smart Village Centre · {len(filtered)} of {len(computed)} technologies · "
        f"Final Revenue = Base Revenue × (VRL% ÷ 100)"
    )

    if len(filtered) == 0:
        st.warning("No technologies match the current filters. Adjust the sidebar controls.")
        return

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview",
        "🔬 Technologies",
        "🎯 VRL Scores",
        "📦 Portfolio",
        "✅ Feasibility",
    ])

    with tab1:
        tab_overview(filtered)
    with tab2:
        tab_technologies(filtered)
    with tab3:
        tab_vrl(filtered)
    with tab4:
        tab_portfolio(filtered, params)
    with tab5:
        tab_feasibility(filtered, params)


if __name__ == "__main__":
    main()
