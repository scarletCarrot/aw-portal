"""Session-based auth.

Rules:
- Anyone can register IF no user exists yet (bootstrap).
- After at least one user exists, /register requires an active session
  (existing user must invite the next teammate).
- Passwords hashed with werkzeug.security.
- Session is signed via Flask's SECRET_KEY (set in app.py).
"""

from __future__ import annotations

from functools import wraps

from flask import (
    Blueprint, request, redirect, url_for, render_template,
    session, flash, g, abort,
)
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db, user_count


bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def current_user():
    """Return user row dict, or None."""
    if g.get("user") is not None:
        return g.user
    uid = session.get("user_id")
    if not uid:
        g.user = None
        return None
    g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return g.user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/register", methods=["GET", "POST"])
def register():
    # Invite gate: only the first user can register without auth.
    bootstrap = (user_count() == 0)
    if not bootstrap and current_user() is None:
        flash("Registration is invite-only. An existing teammate must be logged in to add a new user.", "warn")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        name = (request.form.get("name") or "").strip() or None

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("register.html", bootstrap=bootstrap, name=name, email=email)
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html", bootstrap=bootstrap, name=name, email=email)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), name),
            )
            db.commit()
        except Exception:
            flash(f"Email '{email}' is already registered.", "error")
            return render_template("register.html", bootstrap=bootstrap, name=name, email=email)

        # If this was the bootstrap user, log them in immediately.
        if bootstrap:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome! You're the first user — full access.", "success")
            return redirect(url_for("clients_list"))

        flash(f"Created user {email}.", "success")
        return redirect(url_for("clients_list"))

    return render_template("register.html", bootstrap=bootstrap)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        nxt = request.args.get("next") or url_for("clients_list")
        return redirect(nxt)

    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("auth.login"))
