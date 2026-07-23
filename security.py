"""
security.py - Session-basierte Authentifizierung fuer ekeyAudit.

Enthaelt Login/Logout-Logik, den @login_required Decorator sowie
einfache Nutzerverwaltung (Users anlegen/bearbeiten) auf Basis der
Tabelle 'users' (username, password_hash, rolle).
"""

from functools import wraps

from flask import session, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash

import database as db


def login_user(username, password):
    """Prueft Zugangsdaten. Bei Erfolg wird die Session gesetzt und True zurueckgegeben."""
    user = db.get_user_by_username(username)
    if not user:
        return False
    if not user.get("aktiv", 1):
        return False
    if check_password_hash(user["password_hash"], password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["rolle"] = user["rolle"]
        return True
    return False


def logout_user():
    session.clear()


def current_user():
    if "user_id" not in session:
        return None
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "rolle": session.get("rolle"),
    }


def is_logged_in():
    return "user_id" in session


def is_auth_enabled():
    """Liest die Einstellung 'auth_enabled' aus app_settings. Standard: aus (0)."""
    return db.get_setting("auth_enabled", "0") == "1"


def set_auth_enabled(enabled):
    db.set_setting("auth_enabled", "1" if enabled else "0")


def login_required(view_func):
    """Erzwingt Login nur, wenn Authentifizierung in den Einstellungen aktiviert ist."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not is_auth_enabled():
            return view_func(*args, **kwargs)
        if not is_logged_in():
            return redirect(url_for("gui.login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    """Decorator, der den Zugriff auf bestimmte Rollen beschraenkt (z.B. Admin).
    Wenn Authentifizierung deaktiviert ist, wird der Zugriff immer erlaubt."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not is_auth_enabled():
                return view_func(*args, **kwargs)
            if not is_logged_in():
                return redirect(url_for("gui.login", next=request.path))
            if session.get("rolle") not in roles:
                flash("Keine Berechtigung fuer diese Aktion.", "error")
                return redirect(url_for("gui.index"))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


# --------------------------------------------------------------------------
# Nutzerverwaltung
# --------------------------------------------------------------------------

def create_new_user(username, password, rolle):
    if db.get_user_by_username(username):
        return False, "Benutzername existiert bereits."
    db.create_user(username, generate_password_hash(password), rolle)
    return True, "Benutzer angelegt."


def update_existing_user(user_id, rolle, aktiv, new_password=None):
    pwd_hash = generate_password_hash(new_password) if new_password else None
    db.update_user(user_id, rolle, 1 if aktiv else 0, pwd_hash)
    return True, "Benutzer aktualisiert."
