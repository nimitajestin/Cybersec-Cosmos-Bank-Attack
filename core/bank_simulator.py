"""
ATM → Payment Switch → Core Banking simulator.

Security concept: in a healthy payment switch, the ATM only dispenses cash
when *core banking* authorises the debit. A compromised switch that ignores
the core decision is how an ATM cash-out fraud is modelled in this demo.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import database as db
from core.constants import LEGIT_SWITCH_HASH
from core.detection_engine import evaluate_batch, evaluate_transaction, risk_from_alerts

ProgressCb = Optional[Callable[[int, int, str], None]]


def validate_amount(amount: Any) -> Tuple[bool, float, str]:
    """Reject non-numeric or out-of-range withdrawal amounts before they hit the switch."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return False, 0.0, "Amount must be a number."
    if value <= 0:
        return False, 0.0, "Amount must be greater than zero."
    if value > 50_000_000:
        return False, 0.0, "Amount exceeds the simulation ceiling (INR 5 crore)."
    return True, round(value, 2), ""


def _ts_cutoff(timestamp: str, **delta) -> str:
    """Compute an ISO cutoff so velocity/geo windows can be applied in memory."""
    return db.iso(db.parse_iso(timestamp) - timedelta(**delta))


def _window(history: List[Dict[str, Any]], card: str, cutoff: str) -> List[Dict[str, Any]]:
    """In-memory per-card time window (avoids one SQL round-trip per cash-out row)."""
    return [
        r
        for r in history
        if r.get("card") == card
        and r.get("txn_type") == "ATM"
        and str(r.get("timestamp") or "") >= cutoff
    ]


def authorise_atm(
    state: Dict[str, Any],
    account: Dict[str, Any],
    atm: Dict[str, Any],
    value: float,
    source: str,
    attack_wave: int,
    is_simulated_fraud: bool,
    timestamp: str,
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Pure authorisation decision (core + switch + controls) without touching SQLite.

    Demonstrates fail-closed isolation, FIM, R4 reconciliation, velocity and geo blocks.
    """
    balance_before = float(account["available_balance"])
    country = atm["country"]
    controls = bool(state.get("security_controls"))
    compromised = bool(state.get("switch_compromised"))
    isolated = bool(state.get("switch_isolated"))
    hash_mismatch = str(state.get("live_switch_hash") or "") != str(
        state.get("legit_switch_hash") or LEGIT_SWITCH_HASH
    )

    if value > balance_before:
        core_decision = "DECLINED"
        core_reason = "Insufficient funds"
    else:
        core_decision = "APPROVED"
        core_reason = "Sufficient funds"

    block_reason = None
    control_hits: List[str] = []

    if isolated:
        block_reason = "Payment switch isolated due to confirmed compromise."
        control_hits.append("CONTAINMENT")

    if controls and not block_reason:
        if compromised or hash_mismatch:
            block_reason = "FIM: payment-switch integrity failure — request blocked."
            control_hits.append("FIM")
        if not block_reason and compromised and core_decision == "DECLINED":
            block_reason = "Reconciliation (R4): switch/core mismatch — request blocked."
            control_hits.append("R4")
        if not block_reason:
            cutoff_60 = _ts_cutoff(timestamp, seconds=60)
            if len(_window(history, account["card"], cutoff_60)) >= 10:
                block_reason = "Velocity limit: >10 transactions per card per minute — blocked."
                control_hits.append("R2")
        if not block_reason:
            cutoff_30 = _ts_cutoff(timestamp, minutes=30)
            countries = {r.get("country") for r in _window(history, account["card"], cutoff_30) if r.get("country")}
            countries.add(country)
            if len(countries) >= 2:
                block_reason = "Geo-anomaly: same card in 2+ countries within 30 minutes — blocked."
                control_hits.append("R3")

    if block_reason:
        switch_decision = "BLOCKED"
    elif compromised:
        switch_decision = "APPROVED"
    else:
        switch_decision = core_decision

    new_balance = balance_before
    debited = False
    fraud_flag = 1 if is_simulated_fraud else 0
    if switch_decision == "APPROVED":
        atm_result = "CASH_DISPENSED"
        if core_decision == "APPROVED":
            new_balance = round(balance_before - value, 2)
            debited = True
            status = "SUCCESS"
        else:
            status = "FRAUD_CASHOUT"
            fraud_flag = 1
    elif switch_decision == "BLOCKED":
        atm_result = "BLOCKED"
        status = "BLOCKED"
    else:
        atm_result = "NO_CASH"
        status = "DECLINED"

    return {
        "timestamp": timestamp,
        "atm_id": atm["atm_id"],
        "card": account["card"],
        "amount": value,
        "balance_before": balance_before,
        "balance_after": new_balance,
        "core_decision": core_decision,
        "switch_decision": switch_decision,
        "atm_result": atm_result,
        "status": status,
        "risk_score": 0,
        "risk_reason": core_reason,
        "country": country,
        "txn_type": "ATM",
        "is_simulated_fraud": fraud_flag,
        "attack_wave": int(attack_wave),
        "beneficiary": None,
        "block_reason": block_reason,
        "source": source,
        "core_reason": core_reason,
        "control_hits": control_hits,
        "debited": debited,
        "ok": True,
        "error": None,
        "alerts": [],
    }


def process_atm_withdrawal(
    atm_id: str,
    card: str,
    amount: Any,
    source: str = "MANUAL",
    attack_wave: int = 0,
    is_simulated_fraud: bool = False,
    timestamp: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """
    Run one simulated ATM withdrawal through Core Banking and the Payment Switch.

    Demonstrates authorisation, optional switch override, FIM/reconciliation
    blocking, and immutable transaction logging.
    """
    ok, value, err = validate_amount(amount)
    if not ok:
        return {"ok": False, "error": err}

    try:
        db.init_db()
        state = db.get_state()
        account = db.get_account(card)
        atm = db.get_atm(atm_id)
        history = db.list_transactions(txn_type="ATM", limit=400)
    except db.DatabaseError as exc:
        return {"ok": False, "error": str(exc)}

    if not account:
        return {"ok": False, "error": "Unknown card. Select a card from the list."}
    if account.get("status") != "ACTIVE":
        return {"ok": False, "error": "Account is not ACTIVE in the simulation."}
    if not atm:
        return {"ok": False, "error": "Unknown ATM ID."}

    record = authorise_atm(
        state=state,
        account=account,
        atm=atm,
        value=value,
        source=source,
        attack_wave=attack_wave,
        is_simulated_fraud=is_simulated_fraud,
        timestamp=timestamp or db.iso(),
        history=history,
    )
    if not persist:
        record["txn_id"] = "TXN-PREVIEW"
        return record

    try:
        record["txn_id"] = db.next_id("TXN", "transactions", "txn_id")
        if record.get("debited"):
            db.set_balance(card, record["balance_after"])
        db.insert_transaction(record)
        alerts = evaluate_transaction(record, persist_alerts=True)
        score, reason = risk_from_alerts(alerts, record)
        record["alerts"] = alerts
        record["risk_score"] = score
        record["risk_reason"] = reason
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE transactions SET risk_score = ?, risk_reason = ? WHERE txn_id = ?",
                (score, reason, record["txn_id"]),
            )
    except db.DatabaseError as exc:
        return {"ok": False, "error": str(exc)}
    return record


def process_burst(
    requests: List[Dict[str, Any]],
    attack_wave: int,
    source: str = "CASHOUT",
    progress_cb: ProgressCb = None,
) -> Dict[str, Any]:
    """
    Authorise a cash-out burst in memory, then persist once.

    Security concept: the same policy engine runs on 1 txn or 300 — defense
    mode does not get a 'back door' SQL insert that skips controls.
    """
    db.init_db()
    state = db.get_state()
    accounts = {a["card"]: dict(a) for a in db.get_accounts(include_swift=False)}
    atms = {a["atm_id"]: a for a in db.get_atms()}
    history = db.list_transactions(txn_type="ATM", limit=4000)
    start_n = db.next_txn_number()
    balances = {c: float(a["available_balance"]) for c, a in accounts.items()}
    records: List[Dict[str, Any]] = []
    n = len(requests)

    for i, req in enumerate(requests):
        card = req["card"]
        atm = atms.get(req["atm_id"])
        if card not in accounts or not atm:
            continue
        ok, value, err = validate_amount(req["amount"])
        if not ok:
            continue
        acc = dict(accounts[card])
        acc["available_balance"] = balances[card]
        rec = authorise_atm(
            state=state,
            account=acc,
            atm=atm,
            value=value,
            source=source,
            attack_wave=attack_wave,
            is_simulated_fraud=True,
            timestamp=req.get("timestamp") or db.iso(),
            history=history,
        )
        rec["txn_id"] = f"TXN-{start_n + i:06d}"
        if rec.get("debited"):
            balances[card] = float(rec["balance_after"])
        history.append(rec)
        records.append(rec)
        if progress_cb and (i % 20 == 0 or i + 1 == n):
            progress_cb(i + 1, n, f"Authorised {i + 1}/{n} simulated ATM requests")

    if progress_cb:
        progress_cb(n, n, "Writing ledger and SOC alerts…")

    try:
        for card, bal in balances.items():
            db.set_balance(card, bal)
        db.insert_transactions_bulk(records)
        alerts = evaluate_batch(records, history, state)
        if any(a.get("severity") == "CRITICAL" for a in alerts) or any(
            a.get("severity") == "HIGH" for a in alerts
        ):
            from core.incident_response import on_alerts_fired

            on_alerts_fired(alerts)
        with db.get_conn() as conn:
            conn.executemany(
                "UPDATE transactions SET risk_score = ?, risk_reason = ? WHERE txn_id = ?",
                [(r.get("risk_score", 0), r.get("risk_reason", ""), r["txn_id"]) for r in records],
            )
    except db.DatabaseError as exc:
        return {"ok": False, "error": str(exc), "results": [], "count": 0, "dispensed": 0.0, "blocked": 0}

    dispensed = sum(float(r["amount"]) for r in records if r.get("atm_result") == "CASH_DISPENSED")
    blocked = sum(1 for r in records if r.get("status") == "BLOCKED")
    return {
        "ok": True,
        "results": records,
        "count": len(records),
        "dispensed": dispensed,
        "blocked": blocked,
        "errors": 0,
    }
