"""SQLite connection + initialization + seed helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from flask import g, current_app


DB_FILENAME = "aw_portal.db"


def db_path() -> Path:
    return Path(current_app.root_path) / DB_FILENAME


def get_db() -> sqlite3.Connection:
    """Per-request SQLite connection. Reused within one request."""
    if "db" not in g:
        conn = sqlite3.connect(db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_e=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    schema = (Path(current_app.root_path) / "schema.sql").read_text(encoding="utf-8")
    db = get_db()
    db.executescript(schema)
    db.commit()


def init_app(app) -> None:
    """Register teardown hook + ensure schema is applied on first boot."""
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def seed_demo_client() -> int:
    """Create a sample client matching data.SAMPLE_CLIENT. Returns client id."""
    from data import SAMPLE_CLIENT

    db = get_db()
    cur = db.cursor()
    sc = SAMPLE_CLIENT
    cur.execute(
        """INSERT INTO clients (
              c1_name, c1_dob, c1_ssn_last4, c1_monthly_salary,
              c2_name, c2_dob, c2_ssn_last4, c2_monthly_salary,
              monthly_outflow, floor, ded_auto, ded_home, ded_health,
              trust_address
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            sc["client_1"]["name"], sc["client_1"]["dob"], sc["client_1"]["ssn_last4"], sc["client_1"]["monthly_salary"],
            sc["client_2"]["name"], sc["client_2"]["dob"], sc["client_2"]["ssn_last4"], sc["client_2"]["monthly_salary"],
            sc["sacs_budget"]["monthly_outflow"], sc["sacs_budget"]["floor"],
            sc["sacs_budget"]["insurance_deductibles"]["auto"],
            sc["sacs_budget"]["insurance_deductibles"]["home"],
            sc["sacs_budget"]["insurance_deductibles"]["health"],
            sc["trust"]["property_address"],
        ),
    )
    cid = cur.lastrowid

    for i, a in enumerate(sc["client_1"]["retirement_accounts"]):
        cur.execute(
            "INSERT INTO accounts (client_id, kind, type, last4, sort_order) VALUES (?,?,?,?,?)",
            (cid, "c1_retirement", a["type"], a["last4"], i),
        )
    for i, a in enumerate(sc["client_2"]["retirement_accounts"]):
        cur.execute(
            "INSERT INTO accounts (client_id, kind, type, last4, sort_order) VALUES (?,?,?,?,?)",
            (cid, "c2_retirement", a["type"], a["last4"], i),
        )
    for i, a in enumerate(sc["non_retirement_accounts"]):
        cur.execute(
            "INSERT INTO accounts (client_id, kind, type, last4, is_sacs, sort_order) VALUES (?,?,?,?,?,?)",
            (cid, "non_retirement", a["type"], a["last4"], a.get("is_sacs"), i),
        )
    for i, l in enumerate(sc["liabilities"]):
        cur.execute(
            "INSERT INTO liabilities (client_id, type, interest_rate, sort_order) VALUES (?,?,?,?)",
            (cid, l["type"], l["interest_rate"], i),
        )

    db.commit()
    return cid


def user_count() -> int:
    return get_db().execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
