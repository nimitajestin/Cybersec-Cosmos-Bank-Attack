"""
Page 3 — Simulated multi-country ATM cash-out (high volume, scaled rupees).

Security concept: after switch compromise, attackers drain many ATMs in a
short window. Volume + geo-spread is what SOC rules R2/R3/R5 are built to catch.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core import database as db
from core.attack_engine import run_atm_cashout
from core.ui import format_inr, page_setup, plotly_dark, safe_dataframe, safe_error

state = page_setup("ATM Cash-Out", "💸")

st.markdown(
    "Press **START ATM CASH-OUT** to generate **100–300** withdrawals "
    "across **India, UAE, Thailand, Malaysia**. If the switch is compromised and "
    "controls are off, cash is dispensed even when core declines. "
    "Run it again after **ENABLE SECURITY CONTROLS** (SOC page) to compare before/after."
)

if not state.get("switch_compromised") and not state.get("security_controls"):
    st.info("Tip: turn on **SIMULATE SWITCH COMPROMISE** first, or most over-limit rows will simply decline.")
if state.get("switch_isolated"):
    st.warning("Switch is isolated — the burst will be BLOCKED (good for showing containment).")
if state.get("security_controls"):
    st.success("Defense mode is ON — fraudulent rows should be BLOCKED (before/after comparison).")

n = st.slider("How many ATM transactions?", min_value=100, max_value=300, value=160, step=10)

placeholder = st.empty()
bar = st.progress(0, text="Idle")

if st.button("START ATM CASH-OUT", type="primary", use_container_width=True):
    def _progress(done: int, total: int, msg: str) -> None:
        bar.progress(min(done / max(total, 1), 1.0), text=msg)
        placeholder.metric("Live counter", f"{done} / {total}")

    with st.spinner("Simulating cash-out (local SQLite only)…"):
        summary = run_atm_cashout(n=n, progress_cb=_progress)
    summary.pop("results", None)
    st.session_state["cashout_summary"] = summary
    bar.progress(1.0, text="Done")
    st.rerun()

summary = st.session_state.get("cashout_summary")
if summary:
    st.success(summary.get("message", "Cash-out wave complete."))

try:
    wave = int(state.get("cashout_wave") or 0)
    txns = db.list_transactions(txn_type="ATM", limit=2000)
    fraud = [t for t in txns if t.get("source") == "CASHOUT"]
    latest_wave = [t for t in fraud if int(t.get("attack_wave") or 0) == wave] if wave else fraud
    loss = sum(
        float(t["amount"])
        for t in latest_wave
        if t.get("atm_result") == "CASH_DISPENSED" and t.get("is_simulated_fraud")
    )
    blocked = sum(1 for t in latest_wave if t.get("status") == "BLOCKED")
except db.DatabaseError as exc:
    safe_error(exc)
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Latest wave", str(wave or "—"))
k2.metric("Txns in latest wave", str(len(latest_wave)))
k3.metric("Blocked", str(blocked))
k4.metric("Loss (this wave)", format_inr(loss))

if latest_wave:
    df = pd.DataFrame(latest_wave)
    show_cols = [
        c
        for c in [
            "txn_id",
            "timestamp",
            "atm_id",
            "country",
            "card",
            "amount",
            "balance_before",
            "core_decision",
            "switch_decision",
            "atm_result",
            "status",
            "risk_score",
            "risk_reason",
        ]
        if c in df.columns
    ]
    st.markdown("#### Transaction table (latest wave)")
    safe_dataframe(df[show_cols], use_container_width=True, hide_index=True, height=320)

    vol_rows = db.volume_over_time(wave=wave if wave else None)
    if vol_rows:
        vdf = pd.DataFrame(vol_rows)
        fig = px.line(vdf, x="timestamp", y="txn_count", title="Transaction volume over time")
        st.plotly_chart(plotly_dark(fig), use_container_width=True)

    country_rows = db.loss_by_country(wave=wave if wave else None)
    if country_rows:
        cdf = pd.DataFrame(country_rows)
        fig2 = px.bar(cdf, x="country", y="loss", title="Loss by country (₹)")
        st.plotly_chart(plotly_dark(fig2), use_container_width=True)

    waves = db.wave_loss_summary()
    if len(waves) >= 1:
        wdf = pd.DataFrame(waves)
        wdf["label"] = wdf["wave"].apply(lambda w: f"Wave {int(w)}")
        fig3 = px.bar(wdf, x="label", y="loss", title="Before / after loss comparison (all cash-out waves)")
        st.plotly_chart(plotly_dark(fig3), use_container_width=True)
        st.caption("Wave 1 is typically undefended; a later wave with security controls should show ~₹0 loss.")
else:
    st.write("No cash-out wave yet. Press the button above.")
