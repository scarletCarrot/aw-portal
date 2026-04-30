"""Data-access functions. Translates between SQLite rows and the dict shape calc.py expects."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from db import get_db


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def list_clients() -> list[dict]:
    rows = get_db().execute(
        """SELECT c.*,
                  (SELECT MAX(generated_at) FROM reports r WHERE r.client_id = c.id) AS last_report_at
           FROM clients c
           ORDER BY c.c1_name COLLATE NOCASE"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_client(client_id: int) -> Optional[dict]:
    """Return the full client structure (dict matching data.SAMPLE_CLIENT shape) or None."""
    db = get_db()
    row = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row:
        return None

    accts = db.execute(
        "SELECT * FROM accounts WHERE client_id = ? ORDER BY kind, sort_order",
        (client_id,),
    ).fetchall()
    liabs = db.execute(
        "SELECT * FROM liabilities WHERE client_id = ? ORDER BY sort_order",
        (client_id,),
    ).fetchall()

    def acct(a):
        d = {"type": a["type"], "last4": a["last4"]}
        if a["is_sacs"]:
            d["is_sacs"] = a["is_sacs"]
        return d

    return {
        "id": row["id"],
        "client_1": {
            "name": row["c1_name"],
            "dob": row["c1_dob"],
            "ssn_last4": row["c1_ssn_last4"],
            "monthly_salary": row["c1_monthly_salary"],
            "retirement_accounts": [acct(a) for a in accts if a["kind"] == "c1_retirement"],
        },
        "client_2": {
            "name": row["c2_name"] or "",
            "dob": row["c2_dob"] or "",
            "ssn_last4": row["c2_ssn_last4"] or "",
            "monthly_salary": row["c2_monthly_salary"],
            "retirement_accounts": [acct(a) for a in accts if a["kind"] == "c2_retirement"],
        },
        "non_retirement_accounts": [acct(a) for a in accts if a["kind"] == "non_retirement"],
        "trust": {
            "property_address": row["trust_address"] or "",
        },
        "liabilities": [
            {"type": l["type"], "interest_rate": l["interest_rate"]}
            for l in liabs
        ],
        "sacs_budget": {
            "monthly_outflow": row["monthly_outflow"],
            "floor": row["floor"],
            "insurance_deductibles": {
                "auto": row["ded_auto"],
                "home": row["ded_home"],
                "health": row["ded_health"],
            },
        },
        # raw row fields for the edit form
        "_row": dict(row),
    }


def create_or_update_client(form_data: dict, client_id: Optional[int] = None) -> int:
    """Upsert a client + replace its accounts/liabilities. Returns client id."""
    db = get_db()
    cur = db.cursor()
    now = datetime.utcnow().isoformat(timespec="seconds")

    cols = (
        form_data["c1_name"], form_data.get("c1_dob"), form_data.get("c1_ssn_last4"),
        float(form_data.get("c1_monthly_salary") or 0),
        form_data.get("c2_name") or None,
        form_data.get("c2_dob"), form_data.get("c2_ssn_last4"),
        float(form_data.get("c2_monthly_salary") or 0),
        float(form_data.get("monthly_outflow") or 0),
        float(form_data.get("floor") or 1000),
        float(form_data.get("ded_auto") or 0),
        float(form_data.get("ded_home") or 0),
        float(form_data.get("ded_health") or 0),
        form_data.get("trust_address"),
    )

    if client_id:
        cur.execute(
            """UPDATE clients SET
                  c1_name=?, c1_dob=?, c1_ssn_last4=?, c1_monthly_salary=?,
                  c2_name=?, c2_dob=?, c2_ssn_last4=?, c2_monthly_salary=?,
                  monthly_outflow=?, floor=?, ded_auto=?, ded_home=?, ded_health=?,
                  trust_address=?, updated_at=?
               WHERE id=?""",
            (*cols, now, client_id),
        )
        cur.execute("DELETE FROM accounts WHERE client_id=?", (client_id,))
        cur.execute("DELETE FROM liabilities WHERE client_id=?", (client_id,))
    else:
        cur.execute(
            """INSERT INTO clients (
                  c1_name, c1_dob, c1_ssn_last4, c1_monthly_salary,
                  c2_name, c2_dob, c2_ssn_last4, c2_monthly_salary,
                  monthly_outflow, floor, ded_auto, ded_home, ded_health,
                  trust_address
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            cols,
        )
        client_id = cur.lastrowid

    # Re-insert accounts + liabilities from arrays in the form.
    # Form fields look like:
    #   c1_ret_type[], c1_ret_last4[],
    #   c2_ret_type[], c2_ret_last4[],
    #   non_ret_type[], non_ret_last4[], non_ret_is_sacs[],
    #   liability_type[], liability_rate[]

    def add_accounts(prefix: str, kind: str, with_sacs: bool = False):
        types = form_data.getlist(f"{prefix}_type[]")  # type: ignore
        last4s = form_data.getlist(f"{prefix}_last4[]")  # type: ignore
        sacs   = form_data.getlist(f"{prefix}_is_sacs[]") if with_sacs else [None] * len(types)  # type: ignore
        for i, (t, l4, s) in enumerate(zip(types, last4s, sacs)):
            if (t or "").strip() == "":
                continue
            cur.execute(
                "INSERT INTO accounts (client_id, kind, type, last4, is_sacs, sort_order) VALUES (?,?,?,?,?,?)",
                (client_id, kind, t.strip(), (l4 or "").strip() or None, (s or None) if with_sacs else None, i),
            )

    add_accounts("c1_ret",  "c1_retirement")
    add_accounts("c2_ret",  "c2_retirement")
    add_accounts("non_ret", "non_retirement", with_sacs=True)

    types = form_data.getlist("liability_type[]")           # type: ignore
    rates = form_data.getlist("liability_rate[]")           # type: ignore
    for i, (t, r) in enumerate(zip(types, rates)):
        if (t or "").strip() == "":
            continue
        cur.execute(
            "INSERT INTO liabilities (client_id, type, interest_rate, sort_order) VALUES (?,?,?,?)",
            (client_id, t.strip(), float(r or 0), i),
        )

    db.commit()
    return client_id


def delete_client(client_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM clients WHERE id=?", (client_id,))
    db.commit()


# ---------------------------------------------------------------------------
# Reports (history)
# ---------------------------------------------------------------------------

def save_report(client_id: int, balances: dict, computed: dict, user_id: Optional[int]) -> int:
    db = get_db()
    cur = db.execute(
        """INSERT INTO reports (client_id, balances_json, computed_json, generated_by)
           VALUES (?, ?, ?, ?)""",
        (client_id, json.dumps(balances), json.dumps(computed), user_id),
    )
    db.commit()
    return cur.lastrowid


def list_reports(client_id: int) -> list[dict]:
    rows = get_db().execute(
        """SELECT r.id, r.generated_at, r.balances_json, r.computed_json, u.email AS generated_by_email
           FROM reports r
           LEFT JOIN users u ON u.id = r.generated_by
           WHERE r.client_id = ?
           ORDER BY r.generated_at DESC""",
        (client_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["balances"] = json.loads(d["balances_json"])
        d["computed"] = json.loads(d["computed_json"])
        out.append(d)
    return out


def get_report(report_id: int) -> Optional[dict]:
    row = get_db().execute(
        "SELECT * FROM reports WHERE id = ?", (report_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["balances"] = json.loads(d["balances_json"])
    d["computed"] = json.loads(d["computed_json"])
    return d
