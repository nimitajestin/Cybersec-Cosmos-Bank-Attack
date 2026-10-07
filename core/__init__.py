"""
Cosmos Bank SOC Simulation — core package.

Educational, fully offline banking-fraud *simulation* (no real networks,
malware, or payment-system APIs). Modules map to the demo architecture:

- database.py          SQLite persistence and auto-seed
- bank_simulator.py    ATM / Payment Switch / Core Banking
- attack_engine.py     Simulated compromise, cash-out, SWIFT fraud
- detection_engine.py  Deterministic SOC detection rules R1–R6
- incident_response.py NIST lifecycle + containment actions
- ui.py                Shared Streamlit chrome (disclaimer, theme)
- diagram.py           Offline architecture diagram renderer
- paths.py             Project-root resolution (dev + PyInstaller)
"""
