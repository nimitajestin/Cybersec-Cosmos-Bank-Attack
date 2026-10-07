"""
Page 4 — Simulated unauthorised SWIFT transfer (separate rail from ATM).

Security concept: ATM cash-out is high-volume / moderate-value; SWIFT fraud
is low-volume / high-value. Both can follow the same compromised environment
but they must not be mixed in the authorisation pipeline.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import database as db
from core.attack_engine import process_swift_transfer
from core.constants import SWIFT_AMOUNT, SWIFT_BENEFICIARY
from core.ui import format_inr, mismatch_panels, page_setup, safe_dataframe, safe_error, scale_note

state = page_setup("SWIFT Fraud", "🏦")
scale_note()

st.markdown(
    "This tab is **isolated from the ATM flow**. It models one large unauthorised "
    "payment message toward **Hong Kong Bank (fictional)** after the environment "
    "is marked compromised. Dual-control / whitelist checks run only when "
    "**ENABLE SECURITY CONTROLS** is on."
)

s1, s2, s3 = st.columns(3)
s1.metric("Environment compromised", "YES" if state.get("switch_compromised") else "NO")
s2.metric("SWIFT interface", "LOCKED" if state.get("swift_locked") else "OPEN")
s3.metric("Security controls", "ON" if state.get("security_controls") else "OFF")

st.markdown("#### Payment message (fictional)")
c1, c2 = st.columns(2)
with c1:
    st.text_input("Debit account (masked)", value="XXXX-XXXX-SW01", disabled=True)
    amount = st.number_input(
        "Amount (₹)",
        min_value=1_000_000.0,
        max_value=50_000_000.0,
        value=float(SWIFT_AMOUNT),
        step=1_000_000.0,
    )
with c2:
    st.text_input("Beneficiary", value=SWIFT_BENEFICIARY, disabled=True)
    st.caption("Rule R6 fires for any SWIFT transfer ≥ ₹1 crore.")

if st.button("SUBMIT UNAUTHORISED SWIFT MESSAGE", type="primary", use_container_width=True):
    rec = process_swift_transfer(amount=amount, beneficiary=SWIFT_BENEFICIARY)
    st.session_state["last_swift"] = rec
    st.rerun()

rec = st.session_state.get("last_swift")
if rec:
    if not rec.get("ok"):
        st.error(rec.get("error") or "SWIFT simulation failed.")
    else:
        mismatch_panels(
            rec["core_decision"],
            rec["switch_decision"],
            rec["status"],
            rec.get("block_reason") or rec.get("core_reason"),
        )
        if rec["status"] == "UNAUTHORIZED":
            st.error(
                f"{rec['txn_id']} flagged **UNAUTHORIZED** — simulated {format_inr(rec['amount'])} "
                f"toward {rec.get('beneficiary')}."
            )
        elif rec["status"] == "BLOCKED":
            st.warning(rec.get("block_reason"))
        alerts = rec.get("alerts") or []
        if alerts:
            st.markdown("#### Rules that fired")
            safe_dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)

st.markdown("#### ATM cash-out vs SWIFT fraud (volume vs value)")
try:
    stats = db.atm_vs_swift_stats()
    atm = stats["atm"] or {}
    swift = stats["swift"] or {}
    table = pd.DataFrame(
        [
            {
                "Rail": "ATM cash-out",
                "Pattern": "High volume, many countries, moderate ticket",
                "Txns (excl. seed)": int(atm.get("volume") or 0),
                "Gross value (₹)": format_inr(atm.get("value") or 0),
                "Simulated fraud value (₹)": format_inr(atm.get("fraud_value") or 0),
            },
            {
                "Rail": "SWIFT fraud",
                "Pattern": "Low volume, single high-value payment message",
                "Txns (excl. seed)": int(swift.get("volume") or 0),
                "Gross value (₹)": format_inr(swift.get("value") or 0),
                "Simulated fraud value (₹)": format_inr(swift.get("fraud_value") or 0),
            },
        ]
    )
    safe_dataframe(table, use_container_width=True, hide_index=True)
    st.caption(
        "Historically, both patterns were reported in the 2018 Cosmos Bank case. "
        "Here they are separate buttons on purpose — mixing rails would hide that lesson."
    )
    swift_rows = db.list_transactions(txn_type="SWIFT", limit=50)
    if swift_rows:
        st.markdown("#### SWIFT message log")
        safe_dataframe(pd.DataFrame(swift_rows), use_container_width=True, hide_index=True)
except db.DatabaseError as exc:
    safe_error(exc)
