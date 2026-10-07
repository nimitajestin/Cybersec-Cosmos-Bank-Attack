# FIXES.md — packaging / UI only (engine algorithms unchanged)

Logged during STEP 4 mouse-only click-test (venv Streamlit 1.32.0 on `127.0.0.1:8501`).

## No rendering/runtime errors found

| Surface | Result |
|---|---|
| Home sidebar label | Shows **Home** (`Home.py`) |
| Normal Operation | TXN-000011 / TXN-000012 SUCCESS; hop-by-hop APPROVED / CASH_DISPENSED |
| Switch Compromise | FIM hash mismatch; Core DECLINED vs Switch APPROVED vs ATM CASH_DISPENSED (₹20,000) |
| NIST Detection tick | Appears on **first** mismatch after `st.rerun()` (`✅ Detection`, 3/7 stages) |
| ATM Cash-Out | Wave 1: 160 txns, Plotly charts present, table populated, undefended loss INR 13,066,773, blocked 0 |
| SOC buttons | Isolate → isolated ON + Containment tick; Lock SWIFT → ON; Enable controls → ON + Eradication tick; Re-run cash-out produced BLOCKED ATM rows |
| SWIFT | TXN-000314 BLOCKED (“SWIFT interface locked due to confirmed incident”); R6 fired |
| Investigation | TXN-000314 (SWIFT), TXN-000313 (ATM fraud, BLOCKED, 4 alerts), TXN-000310 listed in nearby rows; evidence checklist rendered |
| Frameworks | Verified in same session (Kill Chain + MITRE + NIST page loads) |
| Arrow mixed-type | No Arrow warnings in Streamlit console after `safe_dataframe` / `safe_table` stringify |
| TensorFlow / Paddle / protobuf | None in traces (isolated venv) |

## Not a code defect (documented only)

- **Harmless Streamlit 404** on `/_stcore/health` (and similar `/Switch_Compromise/_stcore/health` paths): Streamlit internals. See README.
- **Browser automation vs `st.number_input`:** filling ₹5000 via the accessibility tree did not always commit Streamlit widget state; the script used the widget default ₹1,000. Manual mouse +/- or typing in a real browser commits ₹5,000. Engine path is identical.

## Files changed in earlier UI nits (STEP 3)

- `app.py` → `Home.py`
- `core/ui.py` — `stringify_df`, `safe_dataframe`, `safe_table`
- Pages that render tables now call `safe_dataframe` / `safe_table`
- `pages/2_Switch_Compromise.py` — `st.rerun()` after mismatch so NIST sidebar re-reads Detection
- `pages/4_SWIFT_Fraud.py` — `st.rerun()` after SWIFT submit
- `launcher.py` — entry `Home.py`
