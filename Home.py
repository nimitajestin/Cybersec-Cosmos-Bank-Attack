"""Home page for the Cosmos Bank SOC Streamlit demo."""

from __future__ import annotations

import streamlit as st

from core import database as db
from core.diagram import ensure_architecture_png
from core.ui import format_inr, kpi, page_setup, scale_note, safe_error

page_setup("Cosmos Bank SOC Simulation", "🛡️")

st.caption("Offline lab. Fictional cards and amounts only.")
scale_note()

st.markdown("### Case study (2018)")
st.markdown(
    """
**Cosmos Co-operative Bank, Pune** — public reporting described a compromised
**payment switch**, **ATM cash-out** from several countries, and **unauthorised SWIFT**
messages. Losses were on the order of **₹90+ crore**. This app models the *control
failures* (switch vs core, velocity, geo, FIM, dual-control), not malware or live protocols.
"""
)

try:
    db.init_db()
    accounts = db.get_accounts()
    alerts = db.alert_counts()
    txns = db.list_transactions(limit=5000)
    atm_tx = [t for t in txns if t.get("txn_type") == "ATM" and t.get("source") != "SEED"]
    loss = sum(
        float(t["amount"])
        for t in atm_tx
        if t.get("atm_result") == "CASH_DISPENSED" and t.get("is_simulated_fraud")
    )
except db.DatabaseError as exc:
    safe_error(exc)
    st.stop()

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi("Fictional accounts", str(len(accounts)))
with c2:
    kpi("Simulated ATM txns", str(len(atm_tx)))
with c3:
    kpi("CRITICAL alerts", str(alerts.get("CRITICAL", 0)))
with c4:
    kpi("Simulated cash-out loss", format_inr(loss))

st.markdown("### Suggested order")
st.markdown(
    """
1. **Normal Operation** — legitimate withdrawal, hop-by-hop.  
2. **Switch Compromise** — toggle compromise; core DECLINED vs switch APPROVED; FIM hash.  
3. **ATM Cash-Out** — burst of fictional withdrawals.  
4. **SOC Dashboard** — alerts R1–R6, isolate switch, lock SWIFT, enable controls, replay.  
5. **SWIFT Fraud**, **Investigation**, **Frameworks**.
"""
)

st.markdown("### Architecture")
try:
    png = ensure_architecture_png()
    st.image(str(png), caption="ATM → switch → core. The switch is the trust boundary.")
except Exception as exc:
    st.warning(f"Could not load architecture diagram: {exc}")

st.caption("Use the sidebar pages. State is stored in local SQLite.")
