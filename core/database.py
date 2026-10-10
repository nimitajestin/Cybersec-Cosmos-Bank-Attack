"""SQLite store for transactions, alerts, and incident state."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from core.paths import db_path

# Serialise writers so Streamlit reruns cannot corrupt SQLite.
_LOCK = threading.Lock()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS simulation_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    switch_compromised INTEGER NOT NULL DEFAULT 0,
    switch_isolated INTEGER NOT NULL DEFAULT 0,
    swift_locked INTEGER NOT NULL DEFAULT 0,
    security_controls INTEGER NOT NULL DEFAULT 0,
    incident_declared INTEGER NOT NULL DEFAULT 0,
    cashout_wave INTEGER NOT NULL DEFAULT 0,
    baseline_txn_per_min REAL NOT NULL DEFAULT 2.0,
    legit_switch_hash TEXT NOT NULL DEFAULT '',
    live_switch_hash TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    card TEXT PRIMARY KEY,
    holder_name TEXT NOT NULL,
    available_balance REAL NOT NULL,
    original_balance REAL NOT NULL,
    country TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS atms (
    atm_id TEXT PRIMARY KEY,
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ONLINE'
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    atm_id TEXT,
    card TEXT NOT NULL,
    amount REAL NOT NULL,
    balance_before REAL NOT NULL,
    balance_after REAL NOT NULL,
    core_decision TEXT NOT NULL,
    switch_decision TEXT NOT NULL,
    atm_result TEXT NOT NULL,
    status TEXT NOT NULL,
    risk_score INTEGER NOT NULL DEFAULT 0,
    risk_reason TEXT NOT NULL DEFAULT '',
    country TEXT,
    txn_type TEXT NOT NULL DEFAULT 'ATM',
    is_simulated_fraud INTEGER NOT NULL DEFAULT 0,
    attack_wave INTEGER NOT NULL DEFAULT 0,
    beneficiary TEXT,
    block_reason TEXT,
    source TEXT NOT NULL DEFAULT 'MANUAL'
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    severity TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    message TEXT NOT NULL,
    txn_id TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nist_stages (
    stage TEXT PRIMARY KEY,
    sort_order INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clock_label TEXT NOT NULL,
    event TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_txn_time ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_txn_card ON transactions(card);
CREATE INDEX IF NOT EXISTS idx_alert_time ON alerts(timestamp);
"""

NIST_STAGES = [
    ("Preparation", 1),
    ("Detection", 2),
    ("Analysis", 3),
    ("Containment", 4),
    ("Eradication", 5),
    ("Recovery", 6),
    ("Lessons Learned", 7),
]

# Seeded cardholders / ATMs.
SEED_ACCOUNTS = [
    ("XXXX-XXXX-1001", "A. Kulkarni", 50000.0, "India"),
    ("XXXX-XXXX-2847", "S. Mehta", 12000.0, "India"),
    ("XXXX-XXXX-3391", "R. Iyer", 250000.0, "India"),
    ("XXXX-XXXX-4520", "N. Sharma", 8500.0, "India"),
    ("XXXX-XXXX-6677", "P. Deshmukh", 120000.0, "India"),
    ("XXXX-XXXX-8901", "K. Banerjee", 3200.0, "India"),
    ("XXXX-XXXX-SW01", "Nostro Settlement Desk", 500000000.0, "India"),
]

SEED_ATMS = [
    ("IN-PUN-001", "India", "Pune"),
    ("IN-MUM-014", "India", "Mumbai"),
    ("AE-DXB-003", "UAE", "Dubai"),
    ("AE-AUH-007", "UAE", "Abu Dhabi"),
    ("TH-BKK-021", "Thailand", "Bangkok"),
    ("TH-CHM-009", "Thailand", "Chiang Mai"),
    ("MY-KUL-011", "Malaysia", "Kuala Lumpur"),
    ("MY-JHB-004", "Malaysia", "Johor Bahru"),
]


class DatabaseError(RuntimeError):
    """Raised when a persistence call fails; pages convert this to a UI warning."""


def utc_now() -> datetime:
    """Canonical clock for logs so timeline reconstruction is timezone-safe."""
    return datetime.now(timezone.utc)


def iso(dt: Optional[datetime] = None) -> str:
    """Serialize timestamps to ISO-8601 for SQLite storage and display."""
    return (dt or utc_now()).strftime("%Y-%m-%d %H:%M:%S")


def parse_iso(value: str) -> datetime:
    """Parse stored timestamps back to aware UTC datetimes."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = datetime.fromisoformat(value.replace("Z", ""))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@contextmanager
def get_conn():
    """Open a WAL-mode SQLite connection with Row access (defense: fail closed)."""
    path = db_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"Database error: {exc}") from exc
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_db() -> None:
    """Create schema and seed data so the app never starts empty."""
    with _LOCK:
        try:
            with get_conn() as conn:
                conn.executescript(SCHEMA_SQL)
                _ensure_state(conn)
                _ensure_nist(conn)
                _seed_master_data(conn)
                if _count(conn, "transactions") == 0:
                    _seed_baseline_transactions(conn)
                if _count(conn, "timeline_events") == 0:
                    _insert_timeline(
                        conn,
                        "10:00",
                        "Normal operations — payment switch integrity OK, ATM network online.",
                        "normal",
                    )
        except DatabaseError:
            raise
        except Exception as exc:
            raise DatabaseError(f"Could not initialise the simulation database: {exc}") from exc


def _count(conn: sqlite3.Connection, table: str) -> int:
    """Count rows in a known table (table name is hardcoded by callers)."""
    row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
    return int(row["c"] if row else 0)


def _ensure_state(conn: sqlite3.Connection) -> None:
    """Guarantee the singleton simulation_state row exists (idempotent)."""
    row = conn.execute("SELECT id FROM simulation_state WHERE id = 1").fetchone()
    if row:
        return
    from core.constants import LEGIT_SWITCH_HASH

    conn.execute(
        """
        INSERT INTO simulation_state (
            id, switch_compromised, switch_isolated, swift_locked, security_controls,
            incident_declared, cashout_wave, baseline_txn_per_min,
            legit_switch_hash, live_switch_hash, updated_at
        ) VALUES (1, 0, 0, 0, 0, 0, 0, 2.0, ?, ?, ?)
        """,
        (LEGIT_SWITCH_HASH, LEGIT_SWITCH_HASH, iso()),
    )


def _ensure_nist(conn: sqlite3.Connection) -> None:
    """Seed the NIST SP 800-61 response checklist; Preparation starts complete."""
    for name, order in NIST_STAGES:
        existing = conn.execute(
            "SELECT stage FROM nist_stages WHERE stage = ?", (name,)
        ).fetchone()
        if existing:
            continue
        done = 1 if name == "Preparation" else 0
        done_at = iso() if done else None
        conn.execute(
            "INSERT INTO nist_stages (stage, sort_order, completed, completed_at) VALUES (?,?,?,?)",
            (name, order, done, done_at),
        )


def _seed_master_data(conn: sqlite3.Connection) -> None:
    """Load cards and ATM locations used throughout the demo."""
    for card, holder, balance, country in SEED_ACCOUNTS:
        conn.execute(
            """
            INSERT OR IGNORE INTO accounts
                (card, holder_name, available_balance, original_balance, country, status)
            VALUES (?,?,?,?,?, 'ACTIVE')
            """,
            (card, holder, balance, balance, country),
        )
    for atm_id, country, city in SEED_ATMS:
        conn.execute(
            """
            INSERT OR IGNORE INTO atms (atm_id, country, city, status)
            VALUES (?,?,?, 'ONLINE')
            """,
            (atm_id, country, city),
        )
    conn.execute("UPDATE accounts SET holder_name = REPLACE(holder_name, ' (fictional)', '')")


def _seed_baseline_transactions(conn: sqlite3.Connection) -> None:
    """Insert quiet legitimate traffic so velocity baselines are non-zero."""
    now = utc_now()
    # ~2 txn/min equivalent over a quiet hour (used by rule R5).
    samples = [
        ("XXXX-XXXX-1001", "IN-PUN-001", 2000.0, 40),
        ("XXXX-XXXX-2847", "IN-MUM-014", 500.0, 35),
        ("XXXX-XXXX-3391", "IN-PUN-001", 8000.0, 28),
        ("XXXX-XXXX-6677", "IN-MUM-014", 1500.0, 22),
        ("XXXX-XXXX-1001", "IN-PUN-001", 1000.0, 18),
        ("XXXX-XXXX-4520", "IN-PUN-001", 400.0, 14),
        ("XXXX-XXXX-3391", "IN-MUM-014", 2500.0, 10),
        ("XXXX-XXXX-6677", "IN-PUN-001", 700.0, 7),
        ("XXXX-XXXX-2847", "IN-PUN-001", 300.0, 4),
        ("XXXX-XXXX-1001", "IN-MUM-014", 1200.0, 2),
    ]
    for idx, (card, atm_id, amount, minutes_ago) in enumerate(samples, start=1):
        acc = conn.execute("SELECT * FROM accounts WHERE card = ?", (card,)).fetchone()
        atm = conn.execute("SELECT * FROM atms WHERE atm_id = ?", (atm_id,)).fetchone()
        ts = iso(now - timedelta(minutes=minutes_ago))
        bal = float(acc["available_balance"])
        txn_id = f"TXN-{idx:06d}"
        conn.execute(
            """
            INSERT INTO transactions (
                txn_id, timestamp, atm_id, card, amount, balance_before, balance_after,
                core_decision, switch_decision, atm_result, status, risk_score, risk_reason,
                country, txn_type, is_simulated_fraud, attack_wave, beneficiary, block_reason, source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                txn_id,
                ts,
                atm_id,
                card,
                amount,
                bal,
                bal,  # seed rows are historical authorisations already "settled"
                "APPROVED",
                "APPROVED",
                "CASH_DISPENSED",
                "SUCCESS",
                5,
                "Baseline legitimate traffic",
                atm["country"],
                "ATM",
                0,
                0,
                None,
                None,
                "SEED",
            ),
        )


def _insert_timeline(conn: sqlite3.Connection, clock: str, event: str, category: str) -> None:
    """Append one attack-timeline row (idempotent-ish via exact event text)."""
    conn.execute(
        """
        INSERT INTO timeline_events (clock_label, event, category, created_at)
        VALUES (?,?,?,?)
        """,
        (clock, event, category, iso()),
    )


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """Convert a sqlite3.Row into a plain dict for Streamlit / Plotly."""
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    """Convert a query result set into JSON-serialisable dictionaries."""
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def get_state() -> Dict[str, Any]:
    """Read the singleton simulation flags (compromise, isolation, controls)."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM simulation_state WHERE id = 1").fetchone()
        data = row_to_dict(row) or {}
    return data


def update_state(**fields: Any) -> Dict[str, Any]:
    """Patch simulation flags; unknown keys are ignored (input validation)."""
    allowed = {
        "switch_compromised",
        "switch_isolated",
        "swift_locked",
        "security_controls",
        "incident_declared",
        "cashout_wave",
        "baseline_txn_per_min",
        "legit_switch_hash",
        "live_switch_hash",
    }
    payload = {k: v for k, v in fields.items() if k in allowed}
    if not payload:
        return get_state()
    payload["updated_at"] = iso()
    assignments = ", ".join(f"{k} = ?" for k in payload)
    values = list(payload.values())
    with _LOCK:
        with get_conn() as conn:
            conn.execute(f"UPDATE simulation_state SET {assignments} WHERE id = 1", values)
    return get_state()


def get_accounts(include_swift: bool = False) -> List[Dict[str, Any]]:
    """List card accounts shown in ATM / investigation screens."""
    init_db()
    with get_conn() as conn:
        if include_swift:
            rows = conn.execute("SELECT * FROM accounts ORDER BY card").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE card NOT LIKE '%SW01' ORDER BY card"
            ).fetchall()
    return rows_to_dicts(rows)


def get_account(card: str) -> Optional[Dict[str, Any]]:
    """Look up one account by masked card number."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE card = ?", (card,)).fetchone()
    return row_to_dict(row)


def set_balance(card: str, new_balance: float) -> None:
    """Update available balance after a *legitimate* core-approved debit."""
    with _LOCK:
        with get_conn() as conn:
            conn.execute(
                "UPDATE accounts SET available_balance = ? WHERE card = ?",
                (float(new_balance), card),
            )


def restore_balances() -> None:
    """Reset every account to its seeded original_balance (recovery / RESET)."""
    with _LOCK:
        with get_conn() as conn:
            conn.execute("UPDATE accounts SET available_balance = original_balance, status = 'ACTIVE'")


def get_atms() -> List[Dict[str, Any]]:
    """List ATM endpoints used in the cash-out simulation."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM atms ORDER BY country, atm_id").fetchall()
    return rows_to_dicts(rows)


def get_atm(atm_id: str) -> Optional[Dict[str, Any]]:
    """Look up one ATM by ID."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM atms WHERE atm_id = ?", (atm_id,)).fetchone()
    return row_to_dict(row)


def next_id(prefix: str, table: str, column: str) -> str:
    """Allocate the next human-readable TXN-/ALRT- identifier."""
    init_db()
    with get_conn() as conn:
        row = conn.execute(f"SELECT {column} AS ident FROM {table} ORDER BY {column} DESC LIMIT 1").fetchone()
    if not row or not row["ident"]:
        return f"{prefix}-000001"
    last = str(row["ident"]).split("-")[-1]
    try:
        n = int(last) + 1
    except ValueError:
        n = 1
    return f"{prefix}-{n:06d}"


def insert_transaction(record: Dict[str, Any]) -> Dict[str, Any]:
    """Persist one ATM or SWIFT simulation event for later forensics."""
    cols = [
        "txn_id",
        "timestamp",
        "atm_id",
        "card",
        "amount",
        "balance_before",
        "balance_after",
        "core_decision",
        "switch_decision",
        "atm_result",
        "status",
        "risk_score",
        "risk_reason",
        "country",
        "txn_type",
        "is_simulated_fraud",
        "attack_wave",
        "beneficiary",
        "block_reason",
        "source",
    ]
    values = [record.get(c) for c in cols]
    with _LOCK:
        with get_conn() as conn:
            conn.execute(
                f"INSERT INTO transactions ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                values,
            )
    return record


def insert_transactions_bulk(records: List[Dict[str, Any]]) -> None:
    """Batch-insert cash-out bursts without opening a connection per row."""
    if not records:
        return
    cols = [
        "txn_id",
        "timestamp",
        "atm_id",
        "card",
        "amount",
        "balance_before",
        "balance_after",
        "core_decision",
        "switch_decision",
        "atm_result",
        "status",
        "risk_score",
        "risk_reason",
        "country",
        "txn_type",
        "is_simulated_fraud",
        "attack_wave",
        "beneficiary",
        "block_reason",
        "source",
    ]
    with _LOCK:
        with get_conn() as conn:
            conn.executemany(
                f"INSERT INTO transactions ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                [[r.get(c) for c in cols] for r in records],
            )


def insert_alerts_bulk(records: List[Dict[str, Any]]) -> None:
    """Batch-insert SOC alerts generated by the rule engine."""
    if not records:
        return
    cols = [
        "alert_id",
        "timestamp",
        "severity",
        "rule_id",
        "rule_name",
        "message",
        "txn_id",
        "acknowledged",
    ]
    with _LOCK:
        with get_conn() as conn:
            conn.executemany(
                f"INSERT INTO alerts ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                [[r.get(c) for c in cols] for r in records],
            )


def list_transactions(
    txn_type: Optional[str] = None,
    limit: int = 500,
    wave: Optional[int] = None,
    fraud_only: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Query the transaction ledger with optional filters for each page."""
    init_db()
    clauses = []
    params: List[Any] = []
    if txn_type:
        clauses.append("txn_type = ?")
        params.append(txn_type)
    if wave is not None:
        clauses.append("attack_wave = ?")
        params.append(wave)
    if fraud_only is True:
        clauses.append("is_simulated_fraud = 1")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM transactions {where} ORDER BY timestamp DESC, txn_id DESC LIMIT ?"
    params.append(int(limit))
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_dicts(rows)


def get_transaction(txn_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single transaction for the investigation drill-down view."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE txn_id = ?", (txn_id,)).fetchone()
    return row_to_dict(row)


def transactions_for_card_since(card: str, since: datetime) -> List[Dict[str, Any]]:
    """Support velocity and geo-anomaly rules with a per-card time window."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM transactions
            WHERE card = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (card, iso(since)),
        ).fetchall()
    return rows_to_dicts(rows)


def recent_transaction_count(since: datetime, txn_type: str = "ATM") -> int:
    """Count ATM (or SWIFT) events after a cutoff — used by velocity spike R5."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE txn_type = ? AND timestamp >= ?",
            (txn_type, iso(since)),
        ).fetchone()
    return int(row["c"] if row else 0)


def list_alerts(limit: int = 400) -> List[Dict[str, Any]]:
    """Return the SOC alert feed, newest first."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY timestamp DESC, alert_id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return rows_to_dicts(rows)


def alerts_for_txn(txn_id: str) -> List[Dict[str, Any]]:
    """Attach fired rules to a transaction on the investigation page."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE txn_id = ? ORDER BY alert_id",
            (txn_id,),
        ).fetchall()
    return rows_to_dicts(rows)


def alert_counts() -> Dict[str, int]:
    """Aggregate alert volume by severity for the SOC dashboard KPI cards."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT severity, COUNT(*) AS c FROM alerts GROUP BY severity"
        ).fetchall()
    out = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in rows:
        out[str(r["severity"])] = int(r["c"])
    return out


def next_alert_number() -> int:
    """Return the integer portion of the next alert id (for bulk generation)."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT alert_id FROM alerts ORDER BY alert_id DESC LIMIT 1").fetchone()
    if not row:
        return 1
    try:
        return int(str(row["alert_id"]).split("-")[-1]) + 1
    except ValueError:
        return 1


def next_txn_number() -> int:
    """Return the integer portion of the next transaction id (for bulk generation)."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT txn_id FROM transactions ORDER BY txn_id DESC LIMIT 1").fetchone()
    if not row:
        return 1
    try:
        return int(str(row["txn_id"]).split("-")[-1]) + 1
    except ValueError:
        return 1


def add_timeline(clock_label: str, event: str, category: str) -> None:
    """Record a labelled demo-clock event (10:00 / 10:02 / 10:03 …)."""
    with _LOCK:
        with get_conn() as conn:
            dup = conn.execute(
                "SELECT id FROM timeline_events WHERE clock_label = ? AND event = ?",
                (clock_label, event),
            ).fetchone()
            if dup:
                return
            _insert_timeline(conn, clock_label, event, category)


def list_timeline() -> List[Dict[str, Any]]:
    """Return the attack timeline in demo-clock order for the SOC panel."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM timeline_events ORDER BY clock_label ASC, id ASC"
        ).fetchall()
    return rows_to_dicts(rows)


def get_nist() -> List[Dict[str, Any]]:
    """Return NIST SP 800-61 stages with completion flags for the checklist."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM nist_stages ORDER BY sort_order").fetchall()
    return rows_to_dicts(rows)


def complete_nist(stage: str) -> None:
    """Tick a NIST lifecycle stage when the corresponding demo action occurs."""
    with _LOCK:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE nist_stages
                SET completed = 1, completed_at = ?
                WHERE stage = ? AND completed = 0
                """,
                (iso(), stage),
            )


def reset_operational_data() -> None:
    """Wipe transactions/alerts/timeline and restore balances (RESET SIMULATION)."""
    from core.constants import LEGIT_SWITCH_HASH

    with _LOCK:
        with get_conn() as conn:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM alerts")
            conn.execute("DELETE FROM timeline_events")
            conn.execute("UPDATE accounts SET available_balance = original_balance, status = 'ACTIVE'")
            conn.execute(
                """
                UPDATE simulation_state SET
                    switch_compromised = 0,
                    switch_isolated = 0,
                    swift_locked = 0,
                    security_controls = 0,
                    incident_declared = 0,
                    cashout_wave = 0,
                    live_switch_hash = ?,
                    updated_at = ?
                WHERE id = 1
                """,
                (LEGIT_SWITCH_HASH, iso()),
            )
            conn.execute("UPDATE nist_stages SET completed = 0, completed_at = NULL")
            conn.execute(
                "UPDATE nist_stages SET completed = 1, completed_at = ? WHERE stage = 'Preparation'",
                (iso(),),
            )
            _seed_baseline_transactions(conn)
            _insert_timeline(
                conn,
                "10:00",
                "Normal operations — payment switch integrity OK, ATM network online.",
                "normal",
            )


def loss_by_country(wave: Optional[int] = None) -> List[Dict[str, Any]]:
    """Sum simulated cash dispensed on mismatched/fraud ATM rows, grouped by country."""
    init_db()
    clause = ""
    params: List[Any] = []
    if wave is not None:
        clause = "AND attack_wave = ?"
        params.append(wave)
    sql = f"""
        SELECT country, COUNT(*) AS txn_count,
               SUM(CASE WHEN atm_result = 'CASH_DISPENSED' AND (
                        is_simulated_fraud = 1 OR core_decision != switch_decision
                    ) THEN amount ELSE 0 END) AS loss
        FROM transactions
        WHERE txn_type = 'ATM' {clause}
        GROUP BY country
        ORDER BY loss DESC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_dicts(rows)


def volume_over_time(wave: Optional[int] = None) -> List[Dict[str, Any]]:
    """Bucket ATM volume by timestamp for the cash-out Plotly line chart."""
    init_db()
    clause = ""
    params: List[Any] = []
    if wave is not None:
        clause = "AND attack_wave = ?"
        params.append(wave)
    sql = f"""
        SELECT timestamp, COUNT(*) AS txn_count, SUM(amount) AS total_amount
        FROM transactions
        WHERE txn_type = 'ATM' AND source != 'SEED' {clause}
        GROUP BY timestamp
        ORDER BY timestamp ASC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return rows_to_dicts(rows)


def wave_loss_summary() -> List[Dict[str, Any]]:
    """Compare simulated loss before vs after ENABLE SECURITY CONTROLS."""
    init_db()
    sql = """
        SELECT attack_wave AS wave,
               COUNT(*) AS txn_count,
               SUM(CASE WHEN atm_result = 'CASH_DISPENSED' AND is_simulated_fraud = 1
                        THEN amount ELSE 0 END) AS loss,
               SUM(CASE WHEN status = 'BLOCKED' THEN 1 ELSE 0 END) AS blocked
        FROM transactions
        WHERE attack_wave > 0 AND txn_type = 'ATM'
        GROUP BY attack_wave
        ORDER BY attack_wave
    """
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return rows_to_dicts(rows)


def atm_vs_swift_stats() -> Dict[str, Any]:
    """Build the academic comparison table: high-volume ATM vs high-value SWIFT."""
    init_db()
    with get_conn() as conn:
        atm = conn.execute(
            """
            SELECT COUNT(*) AS volume,
                   COALESCE(SUM(amount),0) AS value,
                   COALESCE(SUM(CASE WHEN is_simulated_fraud = 1 AND atm_result = 'CASH_DISPENSED'
                                     THEN amount ELSE 0 END),0) AS fraud_value
            FROM transactions WHERE txn_type = 'ATM' AND source != 'SEED'
            """
        ).fetchone()
        swift = conn.execute(
            """
            SELECT COUNT(*) AS volume,
                   COALESCE(SUM(amount),0) AS value,
                   COALESCE(SUM(CASE WHEN is_simulated_fraud = 1 AND status = 'UNAUTHORIZED'
                                     THEN amount ELSE 0 END),0) AS fraud_value
            FROM transactions WHERE txn_type = 'SWIFT'
            """
        ).fetchone()
    return {"atm": row_to_dict(atm), "swift": row_to_dict(swift)}
