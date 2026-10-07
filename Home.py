"""
Cosmos Bank Cyber Attack Simulation & SOC Response System
Streamlit entry point (Home). All data is fictional and fully offline.

Security concept: an analyst workstation that tells a linear incident story —
normal ops → compromise → cash-out → detection → containment → defense.
"""

from __future__ import annotations

import streamlit as st

from core import database as db
from core.constants import DISCLAIMER
from core.diagram import ensure_architecture_png
from core.ui import format_inr, kpi, page_setup, scale_note, safe_error

state = page_setup("Cosmos Bank SOC Simulation", "🛡️")

st.caption(
    "Academic desktop demo of a *fictional* payment-switch compromise, "
    "ATM cash-out, SWIFT fraud, and NIST-aligned SOC response. "
    "No real malware, no real banks, no network attacks."
)
scale_note()

st.markdown("### Case-study context (historical, for the report)")
st.markdown(
    """
In **August 2018**, **Cosmos Co-operative Bank (Pune)** was reported to have suffered a
cyber incident involving a **compromised payment switch**, **international ATM cash-out**,
and **fraudulent SWIFT messages**. Public reporting described losses on the order of
**₹90+ crore**. This application **does not replay malware or live bank protocols**.
It is a **scaled, fictional laboratory** so students can see *why* switch/core
reconciliation, velocity limits, geo-anomaly controls, FIM, and SWIFT dual-control matter.
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

st.markdown("### Live demo path (mouse-only, in this order)")
st.markdown(
    """
1. **Normal Operation** — approve a legitimate ATM withdrawal; show the full hop-by-hop flow.  
2. **Switch Compromise** — press **SIMULATE SWITCH COMPROMISE**; watch Core **DECLINED** vs Switch **APPROVED** and the FIM hash change.  
3. **ATM Cash-Out** — press **START ATM CASH-OUT**; watch volume, loss, and country charts.  
4. **SOC Dashboard** — read colour-coded alerts R1–R6 and the 10:00–10:09 timeline.  
5. **Containment** (SOC page) — **ISOLATE PAYMENT SWITCH** / **LOCK SWIFT INTERFACE**.  
6. **ENABLE SECURITY CONTROLS** then run the **same** cash-out again — fraud should be **BLOCKED**.  
7. **SWIFT Fraud**, **Investigation**, **Frameworks** — value-based fraud, evidence, Kill Chain / MITRE / NIST.
"""
)

st.markdown("### Architecture")
try:
    png = ensure_architecture_png()
    st.image(str(png), caption="Generated locally with matplotlib (no internet, no Graphviz).")
except Exception as exc:
    st.warning(f"Architecture diagram could not be rendered: {exc}")

st.markdown(
    """
```
  [ATM network] --> [Payment Switch + FIM] --> [Core Banking / ledger]
                          |                         |
                          v                         v
                   [SWIFT gateway]            [SOC rules R1-R6]
                          |                         |
                          +--------> [NIST containment] <------+
```
"""
)

st.info(
    f"{DISCLAIMER}  |  Open the pages in the left sidebar. Simulation state is stored in local SQLite, "
    "so it survives switching tabs."
)
