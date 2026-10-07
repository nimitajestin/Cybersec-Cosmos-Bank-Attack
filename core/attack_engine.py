"""
Simulated payment-switch compromise, ATM cash-out, and SWIFT fraud.

Security concept: this module NEVER talks to a real network or bank. It only
flips local SQLite flags, mutates a dummy SHA-256 (FIM), and writes fictional
transactions so students can watch detection and containment work.
"""

from __future__ import annotations

import random
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

from core import database as db
from core.bank_simulator import process_atm_withdrawal, process_burst, validate_amount
from core.constants import (
    LEGIT_SWITCH_HASH,
    SWIFT_AMOUNT,
    SWIFT_BENEFICIARY,
    TAMPERED_SWITCH_HASH,
)
from core.detection_engine import evaluate_transaction, risk_from_alerts


ProgressCb = Optional[Callable[[int, int, str], None]]


def fim_status() -> Dict[str, Any]:
    """Compare known-good vs live SHA-256 of the dummy PaymentSwitch.exe blob."""
    db.init_db()
    state = db.get_state()
    before = str(state.get("legit_switch_hash") or LEGIT_SWITCH_HASH)
    after = str(state.get("live_switch_hash") or LEGIT_SWITCH_HASH)
    violated = before.lower() != after.lower()
    return {
        "file_name": "PaymentSwitch.exe (dummy / fictional)",
        "algorithm": "SHA-256",
        "before": before,
        "after": after,
        "violated": violated,
        "compromised_flag": bool(state.get("switch_compromised")),
    }


def set_switch_compromise(enabled: bool) -> Dict[str, Any]:
    """Toggle the simulated switch compromise and the FIM hash together."""
    db.init_db()
    live = TAMPERED_SWITCH_HASH if enabled else LEGIT_SWITCH_HASH
    db.update_state(
        switch_compromised=1 if enabled else 0,
        live_switch_hash=live,
    )
    if enabled:
        db.add_timeline(
            "10:02",
            "Payment switch compromise simulated — FIM hash changed, override-auth active.",
            "compromise",
        )
        return {
            "ok": True,
            "message": "Switch COMPROMISED. ATM authorisations will ignore core DECLINED decisions.",
            "fim": fim_status(),
        }
    return {
        "ok": True,
        "message": "Switch restored (compromise flag off, FIM hash matches known-good).",
        "fim": fim_status(),
    }


def toggle_switch_compromise() -> Dict[str, Any]:
    """Button helper: invert the current compromise boolean in SQLite."""
    state = db.get_state()
    return set_switch_compromise(not bool(state.get("switch_compromised")))


def _cashout_requests(n: int, wave: int) -> List[Dict[str, Any]]:
    """Build 100–300 fictional multi-country ATM requests (no real terminals)."""
    atms = db.get_atms()
    cards = [a["card"] for a in db.get_accounts(include_swift=False)]
    rng = random.Random(2018 + wave * 17 + n)
    now = db.utc_now()
    requests: List[Dict[str, Any]] = []
    # Force early geo-spread on the same cards so R3 is visible in the viva.
    hot_cards = cards[:4]
    for i in range(n):
        atm = atms[i % len(atms)]
        if i < 40:
            card = hot_cards[i % len(hot_cards)]
        else:
            card = cards[rng.randrange(len(cards))]
        account = db.get_account(card) or {"available_balance": 0}
        bal = float(account.get("available_balance") or 0)
        # Mix: over-balance (R1) and under-balance high-velocity (R2/R3).
        if rng.random() < 0.65:
            amount = round(rng.uniform(max(bal + 500, 5000), max(bal + 80000, 90000)), 0)
        else:
            amount = round(rng.uniform(2000, 20000), 0)
        ts = now + timedelta(seconds=i // 4)
        requests.append(
            {
                "atm_id": atm["atm_id"],
                "card": card,
                "amount": amount,
                "timestamp": db.iso(ts),
            }
        )
    return requests


def run_atm_cashout(
    n: Optional[int] = None,
    progress_cb: ProgressCb = None,
) -> Dict[str, Any]:
    """
    Generate a fictional ATM cash-out burst across India/UAE/Thailand/Malaysia.

    Demonstrates high-volume, low-value fraud after a switch compromise.
    """
    db.init_db()
    state = db.get_state()
    if not n:
        n = random.randint(120, 220)
    n = max(100, min(300, int(n)))
    wave = int(state.get("cashout_wave") or 0) + 1
    db.update_state(cashout_wave=wave)

    if progress_cb:
        progress_cb(0, n, "Building fictional ATM requests…")

    requests = _cashout_requests(n, wave)
    if progress_cb:
        progress_cb(0, n, "Authorising fictional ATM burst…")

    burst = process_burst(requests, attack_wave=wave, source="CASHOUT", progress_cb=progress_cb)
    if not burst.get("ok"):
        return {"ok": False, "message": burst.get("error") or "Cash-out simulation failed.", **burst}

    results = burst.get("results") or []
    dispensed = float(burst.get("dispensed") or 0)
    blocked = int(burst.get("blocked") or 0)
    first_fraud = next(
        (
            r
            for r in results
            if r.get("atm_result") == "CASH_DISPENSED" and r.get("is_simulated_fraud")
        ),
        None,
    )
    if first_fraud:
        db.add_timeline(
            "10:03",
            "First fraudulent ATM cash-out dispensed (core DECLINED / switch APPROVED).",
            "fraud",
        )

    controls = bool(db.get_state().get("security_controls"))
    return {
        "ok": True,
        "wave": wave,
        "count": len(results),
        "dispensed": dispensed,
        "blocked": blocked,
        "defense_mode": controls,
        "results": results,
        "message": (
            f"Wave {wave}: {len(results)} simulated txns, "
            f"dispensed INR {dispensed:,.0f}, blocked {blocked}. "
            + ("Defense mode was ON." if controls else "Defense mode was OFF.")
        ),
    }


def process_swift_transfer(
    amount: Any = SWIFT_AMOUNT,
    beneficiary: str = SWIFT_BENEFICIARY,
) -> Dict[str, Any]:
    """
    Simulate one unauthorised SWIFT payment from a compromised environment.

    Kept separate from the ATM pipeline (different rail, different controls).
    """
    ok, value, err = validate_amount(amount)
    if not ok:
        return {"ok": False, "error": err}

    try:
        db.init_db()
        state = db.get_state()
        account = db.get_account("XXXX-XXXX-SW01")
    except db.DatabaseError as exc:
        return {"ok": False, "error": str(exc)}

    if not account:
        return {"ok": False, "error": "Fictional SWIFT settlement account missing — reset the simulation."}

    balance_before = float(account["available_balance"])
    compromised = bool(state.get("switch_compromised"))
    locked = bool(state.get("swift_locked"))
    controls = bool(state.get("security_controls"))

    # Core: no valid customer/board instruction exists for this beneficiary.
    core_decision = "DECLINED"
    core_reason = "No authorised payment instruction on file (maker-checker failed)."

    block_reason = None
    if locked:
        block_reason = "SWIFT interface locked due to confirmed incident."
    elif controls:
        block_reason = (
            "SWIFT verification: beneficiary not on whitelist and dual-control not satisfied."
        )
    elif not compromised:
        block_reason = "Healthy environment: SWIFT gateway refused unauthorised message."

    if block_reason:
        switch_decision = "BLOCKED"
        status = "BLOCKED"
        atm_result = "NOT_SENT"
        new_balance = balance_before
        is_fraud = 1
    elif compromised:
        switch_decision = "APPROVED"
        status = "UNAUTHORIZED"
        atm_result = "SWIFT_SENT"
        new_balance = round(balance_before - value, 2)
        is_fraud = 1
        try:
            db.set_balance("XXXX-XXXX-SW01", new_balance)
        except db.DatabaseError as exc:
            return {"ok": False, "error": str(exc)}
    else:
        switch_decision = core_decision
        status = "DECLINED"
        atm_result = "NOT_SENT"
        new_balance = balance_before
        is_fraud = 0

    txn_id = db.next_id("TXN", "transactions", "txn_id")
    record: Dict[str, Any] = {
        "txn_id": txn_id,
        "timestamp": db.iso(),
        "atm_id": "SWIFT-GW-01",
        "card": "XXXX-XXXX-SW01",
        "amount": value,
        "balance_before": balance_before,
        "balance_after": new_balance,
        "core_decision": core_decision,
        "switch_decision": switch_decision,
        "atm_result": atm_result,
        "status": status,
        "risk_score": 0,
        "risk_reason": core_reason,
        "country": "India",
        "txn_type": "SWIFT",
        "is_simulated_fraud": is_fraud,
        "attack_wave": 0,
        "beneficiary": beneficiary,
        "block_reason": block_reason,
        "source": "SWIFT",
        "ok": True,
        "error": None,
        "core_reason": core_reason,
    }
    try:
        db.insert_transaction(record)
        alerts = evaluate_transaction(record, persist_alerts=True)
        score, reason = risk_from_alerts(alerts, record)
        record["alerts"] = alerts
        record["risk_score"] = score
        record["risk_reason"] = reason
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE transactions SET risk_score = ?, risk_reason = ? WHERE txn_id = ?",
                (score, reason, txn_id),
            )
        db.add_timeline(
            "10:05",
            f"SWIFT message {status}: {beneficiary} for simulated INR {value:,.0f}.",
            "swift",
        )
    except db.DatabaseError as exc:
        return {"ok": False, "error": str(exc)}
    return record
