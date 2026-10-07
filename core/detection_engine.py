"""
Deterministic, rule-based SOC detection (R1–R6). No machine learning.

Security concept: signature / threshold detections that an analyst can
explain in a viva — each alert cites the exact rule that fired.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Tuple

from core import database as db
from core.constants import R1_CRORE

RULES = {
    "R1": {
        "name": "Withdrawal exceeds available balance",
        "severity": "CRITICAL",
        "desc": "Core banking would decline; cash leaving an ATM anyway is theft of float.",
    },
    "R2": {
        "name": "High per-card velocity",
        "severity": "HIGH",
        "desc": ">10 transactions on one card inside 60 seconds.",
    },
    "R3": {
        "name": "Impossible travel / multi-country card use",
        "severity": "CRITICAL",
        "desc": "Same card used in 2 or more countries within 30 minutes.",
    },
    "R4": {
        "name": "Switch / core decision mismatch",
        "severity": "CRITICAL",
        "desc": "Payment switch authorised a transaction that core banking declined (or vice versa).",
    },
    "R5": {
        "name": "Network velocity spike",
        "severity": "HIGH",
        "desc": "ATM traffic in the last minute is ≥ 3× the quiet-hour baseline.",
    },
    "R6": {
        "name": "SWIFT transfer above ₹1 crore",
        "severity": "HIGH",
        "desc": "High-value payment-message threshold for dual control.",
    },
}


def _severity_rank(sev: str) -> int:
    """Order severities so the dashboard can colour-code the worst first."""
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(sev, 0)


def _add_alert(
    fired: List[Dict[str, Any]],
    rule_id: str,
    txn: Dict[str, Any],
    extra: str,
) -> None:
    """Build one explainable alert record (rule id is always visible to the analyst)."""
    meta = RULES[rule_id]
    fired.append(
        {
            "rule_id": rule_id,
            "rule_name": meta["name"],
            "severity": meta["severity"],
            "message": f"{rule_id} {meta['name']}: {extra}",
            "txn_id": txn.get("txn_id"),
            "timestamp": txn.get("timestamp") or db.iso(),
        }
    )


def evaluate_transaction(txn: Dict[str, Any], persist_alerts: bool = True) -> List[Dict[str, Any]]:
    """
    Run R1–R6 against a single simulated transaction and optionally persist hits.

    Demonstrates why each ATM cash-out or SWIFT fraud row is detectable with
    simple, auditable thresholds instead of a black-box model.
    """
    fired: List[Dict[str, Any]] = []
    try:
        db.init_db()
        state = db.get_state()
        amount = float(txn.get("amount") or 0)
        balance_before = float(txn.get("balance_before") or 0)
        card = str(txn.get("card") or "")
        country = txn.get("country")
        ts = db.parse_iso(str(txn.get("timestamp") or db.iso()))
        txn_type = str(txn.get("txn_type") or "ATM")

        # R1 — withdrawal > available balance
        if txn_type == "ATM" and amount > balance_before:
            _add_alert(
                fired,
                "R1",
                txn,
                f"requested {amount:.2f} but available balance was {balance_before:.2f}.",
            )

        # R2 — >10 txns per card per minute
        if card:
            window = db.transactions_for_card_since(card, ts - timedelta(seconds=60))
            # include current txn if it is already persisted
            ids = {r["txn_id"] for r in window}
            count = len(window) + (0 if txn.get("txn_id") in ids else 1)
            if count > 10:
                _add_alert(fired, "R2", txn, f"{count} transactions for {card} in 60 seconds.")

        # R3 — same card in 2+ countries within 30 min
        if card and country:
            geo_rows = db.transactions_for_card_since(card, ts - timedelta(minutes=30))
            countries = {r.get("country") for r in geo_rows if r.get("country")}
            countries.add(country)
            if len(countries) >= 2:
                joined = ", ".join(sorted(str(c) for c in countries))
                _add_alert(fired, "R3", txn, f"countries observed: {joined}.")

        # R4 — switch approval ≠ core decision
        core_d = str(txn.get("core_decision") or "")
        switch_d = str(txn.get("switch_decision") or "")
        if core_d and switch_d and core_d != switch_d and switch_d != "BLOCKED":
            _add_alert(fired, "R4", txn, f"core={core_d} vs switch={switch_d}.")
        elif core_d and switch_d and core_d != switch_d and switch_d == "BLOCKED":
            # Isolation / controls blocking is expected; still note mismatch at LOW? Skip — not an attack signal.
            pass

        # R5 — 3× baseline velocity (ATM network)
        if txn_type == "ATM":
            baseline = float(state.get("baseline_txn_per_min") or 2.0)
            recent = db.recent_transaction_count(ts - timedelta(seconds=60), "ATM")
            if txn.get("txn_id"):
                # count includes current row if already inserted
                pass
            if recent >= max(3, int(3 * baseline)):
                _add_alert(
                    fired,
                    "R5",
                    txn,
                    f"{recent} ATM txns/min vs baseline {baseline:.1f} (3× threshold {3 * baseline:.1f}).",
                )

        # R6 — SWIFT above INR 1 crore
        if txn_type == "SWIFT" and amount >= R1_CRORE:
            _add_alert(fired, "R6", txn, f"transfer amount {amount:.2f} >= INR 1 crore threshold.")

        if persist_alerts and fired:
            start = db.next_alert_number()
            payload = []
            for i, alert in enumerate(fired):
                payload.append(
                    {
                        "alert_id": f"ALRT-{start + i:06d}",
                        "timestamp": alert["timestamp"],
                        "severity": alert["severity"],
                        "rule_id": alert["rule_id"],
                        "rule_name": alert["rule_name"],
                        "message": alert["message"],
                        "txn_id": alert.get("txn_id"),
                        "acknowledged": 0,
                    }
                )
            db.insert_alerts_bulk(payload)
            for alert, saved in zip(fired, payload):
                alert["alert_id"] = saved["alert_id"]
            from core.incident_response import on_alerts_fired

            on_alerts_fired(fired)
    except db.DatabaseError:
        # Detection must not crash the demo; return whatever we have.
        return fired
    return fired


def risk_from_alerts(alerts: List[Dict[str, Any]], txn: Dict[str, Any]) -> Tuple[int, str]:
    """Collapse fired rules into a 0–100 risk score and a human-readable reason string."""
    if not alerts:
        if txn.get("status") == "SUCCESS":
            return 5, "No detection rules fired — appears legitimate."
        if txn.get("status") == "DECLINED":
            return 15, "Declined by core banking; no fraud pattern."
        if txn.get("status") == "BLOCKED":
            return 40, txn.get("block_reason") or "Blocked by containment / security controls."
        return 10, "No detection rules fired."

    score = 0
    for a in alerts:
        if a["severity"] == "CRITICAL":
            score += 35
        elif a["severity"] == "HIGH":
            score += 20
        else:
            score += 10
    score = min(100, score)
    reason = " | ".join(f"{a['rule_id']}:{a['rule_name']}" for a in alerts)
    return score, reason


def evaluate_rules(
    txn: Dict[str, Any],
    card_rows: List[Dict[str, Any]],
    recent_atm_count: int,
    baseline: float,
) -> List[Dict[str, Any]]:
    """Apply R1–R6 to one row using caller-supplied windows (no extra SQL)."""
    fired: List[Dict[str, Any]] = []
    amount = float(txn.get("amount") or 0)
    balance_before = float(txn.get("balance_before") or 0)
    card = str(txn.get("card") or "")
    country = txn.get("country")
    ts = str(txn.get("timestamp") or "")
    txn_type = str(txn.get("txn_type") or "ATM")

    if txn_type == "ATM" and amount > balance_before:
        _add_alert(fired, "R1", txn, f"requested {amount:.2f} but available balance was {balance_before:.2f}.")

    if card:
        cutoff_60 = db.iso(db.parse_iso(ts) - timedelta(seconds=60)) if ts else ts
        count = sum(
            1
            for r in card_rows
            if str(r.get("timestamp") or "") >= cutoff_60 and r.get("txn_type") == "ATM"
        )
        if txn.get("txn_id") and not any(r.get("txn_id") == txn.get("txn_id") for r in card_rows):
            count += 1
        if count > 10:
            _add_alert(fired, "R2", txn, f"{count} transactions for {card} in 60 seconds.")

    if card and country:
        cutoff_30 = db.iso(db.parse_iso(ts) - timedelta(minutes=30)) if ts else ts
        countries = {
            r.get("country")
            for r in card_rows
            if r.get("country") and str(r.get("timestamp") or "") >= cutoff_30
        }
        countries.add(country)
        if len(countries) >= 2:
            joined = ", ".join(sorted(str(c) for c in countries))
            _add_alert(fired, "R3", txn, f"countries observed: {joined}.")

    core_d = str(txn.get("core_decision") or "")
    switch_d = str(txn.get("switch_decision") or "")
    if core_d and switch_d and core_d != switch_d and switch_d != "BLOCKED":
        _add_alert(fired, "R4", txn, f"core={core_d} vs switch={switch_d}.")

    if txn_type == "ATM" and recent_atm_count >= max(3, int(3 * baseline)):
        _add_alert(
            fired,
            "R5",
            txn,
            f"{recent_atm_count} ATM txns/min vs baseline {baseline:.1f} (3x threshold {3 * baseline:.1f}).",
        )

    if txn_type == "SWIFT" and amount >= R1_CRORE:
        _add_alert(fired, "R6", txn, f"transfer amount {amount:.2f} >= INR 1 crore threshold.")
    return fired


def evaluate_batch(
    records: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Score a cash-out wave in memory (order-preserving windows), then persist alerts."""
    if not records:
        return []
    baseline = float(state.get("baseline_txn_per_min") or 2.0)
    from collections import defaultdict

    new_ids = {r.get("txn_id") for r in records}
    by_card: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    seen: List[Dict[str, Any]] = []
    for row in history:
        if row.get("txn_id") in new_ids:
            continue
        seen.append(row)
        by_card[str(row.get("card") or "")].append(row)

    all_alerts: List[Dict[str, Any]] = []
    start = db.next_alert_number()
    n = start
    for rec in records:
        seen.append(rec)
        by_card[str(rec.get("card") or "")].append(rec)
        ts = str(rec.get("timestamp") or "")
        cutoff = db.iso(db.parse_iso(ts) - timedelta(seconds=60)) if ts else ts
        recent = sum(
            1 for row in seen if row.get("txn_type") == "ATM" and str(row.get("timestamp") or "") >= cutoff
        )
        fired = evaluate_rules(rec, by_card.get(str(rec.get("card") or ""), []), recent, baseline)
        score, reason = risk_from_alerts(fired, rec)
        rec["alerts"] = fired
        rec["risk_score"] = score
        rec["risk_reason"] = reason
        for alert in fired:
            all_alerts.append(
                {
                    "alert_id": f"ALRT-{n:06d}",
                    "timestamp": alert["timestamp"],
                    "severity": alert["severity"],
                    "rule_id": alert["rule_id"],
                    "rule_name": alert["rule_name"],
                    "message": alert["message"],
                    "txn_id": rec.get("txn_id"),
                    "acknowledged": 0,
                }
            )
            n += 1
    if all_alerts:
        db.insert_alerts_bulk(all_alerts)
    return all_alerts

