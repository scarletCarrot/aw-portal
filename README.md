# AW Client Report Portal

A small Flask app for a financial-planning firm: enter quarterly client balances → automatic
math → polished SACS (cashflow) and TCC (net worth) PDFs.

---

## Features

- **Authentication** — session-based login with hashed passwords (Werkzeug).
- **Multi-client management** — list, create, edit, delete clients. Each client carries a static profile (names, DOBs, account types, salary, expense budget, deductibles, trust property, liabilities).
- **Quarterly report data entry** — pre-populated form per client, sticky live-totals bar that recomputes as you type.
- **Automatic math** — the calc engine (`calc.py`) implements every rule from the discovery call verbatim, with the source quoted in each docstring and 7 passing assertion tests.
- **PDF generation** — SACS and TCC PDFs via Playwright (headless Chromium), so the same Jinja templates render identically in browser and in PDF.
- **Report history** — every generated report is snapshotted into SQLite; download any past report's PDFs from `/clients/<id>/history`.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Flask 3 | Lightweight, fast to iterate. |
| Database | SQLite | Six clients × quarterly reports = trivial volume. Zero ops. |
| Auth | Werkzeug session + password hash | No external deps. |
| Templates | Jinja2 | Same templates serve browser preview AND PDF render. |
| PDF render | **Playwright** (Chromium) | Pure pip + one CLI command. WeasyPrint requires GTK on Windows; Playwright works cross-platform with no system libs. |
| Frontend | HTML + a sprinkle of vanilla JS | Three-person internal tool — no framework needed. |

---

## Run it

### Windows (the path I actually tested)

```powershell
cd C:\Users\<you>\...\karen-test\aw-portal

# 1. Virtual env
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install Python deps
pip install -r requirements.txt

# 3. One-time: download the Chromium that Playwright drives
playwright install chromium

# 4. Run via the Flask CLI (Windows-friendly)
$env:FLASK_APP = "app.py"
flask run
```

Open <http://127.0.0.1:5000>.

### Linux / macOS / WSL

```bash
cd aw-portal
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python app.py
# open http://127.0.0.1:5000
```

### First-time setup

1. Open the app, click **Register**. The first registration is open (no existing users).
2. After the first user exists, registration requires an active session — i.e., a logged-in user has to register additional teammates. Simple invite gate; no email tokens.
3. After login, click **Seed demo client** on the empty clients page if you want to try the app with the sample data from the discovery call.

### Run the test suite

```bash
python test_calc.py
```

Expected: 7 `ok` lines and `All calculation tests passed.`

---

## Critical correctness rules (from the discovery call)

Every rule is in `calc.py` with a docstring quoting the transcript timestamp.

- **SACS Excess** = Inflow − Outflow.
- **SACS Private Reserve Target** = (6 × monthly expenses) + Σ(insurance deductibles).
- **TCC Non-Retirement Total** *excludes* the trust. *(Rebecca, ~24:28: "we do not add the trust in")*
- **TCC Grand Total Net Worth** = C1 Retirement + C2 Retirement + Non-Retirement + Trust. *(Rebecca, ~25:30)*
- **Liabilities** are summed **separately** and **never subtracted** from net worth. *(Rebecca, ~26:15: "we do not subtract liabilities from their net worth, they're just a separate box")*
- **Floor** is constant $1,000 per bank account.

Demo defaults are picked so you can verify by eye:

| Field | Value |
|---|---|
| Inflow | $15,000/mo |
| Outflow | $11,000/mo |
| Excess | **$4,000/mo** |
| Reserve Target | 6 × 11,000 + 1,000 + 2,000 + 1,000 = **$70,000** |
| C1 Retirement Total | 11,162.47 + 15,240.18 = **$26,402.65** |
| C2 Retirement Total | 88,500 + 22,100 + 41,250 = **$151,850.00** |
| Non-Retirement Total | 54,300 + 18,420 + 12,150 + 47,800 = **$132,670.00** |
| Trust | **$452,000.00** |
| Grand Total Net Worth | **$762,922.65** |
| Liabilities Total | 218,400 + 14,250 = **$232,650.00** *(separate)* |

---

## Project layout

```
aw-portal/
├── app.py                      # Flask routes
├── auth.py                     # Login / register / login_required
├── calc.py                     # Calculation engine (source of truth for math)
├── data.py                     # Reference / seed payload
├── db.py                       # SQLite connection + init + seed helpers
├── models.py                   # CRUD functions for clients, accounts, reports
├── schema.sql                  # Database schema
├── test_calc.py                # Assertion tests for every calc rule
├── requirements.txt
├── aw_portal.db                # Created on first run (gitignored)
├── templates/
│   ├── layout.html             # Base template (header, nav, flash messages)
│   ├── login.html
│   ├── register.html
│   ├── clients_list.html       # Multi-client list
│   ├── client_edit.html        # Used for both "new" and "edit"
│   ├── quarterly_form.html     # Per-client report data entry
│   ├── report_preview.html     # Post-submit page with PDF buttons
│   ├── history.html            # Past reports for a client
│   ├── sacs.html               # Same template renders in browser AND PDF
│   └── tcc.html
└── static/
    └── css/
        ├── portal.css
        └── report.css
```

---

## What I'd ship next

1. **PDF visual fidelity pass** to match Andrew's Canva layout pixel-by-pixel. Today's output is recognizably the same structure, not pixel-identical.
2. **Dropbox auto-save** of generated PDFs to per-client folders — Maryann asked for this (transcript ~41:23).
3. **"Use last value" in quarterly form** — when a client has prior reports, prefill the form from the most recent one instead of the static defaults.
4. **Canva export** — only if Andrew/Maryann actually want it after seeing the portal. Rebecca said "we don't want to do it in either [Canva or Word], ideally" (~13:48).
5. **V2 data-pull integrations** in this order, by reliability and compliance friction: Plaid → PreciseFP → Zillow → RightCapital. Schwab last, with very careful auth scoping per Rebecca's compliance constraint.
6. **Client onboarding form** — the second "Lego brick" Zaki proposed (~43:36).

---
## Sources cited from the materials

- `PRD AI Engineer Test.pdf` — primary brief
- `transcript_cleaned.md` — discovery call (cleaned, speaker-attributed)
- Screenshots 5–9 — SACS, TCC, monthly expense worksheet, data point list
