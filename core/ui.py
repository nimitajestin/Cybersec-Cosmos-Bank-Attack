"""
Shared Streamlit chrome: disclaimer, SOC dark CSS, INR formatting, sidebar status.

Security concept: every screen repeats the educational disclaimer so a live
demo cannot be mistaken for a real bank console.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from core import database as db
from core.constants import DISCLAIMER, SCALE_DISCLAIMER
from core.incident_response import nist_checklist

SOC_CSS = """
<style>
    .disclaimer-banner {
        background: linear-gradient(90deg, #3d1a00, #5a2200);
        border: 1px solid #ff8c32;
        color: #ffe6cc;
        padding: 0.7rem 1rem;
        border-radius: 8px;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin-bottom: 0.8rem;
        text-align: center;
    }
    .scale-note {
        background: #1b2838;
        border-left: 4px solid #58a6ff;
        padding: 0.55rem 0.8rem;
        color: #c9d1d9;
        border-radius: 4px;
        margin: 0.4rem 0 0.8rem 0;
        font-size: 0.92rem;
    }
    .mismatch-wrap { display: flex; gap: 12px; }
    .panel {
        border-radius: 10px;
        padding: 1rem 1.1rem;
        min-height: 140px;
        border: 1px solid #30363d;
    }
    .panel h3 { margin: 0 0 0.4rem 0; font-size: 0.95rem; letter-spacing: 0.08em; }
    .panel .big {
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0.35rem 0;
    }
    .panel-red { background: #3d0d0d; border-color: #f85149; color: #ffb4b0; }
    .panel-green { background: #0d3d1a; border-color: #3fb950; color: #aff5b4; }
    .panel-amber { background: #3d3200; border-color: #d29922; color: #ffe08a; }
    .panel-blue { background: #0d213d; border-color: #58a6ff; color: #a8d4ff; }
    .panel-mute { background: #161b22; color: #c9d1d9; }
    .kpi {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 0.8rem 1rem;
    }
    .kpi .lbl { color: #8b949e; font-size: 0.8rem; text-transform: uppercase; }
    .kpi .val { font-size: 1.5rem; font-weight: 800; color: #e6edf3; }
    .sev-crit { color: #ff6b6b; font-weight: 800; }
    .sev-high { color: #ffa657; font-weight: 800; }
    .sev-med { color: #ffe08a; font-weight: 700; }
    code.hash { font-size: 0.78rem; word-break: break-all; }
</style>
"""


def format_inr(amount: Any) -> str:
    """Format a number using Indian grouping (lakhs / crores) with a rupee sign."""
    try:
        n = int(round(float(amount)))
    except (TypeError, ValueError):
        return "₹—"
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) <= 3:
        body = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while rest:
            parts.append(rest[-2:])
            rest = rest[:-2]
        body = ",".join(reversed(parts)) + "," + last3
    return f"{sign}₹{body}"


def inject_css() -> None:
    """Apply the dark SOC dashboard extras on top of Streamlit's dark theme."""
    st.markdown(SOC_CSS, unsafe_allow_html=True)


def disclaimer() -> None:
    """Hardcoded educational banner required on every screen."""
    st.markdown(f'<div class="disclaimer-banner">{DISCLAIMER}</div>', unsafe_allow_html=True)


def scale_note() -> None:
    """Remind the audience that demo rupees are scaled, not the 2018 totals."""
    st.markdown(f'<div class="scale-note">{SCALE_DISCLAIMER}</div>', unsafe_allow_html=True)


def page_setup(title: str, icon: str = "🛡️") -> Dict[str, Any]:
    """Standard header + sidebar used by every multipage script (survives tab switches via SQLite)."""
    st.set_page_config(
        page_title=f"{title} | Cosmos SOC",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    disclaimer()
    st.title(f"{icon} {title}")
    state = render_sidebar()
    return state


def _flag(v: Any) -> str:
    """Render a boolean simulation flag as a short status chip."""
    return "ON" if v else "OFF"


def render_sidebar() -> Dict[str, Any]:
    """Show live simulation state so the professor can follow the story from any page."""
    try:
        db.init_db()
        state = db.get_state()
        nist = nist_checklist()
    except db.DatabaseError as exc:
        st.sidebar.error(str(exc))
        return {}

    st.sidebar.markdown("### Simulation state")
    st.sidebar.write(f"Switch compromised: **{_flag(state.get('switch_compromised'))}**")
    st.sidebar.write(f"Switch isolated: **{_flag(state.get('switch_isolated'))}**")
    st.sidebar.write(f"SWIFT locked: **{_flag(state.get('swift_locked'))}**")
    st.sidebar.write(f"Security controls: **{_flag(state.get('security_controls'))}**")
    st.sidebar.write(f"Incident declared: **{_flag(state.get('incident_declared'))}**")
    st.sidebar.markdown("### NIST SP 800-61")
    done = sum(1 for s in nist if s.get("completed"))
    st.sidebar.progress(done / max(len(nist), 1), text=f"{done}/{len(nist)} stages")
    for stage in nist:
        mark = "✅" if stage.get("completed") else "⬜"
        st.sidebar.caption(f"{mark} {stage['stage']}")
    st.sidebar.markdown("---")
    st.sidebar.caption("Offline educational demo. No real banks, cards, or networks.")
    return state


def kpi(label: str, value: str) -> None:
    """Draw a compact KPI tile used on the SOC and cash-out pages."""
    st.markdown(
        f'<div class="kpi"><div class="lbl">{label}</div><div class="val">{value}</div></div>',
        unsafe_allow_html=True,
    )


def mismatch_panels(core: str, switch: str, atm: str, block_reason: Optional[str] = None) -> None:
    """Bold red-vs-green comparison: the academic centrepiece of switch compromise."""
    def colour(decision: str) -> str:
        u = (decision or "").upper()
        if u in {"APPROVED", "CASH_DISPENSED", "SWIFT_SENT", "UNAUTHORIZED"}:
            return "panel-green" if u != "UNAUTHORIZED" else "panel-red"
        if u in {"DECLINED", "NO_CASH", "NOT_SENT"}:
            return "panel-red"
        if u in {"BLOCKED"}:
            return "panel-amber"
        return "panel-mute"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f'<div class="panel {colour(core)}"><h3>CORE BANKING</h3>'
            f'<div class="big">{core}</div><div>Authoritative ledger decision</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="panel {colour(switch)}"><h3>PAYMENT SWITCH</h3>'
            f'<div class="big">{switch}</div><div>What the ATM actually received</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="panel {colour(atm)}"><h3>ATM / RAIL RESULT</h3>'
            f'<div class="big">{atm}</div><div>{block_reason or "Physical / message outcome"}</div></div>',
            unsafe_allow_html=True,
        )


def plotly_dark(fig: Any) -> Any:
    """Apply a SOC-console Plotly theme that works fully offline."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6edf3"),
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def safe_error(exc: Exception) -> None:
    """Show a user-friendly database/validation failure instead of a traceback."""
    st.error(f"Something went wrong in the simulation: {exc}")


def stringify_df(data: Any) -> pd.DataFrame:
    """Cast every column to str so Streamlit Arrow never warns on mixed types."""
    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(lambda v: "" if v is None else str(v))
    return out


def safe_dataframe(data: Any, **kwargs: Any) -> None:
    """Render a dataframe after string-casting all cells (Arrow-safe)."""
    st.dataframe(stringify_df(data), **kwargs)


def safe_table(data: Any, **kwargs: Any) -> None:
    """Render a static table after string-casting all cells (Arrow-safe)."""
    st.table(stringify_df(data), **kwargs)
