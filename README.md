# Cosmos Bank Cyber Attack Simulation & SOC Response System

**EDUCATIONAL SIMULATION — All banks, cards, amounts and transactions are fictional.**

Offline academic desktop demo of a **payment-switch compromise** leading to **ATM cash-out** and **SWIFT fraud**, with **rule-based SOC detection**, **NIST SP 800-61 containment**, and **defensive controls**. Built for a Cyber Security college project.

There is **no real malware**, **no real banking API**, and **no real network attack**. The “switch compromise” is a local SQLite boolean plus a SHA-256 of two dummy strings. Cash-out is a burst of fictional ledger rows.

**Repository:** [https://github.com/nimitajestin/Cybersec-Cosmos-Bank-Attack](https://github.com/nimitajestin/Cybersec-Cosmos-Bank-Attack)

---

## Disclaimer

EDUCATIONAL SIMULATION — All banks, cards, amounts and transactions are fictional. Runtime is **100% offline**. Do not point this at a real bank, card network, or SWIFT endpoint.

---

## Case-study summary (Cosmos Bank, Pune, 2018)

In August 2018, **Cosmos Co-operative Bank (Pune)** was publicly reported to have suffered a cyber incident involving:

1. Compromise of the **card payment switch** (authorisations no longer faithfully reflecting core banking).
2. Coordinated **ATM cash-out** from terminals in multiple countries.
3. **Fraudulent SWIFT** payment messages moving a large value.

Reported losses were on the order of **₹90+ crore**. This lab **does not reconstruct malware, exploits, or live SWIFT/ISO-8583 traffic**. It teaches the *control failures* using **scaled fictional rupees**:

> Simulation scale: ₹1 lakh = ₹1 crore in the historical incident. Total fictional loss shown, not real amounts.

---

## Architecture

See the shipped diagram: [`assets/architecture.png`](assets/architecture.png) (also generated on first Home load with matplotlib; no Graphviz, no internet).

```
                    EDUCATIONAL / OFFLINE ONLY
  +-----------+     +---------------------+     +----------------+
  | ATM net   | --> | Payment Switch      | --> | Core Banking   |
  | IN UAE TH |     | + FIM (SHA-256)     |     | APPROVE/DECLINE|
  | MY (fake) | <-- | may OVERRIDE core   | <-- | SQLite ledger  |
  +-----------+     +----------+----------+     +--------+-------+
                               |                         |
                               v                         v
                    +------------------+        +----------------+
                    | SWIFT gateway    |        | SOC R1-R6      |
                    | (fictional msgs) |        | NIST response  |
                    +------------------+        +----------------+
                               |                         |
                               +-----> Streamlit console <-----+
```

**Trust boundary:** the payment switch. If it stops copying the core decision, ATMs can dispense cash against a **DECLINED** authorisation.

---

## Prerequisites

- **Python 3.10+ only** (tested on Windows 10/11, Python 3.11).
- No API keys, cloud accounts, or paid libraries.
- Use a **project venv**. Do not mix this demo with a global Python that has TensorFlow / Paddle (protobuf clashes).

---

## How to run (primary path)

```bat
cd Cybersec-Cosmos-Bank-Attack
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run Home.py
```

The browser opens on `http://127.0.0.1:8501`. SQLite file `cosmos_soc.db` is created beside `Home.py` on first run (auto-seed).

### Live demo path (mouse only)

1. **Normal Operation** — submit a small withdrawal (below balance) → all hops APPROVED.
2. **Switch Compromise** — **SIMULATE SWITCH COMPROMISE** → FIM ❌ violation → send an **over-limit** withdrawal → Core **DECLINED** / Switch **APPROVED** / ATM **CASH_DISPENSED**. Sidebar **NIST Detection** ticks on that first mismatch.
3. **ATM Cash-Out** — **START ATM CASH-OUT** (100–300 fictional txns). Charts and table fill.
4. **SOC Dashboard** — coloured alerts (R1–R6), 10:00–10:09 timeline.
5. **ISOLATE PAYMENT SWITCH** / **LOCK SWIFT INTERFACE**.
6. **ENABLE SECURITY CONTROLS** then **RE-RUN SAME CASH-OUT** — fraud **BLOCKED**.
7. **SWIFT Fraud**, **Investigation**, **Frameworks**.

### Harmless Streamlit 404s

Messages such as `404` on `/_stcore/health` (including under page paths like `/Switch_Compromise/_stcore/health`) are **harmless Streamlit internals**. They are not application bugs and do not affect the demo.

---

## How to build the Windows exe (optional)

Primary demo path is `streamlit run Home.py`. The exe is optional packaging.

1. Close heavy apps (and any previous PyInstaller run).
2. Double-click `build.bat`, or from the venv:

```bat
pyinstaller --noconfirm --clean --onedir --windowed --name CosmosBankDemo ^
  --hidden-import plotly --collect-data plotly --collect-data streamlit ^
  --add-data "core;core" --add-data "pages;pages" --add-data "assets;assets" ^
  Home.py
```

A 6.22.3 `--onedir` build **does complete** (`dist\CosmosBankDemo\CosmosBankDemo.exe`). Launching that exe does **not** start the Streamlit server (`Home.py` is a page script, not `streamlit run`). **Do not ship a broken exe.** Use `streamlit run Home.py` for the viva.

**Do not** use `--collect-all plotly` (can raise WinError 1450). Pin `pyinstaller==6.22.3` (older 6.11.1 hooks can fail with `is_py315`). The `dist/` folder is ~236 MB — leave it out of a ≤100 MB zip.

`build_exe.bat` is a leftover helper; **`build.bat` is the one-click command**.

---

## How to push to GitHub

Remote already used for this project:

`https://github.com/nimitajestin/Cybersec-Cosmos-Bank-Attack.git`

If you clone a fresh copy:

```bat
cd Cybersec-Cosmos-Bank-Attack
git init
git add Home.py launcher.py requirements.txt README.md FIXES.md build.bat sample_data.sql
git add core pages assets screenshots .streamlit .gitignore
git commit -m "Add Cosmos Bank SOC educational simulation (offline Streamlit demo)"
git branch -M main
git remote add origin https://github.com/nimitajestin/Cybersec-Cosmos-Bank-Attack.git
git push -u origin main
```

Do **not** commit `__pycache__`, `venv/`, `build/`, `dist/`, or `cosmos_soc.db`.

---

## Screenshots

Captured during the viva click-test:

| File | What it shows |
|---|---|
| [`screenshots/1_normal.png`](screenshots/1_normal.png) | Normal Operation — SUCCESS hop-by-hop (core / switch / ATM green) |
| [`screenshots/2_compromise_mismatch.png`](screenshots/2_compromise_mismatch.png) | Switch compromise — FIM violation + Core DECLINED / Switch APPROVED |
| [`screenshots/3_cashout_dashboard.png`](screenshots/3_cashout_dashboard.png) | ATM cash-out — live wave, charts, transaction table |
| [`screenshots/4_alerts_timeline.png`](screenshots/4_alerts_timeline.png) | SOC — CRITICAL/HIGH feed + attack timeline |
| [`screenshots/5_nist_containment.png`](screenshots/5_nist_containment.png) | Isolate + lock SWIFT + NIST containment ticks |
| [`screenshots/6_defense_blocked.png`](screenshots/6_defense_blocked.png) | Defense mode ON — cash-out wave blocked |

Also on disk: [`assets/architecture.png`](assets/architecture.png).

---

## Features mapped to the specification

| ID | Feature | Where |
|----|---------|--------|
| **F1** | Normal ATM transaction (ATM → switch → core → approve/decline → cash → new balance) logged to SQLite | `pages/1_Normal_Operation.py`, `core/bank_simulator.py` |
| **F2** | Simulated switch compromise toggle; core DECLINED vs switch APPROVED; SHA-256 FIM | `pages/2_Switch_Compromise.py`, `core/attack_engine.py` |
| **F3** | ATM cash-out 100–300 txns, IN/UAE/TH/MY, loss in ₹, scale disclaimer, Plotly charts | `pages/3_ATM_CashOut.py` |
| **F4** | Rule-based SOC R1–R6, coloured feed, severity counts, 10:00–10:09 timeline | `core/detection_engine.py`, `pages/5_SOC_Dashboard.py` |
| **F5** | Isolate switch, lock SWIFT, reset; NIST checklist; BLOCKED after isolation | `core/incident_response.py`, SOC page |
| **F6** | ENABLE SECURITY CONTROLS then replay cash-out; before/after loss | SOC page + Cash-Out wave chart |
| **F7** | SWIFT fraud tab (not mixed with ATM); HK Bank (fictional); volume vs value table | `pages/4_SWIFT_Fraud.py` |
| **F8** | Investigation drill-down + evidence checklist | `pages/6_Investigation.py` |
| **F9** | Kill Chain (unknown stages marked `?`) + MITRE T1657 / T1565 analytical mapping | `pages/7_Frameworks.py` |

---

## NIST + MITRE + Kill Chain (for the report)

### NIST SP 800-61r2 Computer Security Incident Handling

| Stage | How the demo implements it |
|---|---|
| Preparation | Seeded FIM baseline, rule catalogue, playbook UI |
| Detection | Deterministic R1–R6 alerts |
| Analysis | Investigation page + CRITICAL auto-tick |
| Containment | Isolate payment switch; lock SWIFT; fail closed |
| Eradication | Enable FIM + reconciliation + velocity + geo + SWIFT verify |
| Recovery | Restore known-good hash; RESET SIMULATION |
| Lessons Learned | Frameworks page (honest unknowns) |

### MITRE ATT&CK

- **T1657 Financial Theft** — evidence-based in the lab (cash-out + SWIFT value).
- **T1565 Data Manipulation** — **ANALYTICAL MAPPING — not publicly confirmed.**

### Cyber Kill Chain

Documented: **compromise**, **fraudulent approvals**, **ATM cash-out**, **SWIFT transfers**. Unknown (marked `?`): **Reconnaissance, Delivery, Exploitation**.

---

## Detection rules (R1–R6)

| Rule | Severity | Logic |
|---|---|---|
| R1 | CRITICAL | Withdrawal > available balance |
| R2 | HIGH | >10 transactions per card per minute |
| R3 | CRITICAL | Same card in 2+ countries within 30 minutes |
| R4 | CRITICAL | Switch decision ≠ core decision (override) |
| R5 | HIGH | ATM velocity ≥ 3× quiet-hour baseline |
| R6 | HIGH | SWIFT transfer ≥ ₹1 crore |

---

## Project tree

```
Cybersec-Cosmos-Bank-Attack/
├── Home.py
├── launcher.py
├── requirements.txt
├── README.md
├── FIXES.md
├── build.bat
├── sample_data.sql
├── core/
├── pages/
├── assets/architecture.png
├── screenshots/
└── .streamlit/config.toml
```

---

## Disclaimer (repeat on every screen)

EDUCATIONAL SIMULATION — All banks, cards, amounts and transactions are fictional.
