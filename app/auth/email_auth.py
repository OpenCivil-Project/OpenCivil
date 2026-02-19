"""
auth/email_auth.py
------------------
Business logic for email/password authentication.
Handles register, login, email verification, and password reset.
All DB and email calls are wrapped so the dialog just calls simple methods.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, Dict, Any

import bcrypt
from pymongo.errors import DuplicateKeyError

from .db import (
    create_user, get_user_by_email,
    set_verify_code, verify_user,
    set_reset_code, reset_password,
    update_last_login, Database,
)
from .email_service import generate_code, send_verification_email, send_reset_email

logger = logging.getLogger(__name__)

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _check(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def _ok(data: Any = None)  -> Tuple[bool, str, Any]:
    return True,  "",      data

def _err(msg: str)         -> Tuple[bool, str, None]:
    return False, msg,     None

def register(name: str, email: str,
             password: str) -> Tuple[bool, str, None]:
    """
    Create a new account and send a verification email.
    Returns (success, error_message, None).
    """
                      
    if len(password) < 8:
        return _err("Password must be at least 8 characters.")
    if "@" not in email:
        return _err("Please enter a valid email address.")

    try:
        Database.connect()
    except Exception:
        return _err("Cannot connect to database. Check your internet connection.")

    existing = get_user_by_email(email)
    if existing:
        if existing.get("provider") == "google":
            return _err("This email is linked to a Google account. Use Google login.")
        return _err("An account with this email already exists.")

    try:
        pw_hash = _hash(password)
        create_user(name, email, pw_hash, provider="email")

        code = generate_code(6)
        set_verify_code(email, code)
        send_verification_email(email, name, code)

        logger.info("Registered new user: %s", email)
        return _ok()

    except DuplicateKeyError:
        return _err("An account with this email already exists.")
    except Exception as exc:
        logger.error("Registration error: %s", exc)
        return _err(f"Registration failed: {exc}")

def login(email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Verify credentials and return user info dict on success.
    Returns (success, error_message, user_info_or_None).
    """
    try:
        Database.connect()
    except Exception:
        return _err("Cannot connect to database. Check your internet connection.")

    user = get_user_by_email(email)
    if not user:
        return _err("No account found with this email.")

    if user.get("provider") == "google":
        return _err("This email is linked to a Google account. Use Google login.")

    if not _check(password, user.get("password_hash", "")):
        return _err("Incorrect password.")

    if not user.get("verified"):
        return _err("Please verify your email first. Check your inbox.")

    update_last_login(email)

    user_info = {
        "name":     user["name"],
        "email":    user["email"],
        "picture":  user.get("picture", ""),
        "provider": "email",
    }
    return _ok(user_info)

def confirm_verification(email: str,
                         code: str) -> Tuple[bool, str, None]:
    """Check the 6-digit code and mark account as verified."""
    try:
        Database.connect()
    except Exception:
        return _err("Cannot connect to database.")

    success = verify_user(email, code)
    if not success:
        return _err("Invalid or expired code. Please try again.")

    logger.info("Email verified: %s", email)
    return _ok()

def send_forgot_password(email: str) -> Tuple[bool, str, None]:
    """Generate a reset code and email it to the user."""
    try:
        Database.connect()
    except Exception:
        return _err("Cannot connect to database.")

    user = get_user_by_email(email)
    if not user:
                                                                
        return _ok()

    if user.get("provider") == "google":
        return _err("This account uses Google login. No password to reset.")

    code    = generate_code(6)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    set_reset_code(email, code, expires)

    try:
        send_reset_email(email, user.get("name", ""), code)
    except Exception as exc:
        logger.error("Failed to send reset email: %s", exc)
        return _err("Failed to send email. Please try again.")

    return _ok()

def confirm_reset(email: str, code: str,
                  new_password: str) -> Tuple[bool, str, None]:
    """Verify the reset code and set the new password."""
    if len(new_password) < 8:
        return _err("Password must be at least 8 characters.")

    try:
        Database.connect()
    except Exception:
        return _err("Cannot connect to database.")

    success = reset_password(email, code, _hash(new_password))
    if not success:
        return _err("Invalid or expired reset code. Please request a new one.")

    logger.info("Password reset successful: %s", email)
    return _ok()
