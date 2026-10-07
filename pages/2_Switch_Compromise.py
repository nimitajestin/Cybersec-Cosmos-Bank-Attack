"""
Page 2 — Simulated payment-switch compromise and File Integrity Monitoring.

Security concept: if the switch no longer mirrors core banking, an ATM can
dispense cash against a DECLINED authorisation. FIM (SHA-256) is how ops
notices the binary changed.
"""

from __future__ import annotations

import streamlit as st

from core import database as db
from core.attack_engine import fim_status, toggle_switch_compromise
from core.bank_simulator import process_atm_withdrawal
from core.ui import format_inr, mismatch_panels, page_setup, safe_error

state = page_setup("Switch Compromise", "⚠️")

st.markdown(
    "This page is the **centrepiece**. A healthy switch **must** copy Core Banking. "
    "After the simulated compromise it **approves withdrawals even when core declines** "
    "(insufficient funds). No real executable is modified — only two dummy blobs are hashed."
)

compromised = bool(state.get("switch_compromised"))
st.markdown(f"### Current flag: {'🔴 COMPROMISED' if compromised else '🟢 INTACT'}")

btn_label = (
    "✅ RESTORE SWITCH (clear compromise)"
    if compromised
    else "🛑 SIMULATE SWITCH COMPROMISE"
)
if st.button(btn_label, type="primary", use_container_width=True):
    out = toggle_switch_compromise()
    st.success(out["message"])
    st.rerun()

st.markdown("#### File Integrity Monitoring (SHA-256 of dummy PaymentSwitch.exe)")
try:
    fim = fim_status()
except db.DatabaseError as exc:
    safe_error(exc)
    st.stop()

h1, h2 = st.columns(2)
with h1:
    st.markdown("**Known-good hash (before)**")
    st.code(fim["before"], language=None)
with h2:
    st.markdown("**Live hash (after)**")
    st.code(fim["after"], language=None)

if fim["violated"]:
    st.error("❌ FILE INTEGRITY VIOLATION — PaymentSwitch.exe hash does not match the known-good baseline.")
else:
    st.success("FIM OK — live hash matches the known-good baseline.")

st.markdown("---")
st.markdown("#### Reproduce the mismatch (use an amount **above** available balance)")
st.caption("Core should DECLINE insufficient funds. After compromise, the switch still returns APPROVED.")

try:
    accounts = db.get_accounts(include_swift=False)
    atms = db.get_atms()
except db.DatabaseError as exc:
    safe_error(exc)
    st.stop()

c1, c2, c3 = st.columns(3)
with c1:
    card = st.selectbox("Card", [a["card"] for a in accounts], index=1)
    account = next(a for a in accounts if a["card"] == card)
    st.caption(f"Available: {format_inr(account['available_balance'])}")
with c2:
    india = [a for a in atms if a["country"] == "India"]
    atm_id = st.selectbox("ATM ID", [a["atm_id"] for a in india])
with c3:
    over = max(int(account["available_balance"]) + 5000, 20000)
    amount = st.number_input("Requested amount (₹)", min_value=100, value=int(over), step=500)

if st.button("SEND OVER-LIMIT WITHDRAWAL", use_container_width=True):
    rec = process_atm_withdrawal(atm_id=atm_id, card=card, amount=amount, source="MANUAL")
    st.session_state["mismatch_txn"] = rec
    st.rerun()

rec = st.session_state.get("mismatch_txn")
if rec:
    if not rec.get("ok"):
        st.error(rec.get("error"))
    else:
        mismatch_panels(rec["core_decision"], rec["switch_decision"], rec["atm_result"], rec.get("block_reason"))
        if rec["core_decision"] == "DECLINED" and rec["switch_decision"] == "APPROVED":
            st.error(
                "Mismatch: Core Banking said DECLINED but the switch returned APPROVED and the ATM "
                f"shows {rec['atm_result']}. Simulated bank loss = {format_inr(rec['amount'])} "
                "(ledger was NOT debited)."
            )
        elif rec["status"] == "BLOCKED":
            st.warning(rec.get("block_reason") or "Blocked by containment / controls.")
        else:
            st.info("No override observed. Enable compromise (and disable isolation/controls) then retry with amount > balance.")

        st.write(
            {
                "txn_id": rec["txn_id"],
                "core_reason": rec.get("core_reason"),
                "balance_before": format_inr(rec["balance_before"]),
                "balance_after": format_inr(rec["balance_after"]),
                "risk": f"{rec.get('risk_score')} — {rec.get('risk_reason')}",
            }
        )
