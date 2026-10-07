"""
NIST SP 800-61 incident-response actions for the simulated compromise.

Security concept: after detection, responders *contain* (isolate the switch,
lock SWIFT), then eradicate/recover. Fail-closed beats fail-open.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core import database as db
from core.constants import LEGIT_SWITCH_HASH


def on_alerts_fired(alerts: List[Dict[str, Any]]) -> None:
    """Advance Detection (and Analysis for CRITICAL) when the rule engine fires."""
    if not alerts:
        return
    db.complete_nist("Detection")
    if any(a.get("severity") == "CRITICAL" for a in alerts):
        db.complete_nist("Analysis")
        state = db.get_state()
        if not state.get("incident_declared"):
            db.update_state(incident_declared=1)
            db.add_timeline(
                "10:08",
                "Incident declared — CRITICAL SOC alerts (R1/R3/R4) confirm switch fraud.",
                "incident",
            )


def isolate_payment_switch() -> Dict[str, Any]:
    """Containment: take the compromised switch offline so ATMs fail closed."""
    db.init_db()
    db.update_state(switch_isolated=1)
    db.complete_nist("Containment")
    db.add_timeline(
        "10:09",
        "Payment switch isolated — all new ATM authorisations BLOCKED.",
        "containment",
    )
    return {
        "ok": True,
        "message": "Payment switch isolated. New ATM requests will be BLOCKED.",
    }


def lock_swift_interface() -> Dict[str, Any]:
    """Containment: freeze the simulated SWIFT gateway to stop high-value fraud."""
    db.init_db()
    db.update_state(swift_locked=1)
    db.complete_nist("Containment")
    db.add_timeline(
        "10:09",
        "SWIFT interface locked — outbound payment messages BLOCKED.",
        "containment",
    )
    return {"ok": True, "message": "SWIFT interface locked. Outbound transfers BLOCKED."}


def enable_security_controls(enabled: bool = True) -> Dict[str, Any]:
    """
    Activate (or disable) defensive controls: FIM, R4 reconciliation,
    velocity limits, geo-anomaly blocking, SWIFT dual-verification.
    """
    db.init_db()
    db.update_state(security_controls=1 if enabled else 0)
    if enabled:
        db.complete_nist("Eradication")
        db.add_timeline(
            "10:10",
            "Security controls enabled — FIM, reconciliation, velocity, geo, SWIFT verification.",
            "defense",
        )
        return {"ok": True, "message": "Defense mode ON. The same cash-out pattern should now be BLOCKED."}
    return {"ok": True, "message": "Defense mode OFF. Switch behaviour follows compromise flag only."}


def restore_switch_integrity() -> Dict[str, Any]:
    """Recovery: restore the known-good FIM hash and clear the compromise flag."""
    db.init_db()
    db.update_state(
        switch_compromised=0,
        live_switch_hash=LEGIT_SWITCH_HASH,
        switch_isolated=0,
    )
    db.complete_nist("Recovery")
    db.add_timeline(
        "10:12",
        "Payment switch restored from known-good hash; compromise flag cleared.",
        "recovery",
    )
    return {"ok": True, "message": "Switch restored to known-good integrity hash."}


def mark_lessons_learned() -> None:
    """Tick Lessons Learned when the Frameworks page is opened (post-incident review)."""
    db.complete_nist("Lessons Learned")


def reset_simulation() -> Dict[str, Any]:
    """Full demo reset: wipe fraud rows, restore balances, return to 10:00 normal ops."""
    try:
        db.reset_operational_data()
        return {"ok": True, "message": "Simulation reset. Accounts, switch, and timeline restored to 10:00."}
    except db.DatabaseError as exc:
        return {"ok": False, "message": str(exc)}


def nist_checklist() -> List[Dict[str, Any]]:
    """Return NIST stages for the sidebar / containment page checklist."""
    db.init_db()
    return db.get_nist()
