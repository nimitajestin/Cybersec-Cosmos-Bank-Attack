"""
Page 6 — Transaction investigation / evidence checklist.

Security concept: after containment, analysts reconstruct a single txn:
who, where, how much, what core said, what the switch said, which rule fired.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import database as db
from core.ui import format_inr, mismatch_panels, page_setup, safe_dataframe, safe_error

state = page_setup("Investigation", "🔎")

st.markdown(
    "Pick any simulated transaction for a forensic-style detail view. "
    "This is log review — not live access to a bank."
)

try:
    db.init_db()
    db.complete_nist("Analysis")
    rows = db.list_transactions(limit=800)
except db.DatabaseError as exc:
    safe_error(exc)
    st.stop()

if not rows:
    st.info("No transactions yet. Run Normal Operation or ATM Cash-Out first.")
    st.stop()

ids = [r["txn_id"] for r in rows]
query = st.text_input("Filter by txn id / card / ATM (optional)", value="")
if query.strip():
    q = query.strip().upper()
    ids = [
        r["txn_id"]
        for r in rows
        if q in str(r.get("txn_id", "")).upper()
        or q in str(r.get("card", "")).upper()
        or q in str(r.get("atm_id", "")).upper()
    ]
    if not ids:
        st.warning("No matches. Clear the filter.")
        st.stop()

choice = st.selectbox("Transaction", ids, index=0)
txn = db.get_transaction(choice)
if not txn:
    st.error("Transaction could not be loaded.")
    st.stop()

mismatch_panels(
    txn.get("core_decision", ""),
    txn.get("switch_decision", ""),
    txn.get("atm_result", ""),
    txn.get("block_reason"),
)

left, right = st.columns(2)
with left:
    st.markdown("#### Record")
    detail = pd.DataFrame(
        [
            ("txn_id", txn.get("txn_id")),
            ("timestamp (UTC)", txn.get("timestamp")),
            ("type", txn.get("txn_type")),
            ("ATM / gateway", txn.get("atm_id")),
            ("location", txn.get("country")),
            ("card", txn.get("card")),
            ("requested amount", format_inr(txn.get("amount"))),
            ("core balance (before)", format_inr(txn.get("balance_before"))),
            ("core balance (after)", format_inr(txn.get("balance_after"))),
            ("core decision", txn.get("core_decision")),
            ("switch decision", txn.get("switch_decision")),
            ("ATM / rail result", txn.get("atm_result")),
            ("status", txn.get("status")),
            ("risk score", txn.get("risk_score")),
            ("risk reason", txn.get("risk_reason")),
            ("beneficiary", txn.get("beneficiary") or "—"),
            ("attack wave", txn.get("attack_wave")),
            ("simulated fraud flag", txn.get("is_simulated_fraud")),
        ],
        columns=["Field", "Value"],
    )
    detail["Value"] = detail["Value"].map(lambda v: "" if v is None else str(v))
    safe_dataframe(detail, use_container_width=True, hide_index=True)

with right:
    st.markdown("#### Evidence checklist")
    alerts = db.alerts_for_txn(choice)
    checks = [
        ("Logs retained in SQLite", True, f"{txn.get('txn_id')} present in transactions table"),
        ("Timestamp recorded", bool(txn.get("timestamp")), str(txn.get("timestamp"))),
        ("Geo / ATM location", bool(txn.get("country") or txn.get("atm_id")), f"{txn.get('atm_id')} / {txn.get('country')}"),
        ("Core decision captured", bool(txn.get("core_decision")), str(txn.get("core_decision"))),
        ("Switch decision captured", bool(txn.get("switch_decision")), str(txn.get("switch_decision"))),
        ("Alert generated", bool(alerts), f"{len(alerts)} alert(s)" if alerts else "No rule fired"),
        ("FIM context (incident-wide)", True, "See Switch Compromise page for SHA-256 before/after"),
    ]
    for title, ok, note in checks:
        st.write(f"{'✅' if ok else '❌'} **{title}** — {note}")

    if alerts:
        st.markdown("##### Alerts tied to this txn")
        safe_dataframe(pd.DataFrame(alerts), use_container_width=True, hide_index=True)
    else:
        st.caption("No alerts for this row (typical for seeded baseline traffic).")

st.markdown("#### Nearby rows (same card)")
same = [r for r in rows if r.get("card") == txn.get("card")][:20]
safe_dataframe(pd.DataFrame(same), use_container_width=True, hide_index=True)
