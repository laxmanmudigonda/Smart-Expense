"""Small, reusable authentication and request-security helpers."""

import re
import secrets
from datetime import date
from decimal import Decimal
from decimal import InvalidOperation
from functools import wraps
from hmac import compare_digest

from flask import flash, redirect, session, url_for


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
MONEY_PATTERN = re.compile(r"^\d+(?:\.\d{1,2})?$")


def login_required(view):
    """Redirect anonymous visitors away from private application pages."""
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def generate_csrf_token():
    """Return the session's CSRF token, creating a strong token if needed."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def validate_csrf(submitted_token):
    """Compare a submitted CSRF token without timing-based leakage."""
    expected_token = session.get("csrf_token")
    return bool(
        expected_token
        and submitted_token
        and compare_digest(expected_token, submitted_token)
    )


def validate_username(username):
    """Return a user-facing username error or None when valid."""
    if not username:
        return "Username is required."
    if not 3 <= len(username) <= 30:
        return "Username must contain 3 to 30 characters."
    if not USERNAME_PATTERN.fullmatch(username):
        return "Username may contain only letters, numbers, and underscores."
    return None


def validate_password(password):
    """Return a user-facing password error or None when valid."""
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if len(password) > 128:
        return "Password must contain no more than 128 characters."
    if not any(character.isalpha() for character in password):
        return "Password must include at least one letter."
    if not any(character.isdigit() for character in password):
        return "Password must include at least one number."
    return None


def parse_amount_cents(value):
    """Convert a plain decimal money string to positive integer cents."""
    value = value.strip()
    if not MONEY_PATTERN.fullmatch(value):
        raise ValueError("Amount must be a positive number with up to two decimals.")
    try:
        amount_cents = int(Decimal(value) * 100)
    except (InvalidOperation, ValueError):
        raise ValueError("Amount must be a valid number.") from None
    if amount_cents <= 0:
        raise ValueError("Amount must be greater than zero.")
    if amount_cents > 99_999_999_999:
        raise ValueError("Amount is too large.")
    return amount_cents


def validate_iso_date(value):
    """Return a canonical ISO date string or raise a user-facing error."""
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ValueError("Choose a valid transaction date.") from None


def escape_like(value):
    """Escape SQL LIKE wildcard characters for literal search text."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
