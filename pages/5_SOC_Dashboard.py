"""
Page 5 — SOC dashboard: alerts, KPIs, attack timeline, NIST containment.

Security concept: detection is useless unless an operator can isolate the
compromised hop (payment switch / SWIFT gateway) and fail closed.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core import database as db
from core.attack_engine import run_atm_cashout
from core.detection_engine import RULES
from core.incident_response import (
    enable_security_controls,
    isolate_payment_switch,
    lock_swift_interface,
    nist_checklist,
    reset_simulation,
    restore_switch_integrity,
)
from core.ui import format_inr, kpi, page_setup, plotly_dark, safe_dataframe, safe_error, safe_table, scale_note

state = page_setup("SOC Dashboard", "🛰️")
scale_note()

# ----- Containment / defense controls (mouse-only) -----
st.markdown("### Containment & defense")
b1, b2, b3, b4 = st.columns(4)
with b1:
    if st.button("ISOLATE PAYMENT SWITCH", type="primary", use_container_width=True):
        st.success(isolate_payment_switch()["message"])
        st.rerun()
with b2:
    if st.button("LOCK SWIFT INTERFACE", use_container_width=True):
        st.success(lock_swift_interface()["message"])
        st.rerun()
with b3:
    label = "DISABLE SECURITY CONTROLS" if state.get("security_controls") else "ENABLE SECURITY CONTROLS"
    if st.button(label, use_container_width=True):
        st.success(enable_security_controls(not bool(state.get("security_controls")))["message"])
        st.rerun()
with b4:
    if st.button("RESET SIMULATION", use_container_width=True):
        out = reset_simulation()
        st.session_state.pop("cashout_summary", None)
        st.session_state.pop("last_normal_txn", None)
        st.session_state.pop("mismatch_txn", None)
        st.session_state.pop("last_swift", None)
        (st.success if out["ok"] else st.error)(out["message"])
        st.rerun()

r1, r2 = st.columns(2)
with r1:
    if st.button("RESTORE SWITCH (recovery / known-good hash)", use_container_width=True):
        st.success(restore_switch_integrity()["message"])
        st.rerun()
with r2:
    if st.button("RE-RUN SAME CASH-OUT (defense finale)", use_container_width=True):
        with st.spinner("Replaying the cash-out pattern against current controls…"):
            summary = run_atm_cashout(n=140)
        summary.pop("results", None)
        st.session_state["cashout_summary"] = summary
        st.success(summary["message"])
        st.rerun()

st.caption(
    "Finale: isolate or **ENABLE SECURITY CONTROLS**, then re-run cash-out. "
    "Fraudulent rows should show BLOCKED and the before/after bar on the Cash-Out page should drop."
)

# ----- KPIs -----
try:
    counts = db.alert_counts()
    txns = db.list_transactions(limit=8000)
    loss = sum(
        float(t["amount"])
        for t in txns
        if t.get("txn_type") == "ATM"
        and t.get("is_simulated_fraud")
        and t.get("atm_result") == "CASH_DISPENSED"
    )
    blocked = sum(1 for t in txns if t.get("status") == "BLOCKED")
except db.DatabaseError as exc:
    safe_error(exc)
    st.stop()

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    kpi("🔴 CRITICAL", str(counts.get("CRITICAL", 0)))
with k2:
    kpi("🟠 HIGH", str(counts.get("HIGH", 0)))
with k3:
    kpi("🟡 MEDIUM", str(counts.get("MEDIUM", 0)))
with k4:
    kpi("Blocked txns", str(blocked))
with k5:
    kpi("Simulated ATM loss", format_inr(loss))

# ----- NIST checklist -----
st.markdown("### NIST SP 800-61 lifecycle")
nist = nist_checklist()
cols = st.columns(len(nist))
for col, stage in zip(cols, nist):
    mark = "✅" if stage.get("completed") else "⬜"
    col.markdown(f"**{mark} {stage['stage']}**")
    if stage.get("completed_at"):
        col.caption(str(stage["completed_at"]))

# ----- Timeline -----
st.markdown("### Attack timeline")
st.caption("Demo clock: 10:00 normal → 10:02 compromise → 10:03 first fraud → 10:08 incident → 10:09 isolate.")
try:
    timeline = db.list_timeline()
    if timeline:
        tdf = pd.DataFrame(timeline)[["clock_label", "event", "category", "created_at"]]
        tdf.columns = ["Demo clock", "Event", "Category", "Logged at (UTC)"]
        safe_table(tdf)
    else:
        st.write("Timeline empty — reset or start the demo path.")
except db.DatabaseError as exc:
    safe_error(exc)

# ----- Alert feed -----
st.markdown("### Alert feed (rule that fired is always named)")
sev_filter = st.multiselect(
    "Severity filter",
    ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
    default=["CRITICAL", "HIGH"],
)
try:
    alerts = db.list_alerts(limit=500)
except db.DatabaseError as exc:
    safe_error(exc)
    alerts = []

if alerts:
    adf = pd.DataFrame(alerts)
    if sev_filter:
        adf = adf[adf["severity"].isin(sev_filter)]

    def _dot(sev: str) -> str:
        return {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪") + " " + sev

    if not adf.empty:
        adf = adf.copy()
        adf["severity"] = adf["severity"].map(_dot)
        safe_dataframe(
            adf[["alert_id", "timestamp", "severity", "rule_id", "rule_name", "message", "txn_id"]],
            use_container_width=True,
            hide_index=True,
            height=360,
        )
        fig = px.histogram(pd.DataFrame(alerts), x="rule_id", color="severity", title="Alerts by rule")
        st.plotly_chart(plotly_dark(fig), use_container_width=True)
    else:
        st.info("No alerts in the selected severities yet. Run cash-out after compromise.")
else:
    st.info("Alert feed empty. Generate traffic on Normal / Compromise / Cash-Out pages.")

with st.expander("Detection rule reference (R1–R6)"):
    ref = pd.DataFrame(
        [
            {"Rule": k, "Severity": v["severity"], "Name": v["name"], "What it means": v["desc"]}
            for k, v in RULES.items()
        ]
    )
    safe_dataframe(ref, use_container_width=True, hide_index=True)
