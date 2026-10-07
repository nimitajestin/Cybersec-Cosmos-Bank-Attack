"""
Page 7 — Academic mappings: Cyber Kill Chain, MITRE ATT&CK, NIST.

Security concept: map only what the public case and this lab actually
demonstrate. Unknown intrusion stages stay marked "?" — that is the honest
answer, not a gap in the demo.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.incident_response import mark_lessons_learned, nist_checklist
from core.ui import page_setup, safe_dataframe

state = page_setup("Frameworks", "📚")
mark_lessons_learned()

st.markdown(
    "This page is written for the **project report / viva**. It distinguishes "
    "**documented / demonstrated** steps from **unknown** intrusion stages "
    "(reconnaissance, delivery, exploitation of the switch host)."
)

st.markdown("### Cyber Kill Chain")
kill = pd.DataFrame(
    [
        {
            "Stage": "1. Reconnaissance",
            "Status": "?",
            "In this lab / public case": "Not demonstrated. How the switch environment was first studied is not publicly confirmed.",
        },
        {
            "Stage": "2. Weaponization",
            "Status": "?",
            "In this lab / public case": "Not demonstrated. No malware sample is used or shipped.",
        },
        {
            "Stage": "3. Delivery",
            "Status": "?",
            "In this lab / public case": "Unknown. Public reporting did not reliably document the delivery channel.",
        },
        {
            "Stage": "4. Exploitation",
            "Status": "?",
            "In this lab / public case": "Unknown at host level. We do **not** simulate an exploit — only the *result* (switch logic no longer mirrors core).",
        },
        {
            "Stage": "5. Installation / Compromise",
            "Status": "Documented in demo",
            "In this lab / public case": "SIMULATE SWITCH COMPROMISE + FIM hash change stands in for persistence on the payment switch.",
        },
        {
            "Stage": "6. Command & Control / Fraudulent approvals",
            "Status": "Documented in demo",
            "In this lab / public case": "Switch returns APPROVED while core returns DECLINED (R4 mismatch).",
        },
        {
            "Stage": "7. Actions on Objectives",
            "Status": "Documented in demo",
            "In this lab / public case": "ATM cash-out across fictional IN/UAE/TH/MY terminals; SWIFT transfer to Hong Kong Bank (fictional).",
        },
    ]
)
safe_dataframe(kill, use_container_width=True, hide_index=True)
st.caption("Stages marked '?' are academically honest unknowns — do not invent a kill-chain story the evidence does not support.")

st.markdown("### MITRE ATT&CK mapping")
mitre = pd.DataFrame(
    [
        {
            "Technique": "T1657 Financial Theft",
            "Confidence": "Evidence-based (lab + public case pattern)",
            "Notes": (
                "ATM cash-out and unauthorised SWIFT value transfer are direct financial-theft "
                "objectives. This lab produces ledger evidence (txn rows, amounts, countries)."
            ),
        },
        {
            "Technique": "T1565 Data Manipulation",
            "Confidence": "ANALYTICAL MAPPING — not publicly confirmed",
            "Notes": (
                "We *model* the switch authorisation flag being altered so DECLINE becomes APPROVE. "
                "That is a teaching analogue of data manipulation on a payment processor. "
                "It is **not** a claim that T1565 was forensically proven in the 2018 incident."
            ),
        },
        {
            "Technique": "T1496 / resource hijack, T1078 Valid Accounts, etc.",
            "Confidence": "Not mapped",
            "Notes": "Out of scope. Mapping unused ATT&CK IDs would over-claim.",
        },
    ]
)
safe_dataframe(mitre, use_container_width=True, hide_index=True)

st.markdown("### NIST SP 800-61 — how this demo ticks each box")
nist = nist_checklist()
nist_explain = {
    "Preparation": "Playbooks, FIM baseline, rule catalogue R1–R6, and this lab environment.",
    "Detection": "Deterministic alerts when cash-out / SWIFT rows hit R1–R6.",
    "Analysis": "Investigation page: hop-by-hop decisions, geo, evidence checklist.",
    "Containment": "ISOLATE PAYMENT SWITCH and LOCK SWIFT INTERFACE (fail closed).",
    "Eradication": "ENABLE SECURITY CONTROLS (FIM, reconciliation, velocity, geo, SWIFT verify).",
    "Recovery": "RESTORE SWITCH to the known-good SHA-256; RESET SIMULATION for the next demo.",
    "Lessons Learned": "This page — kill chain honesty, MITRE caution, scaled-loss disclaimer.",
}
rows = []
for stage in nist:
    name = stage["stage"]
    rows.append(
        {
            "Stage": name,
            "Complete in this run": "Yes" if stage.get("completed") else "Not yet",
            "What the demo uses it for": nist_explain.get(name, ""),
            "Completed at": stage.get("completed_at") or "—",
        }
    )
safe_dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.markdown("### Defensive controls exercised")
st.markdown(
    """
| Control | Feature | When it blocks |
|---|---|---|
| Switch/core reconciliation | R4 | Switch APPROVED ≠ core DECLINED |
| Velocity limit | R2 | >10 txns / card / minute |
| Geo-anomaly | R3 | Same card in 2+ countries / 30 min |
| FIM (SHA-256) | Dummy PaymentSwitch.exe | Hash mismatch while controls ON |
| SWIFT dual-control | R6 + whitelist check | Transfer ≥ ₹1 crore without second approval |
| Containment | Isolate / lock | All new ATM or SWIFT requests fail closed |
"""
)

_ = state  # silence unused if sidebar already consumed it
