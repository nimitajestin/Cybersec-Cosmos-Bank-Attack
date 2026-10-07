"""
Page 1 — Normal ATM authorisation path (healthy payment switch).

Security concept: cash is dispensed only when Core Banking approves the
debit and the switch faithfully forwards that decision.
"""

from __future__ import annotations

import streamlit as st

from core import database as db
from core.bank_simulator import process_atm_withdrawal
from core.ui import format_inr, mismatch_panels, page_setup, safe_dataframe, safe_error

state = page_setup("Normal Operation", "✅")

st.markdown(
    "Walk a **legitimate** withdrawal through **ATM → Payment Switch → Core Banking**. "
    "Use a small amount that is **below** available balance so the core can APPROVE."
)

try:
    db.init_db()
    accounts = db.get_accounts(include_swift=False)
    atms = [a for a in db.get_atms() if a["country"] == "India"]
except db.DatabaseError as exc:
    safe_error(exc)
    st.stop()

if not accounts or not atms:
    st.error("Master data missing. Click RESET SIMULATION on the SOC page.")
    st.stop()

col_a, col_b = st.columns(2)
with col_a:
    card = st.selectbox("Card number (masked)", [a["card"] for a in accounts], index=0)
    account = next(a for a in accounts if a["card"] == card)
    st.caption(f"Holder: {account['holder_name']}  ·  Status: {account['status']}")
    st.metric("Available balance", format_inr(account["available_balance"]))
with col_b:
    atm_id = st.selectbox("ATM ID", [a["atm_id"] for a in atms], index=0)
    atm = next(a for a in atms if a["atm_id"] == atm_id)
    st.caption(f"{atm['city']}, {atm['country']}  ·  {atm['status']}")
    amount = st.number_input("Withdrawal amount (₹)", min_value=100, max_value=50000, value=1000, step=100)

if state.get("switch_isolated"):
    st.warning("Payment switch is currently ISOLATED. This request will be BLOCKED until you reset or recover.")
if state.get("switch_compromised"):
    st.info("Compromise flag is ON. For a clean 'normal' demo, turn it off on the Switch Compromise page.")

if st.button("SUBMIT ATM WITHDRAWAL", type="primary", use_container_width=True):
    result = process_atm_withdrawal(atm_id=atm_id, card=card, amount=amount, source="MANUAL")
    st.session_state["last_normal_txn"] = result
    if result.get("ok") and result.get("alerts"):
        st.rerun()

result = st.session_state.get("last_normal_txn")
if result:
    if not result.get("ok"):
        st.error(result.get("error") or "Validation failed.")
    else:
        st.success(f"Logged {result['txn_id']}  ·  status {result['status']}")
        mismatch_panels(
            result["core_decision"],
            result["switch_decision"],
            result["atm_result"],
            result.get("block_reason"),
        )
        st.markdown("#### Hop-by-hop authorisation flow")
        st.markdown(
            f"""
1. **ATM {result['atm_id']}** receives card `{result['card']}` request for **{format_inr(result['amount'])}**.  
2. **Payment Switch** forwards the authorisation to Core Banking.  
3. **Core Banking** checks ledger: balance was **{format_inr(result['balance_before'])}** → **{result['core_decision']}**.  
4. **Switch decision** returned to ATM: **{result['switch_decision']}**.  
5. **ATM result:** **{result['atm_result']}**. New simulated balance: **{format_inr(result['balance_after'])}**.  
6. **Risk:** {result.get('risk_score')}/100 — {result.get('risk_reason')}
"""
        )
        safe_dataframe(
            {
                "Field": [
                    "txn_id",
                    "timestamp",
                    "atm_id",
                    "card",
                    "amount",
                    "balance_before",
                    "core_decision",
                    "switch_decision",
                    "status",
                    "risk_score",
                    "risk_reason",
                ],
                "Value": [
                    str(result["txn_id"]),
                    str(result["timestamp"]),
                    str(result["atm_id"]),
                    str(result["card"]),
                    format_inr(result["amount"]),
                    format_inr(result["balance_before"]),
                    str(result["core_decision"]),
                    str(result["switch_decision"]),
                    str(result["status"]),
                    str(result["risk_score"]),
                    str(result["risk_reason"]),
                ],
            },
            hide_index=True,
            use_container_width=True,
        )

st.markdown("#### Recent ledger (including seeded baseline)")
try:
    recent = db.list_transactions(txn_type="ATM", limit=15)
    if recent:
        safe_dataframe(recent, use_container_width=True, hide_index=True)
except db.DatabaseError as exc:
    safe_error(exc)
