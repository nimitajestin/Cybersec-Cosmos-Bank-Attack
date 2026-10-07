"""
Shared fictional constants for the Cosmos Bank SOC educational simulation.

Security concept: File Integrity Monitoring (FIM) compares a known-good hash
of a payment-switch binary against the live file. We hash two *dummy strings*
with SHA-256 — never a real executable and never a real bank system.
"""

from __future__ import annotations

import hashlib

# Dummy "binaries" — plain UTF-8 blobs, not PE/ELF malware.
LEGIT_SWITCH_BLOB = (
    b"COSMOS-PAYMENT-SWITCH-SIM v2.4.1 | signed-ok | auth-forward-to-core | "
    b"EDUCATIONAL-FICTIONAL-FILE | no-real-code"
)
TAMPERED_SWITCH_BLOB = (
    b"COSMOS-PAYMENT-SWITCH-SIM v2.4.1 | TAMPERED | override-core-decline | "
    b"EDUCATIONAL-FICTIONAL-FILE | no-real-code"
)

LEGIT_SWITCH_HASH = hashlib.sha256(LEGIT_SWITCH_BLOB).hexdigest()
TAMPERED_SWITCH_HASH = hashlib.sha256(TAMPERED_SWITCH_BLOB).hexdigest()

# Academic scale note shown on cash-out and SOC pages.
SCALE_DISCLAIMER = (
    "Simulation scale: ₹1 lakh = ₹1 crore in the historical incident. "
    "Total fictional loss shown, not real amounts."
)

DISCLAIMER = (
    "EDUCATIONAL SIMULATION — All banks, cards, amounts and transactions are fictional."
)

# SWIFT beneficiary is explicitly labelled fictional.
SWIFT_BENEFICIARY = "Hong Kong Bank (fictional) — A/C HK-FICT-998877"
SWIFT_AMOUNT = 25_000_000.0  # ₹2.5 crore simulated (scaled)

R1_CRORE = 10_000_000.0  # ₹1 crore threshold for rule R6
