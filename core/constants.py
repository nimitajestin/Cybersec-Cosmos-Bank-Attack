"""Shared constants for the Cosmos Bank SOC demo."""

from __future__ import annotations

import hashlib

LEGIT_SWITCH_BLOB = b"COSMOS-PAYMENT-SWITCH v2.4.1 | signed-ok | auth-forward-to-core"
TAMPERED_SWITCH_BLOB = b"COSMOS-PAYMENT-SWITCH v2.4.1 | TAMPERED | override-core-decline"

LEGIT_SWITCH_HASH = hashlib.sha256(LEGIT_SWITCH_BLOB).hexdigest()
TAMPERED_SWITCH_HASH = hashlib.sha256(TAMPERED_SWITCH_BLOB).hexdigest()

SWIFT_BENEFICIARY = "Hong Kong Bank — A/C HK-998877"
SWIFT_AMOUNT = 25_000_000.0  # ₹2.5 crore in the demo ledger

R1_CRORE = 10_000_000.0  # ₹1 crore threshold for rule R6
