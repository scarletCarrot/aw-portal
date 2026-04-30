"""AW Client Report Portal — Flask app (multi-client + auth + history)."""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
from io import BytesIO
from pathlib import Path

from flask import (
    Flask, render_template, request, send_file, redirect, url_for,
    abort, flash, session,
)

import db as dbmod
import models
from auth import bp as auth_bp, login_required, current_user
from calc import compute_report


BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# PDF backend (Playwright/Chromium). Inlines report.css to avoid base-URL pain.
# ---------------------------------------------------------------------------

def _render_pdf(html_str: str) -> bytes:
    from playwright.sync_api import sync_playwright  # type: ignore

    css_path = BASE_DIR / "static" / "css" / "report.css"
    if css_path.exists():
        css_text = css_path.read_text(encoding="utf-8")
        html_str = re.sub(
            r'<link[^>]*report\.css[^>]*>',
            f"<style>{css_text}</style>",
            html_str,
        )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html_str, wait_until="domcontentloaded")
            return page.pdf(
                format="Letter",
                margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"},
                print_background=True,
            )
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "AW_SECRET_KEY", "dev-only-secret-key-change-me-in-production"
)
app.jinja_env.globals.update(zip=zip)

dbmod.init_app(app)
app.register_blueprint(auth_bp)


@app.context_processor
def _inject_user():
    return {"current_user": current_user()}


def _today() -> str:
    return dt.date.today().strftime("%B %d, %Y")


# ---------------------------------------------------------------------------
# Root + clients CRUD
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user() is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for("clients_list"))


@app.route("/clients")
@login_required
def clients_list():
    return render_template("clients_list.html", clients=models.list_clients())


@app.route("/clients/new", methods=["GET", "POST"])
@login_required
def client_new():
    if request.method == "POST":
        cid = models.create_or_update_client(request.form)
        flash("Client created.", "success")
        return redirect(url_for("client_edit", client_id=cid))
    return render_template("client_edit.html", client=None)


@app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def client_edit(client_id):
    client = models.get_client(client_id)
    if client is None:
        abort(404)
    if request.method == "POST":
        models.create_or_update_client(request.form, client_id=client_id)
        flash("Client saved.", "success")
        return redirect(url_for("client_edit", client_id=client_id))
    return render_template("client_edit.html", client=client)


@app.post("/clients/<int:client_id>/delete")
@login_required
def client_delete(client_id):
    if models.get_client(client_id) is None:
        abort(404)
    models.delete_client(client_id)
    flash("Client deleted.", "success")
    return redirect(url_for("clients_list"))


@app.post("/clients/seed-demo")
@login_required
def seed_demo():
    cid = dbmod.seed_demo_client()
    flash("Demo client created.", "success")
    return redirect(url_for("client_edit", client_id=cid))


# ---------------------------------------------------------------------------
# Per-client report flow
# ---------------------------------------------------------------------------

def _parse_report_form(form, client) -> dict:
    def n(key):
        v = form.get(key, "")
        try:
            return float(v) if v != "" else 0.0
        except ValueError:
            return 0.0

    c1 = len(client["client_1"]["retirement_accounts"])
    c2 = len(client["client_2"]["retirement_accounts"])
    nr = len(client["non_retirement_accounts"])
    li = len(client["liabilities"])

    return {
        "c1_ret_balances":    [n(f"c1_ret_balance_{i}") for i in range(c1)],
        "c1_ret_cash":        [n(f"c1_ret_cash_{i}") or None for i in range(c1)],
        "c2_ret_balances":    [n(f"c2_ret_balance_{i}") for i in range(c2)],
        "c2_ret_cash":        [n(f"c2_ret_cash_{i}") or None for i in range(c2)],
        "non_ret_balances":   [n(f"non_ret_balance_{i}") for i in range(nr)],
        "non_ret_cash":       [n(f"non_ret_cash_{i}") or None for i in range(nr)],
        "trust_zillow":       n("trust_zillow"),
        "liability_balances": [n(f"liability_balance_{i}") for i in range(li)],
    }


@app.route("/clients/<int:client_id>/report", methods=["GET", "POST"])
@login_required
def client_report(client_id):
    client = models.get_client(client_id)
    if client is None:
        abort(404)

    if request.method == "POST":
        balances = _parse_report_form(request.form, client)
        computed = compute_report(client, balances)
        rid = models.save_report(client_id, balances, computed, current_user()["id"])
        session[f"report:{client_id}"] = rid

        return render_template(
            "report_preview.html",
            client=client, balances=balances, report=computed,
            today=_today(), report_id=rid,
        )

    history = models.list_reports(client_id)
    if history:
        defaults = history[0]["balances"]
        prefilled = True
    else:
        c1 = len(client["client_1"]["retirement_accounts"])
        c2 = len(client["client_2"]["retirement_accounts"])
        nr = len(client["non_retirement_accounts"])
        li = len(client["liabilities"])
        defaults = {
            "c1_ret_balances": [None] * c1, "c1_ret_cash": [None] * c1,
            "c2_ret_balances": [None] * c2, "c2_ret_cash": [None] * c2,
            "non_ret_balances": [None] * nr, "non_ret_cash": [None] * nr,
            "trust_zillow": None,
            "liability_balances": [None] * li,
        }
        prefilled = False

    return render_template(
        "quarterly_form.html",
        client=client, defaults=defaults,
        today=_today(), prefilled_from_history=prefilled,
    )


# ---------------------------------------------------------------------------
# Report rendering (HTML + PDF)
# ---------------------------------------------------------------------------

def _load_report_for_client(client_id):
    client = models.get_client(client_id)
    if client is None:
        abort(404)
    rid = session.get(f"report:{client_id}")
    rep = models.get_report(rid) if rid else None
    if rep is None:
        history = models.list_reports(client_id)
        rep = history[0] if history else None
    if rep is None:
        abort(404, description="No report has been generated for this client yet.")
    return client, rep["balances"], rep["computed"]


def _load_specific_report(report_id):
    rep = models.get_report(report_id)
    if rep is None:
        abort(404)
    client = models.get_client(rep["client_id"])
    return client, rep["balances"], rep["computed"]


def _render_sacs(client, balances, computed):
    return render_template(
        "sacs.html",
        client=client, balances=balances,
        sacs=computed["sacs"], today=_today(),
        report_css_url=url_for("static", filename="css/report.css"),
    )


def _render_tcc(client, balances, computed):
    return render_template(
        "tcc.html",
        client=client, balances=balances,
        tcc=computed["tcc"], today=_today(),
        report_css_url=url_for("static", filename="css/report.css"),
    )


@app.route("/clients/<int:client_id>/sacs")
@login_required
def client_sacs_html(client_id):
    return _render_sacs(*_load_report_for_client(client_id))


@app.route("/clients/<int:client_id>/tcc")
@login_required
def client_tcc_html(client_id):
    return _render_tcc(*_load_report_for_client(client_id))


@app.route("/clients/<int:client_id>/sacs.pdf")
@login_required
def client_sacs_pdf(client_id):
    client, balances, computed = _load_report_for_client(client_id)
    pdf = _render_pdf(_render_sacs(client, balances, computed))
    return send_file(BytesIO(pdf), as_attachment=True,
                     download_name=f"SACS_{client['client_1']['name']}.pdf",
                     mimetype="application/pdf")


@app.route("/clients/<int:client_id>/tcc.pdf")
@login_required
def client_tcc_pdf(client_id):
    client, balances, computed = _load_report_for_client(client_id)
    pdf = _render_pdf(_render_tcc(client, balances, computed))
    return send_file(BytesIO(pdf), as_attachment=True,
                     download_name=f"TCC_{client['client_1']['name']}.pdf",
                     mimetype="application/pdf")


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@app.route("/clients/<int:client_id>/history")
@login_required
def client_history(client_id):
    client = models.get_client(client_id)
    if client is None:
        abort(404)
    return render_template("history.html", client=client, history=models.list_reports(client_id))


@app.route("/reports/<int:report_id>/sacs.pdf")
@login_required
def historic_sacs_pdf(report_id):
    client, balances, computed = _load_specific_report(report_id)
    pdf = _render_pdf(_render_sacs(client, balances, computed))
    return send_file(BytesIO(pdf), as_attachment=True,
                     download_name=f"SACS_{client['client_1']['name']}_r{report_id}.pdf",
                     mimetype="application/pdf")


@app.route("/reports/<int:report_id>/tcc.pdf")
@login_required
def historic_tcc_pdf(report_id):
    client, balances, computed = _load_specific_report(report_id)
    pdf = _render_pdf(_render_tcc(client, balances, computed))
    return send_file(BytesIO(pdf), as_attachment=True,
                     download_name=f"TCC_{client['client_1']['name']}_r{report_id}.pdf",
                     mimetype="application/pdf")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    use_reloader = not sys.platform.startswith("win")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=use_reloader)
