"""Student and outlet-worker sign-in helpers."""

import hashlib
import hmac
import os
import re

from database import add_user, get_outlets, get_user_by_email

DEMO_WORKER_PASSWORD = "CampusDemo123!"


def hash_password(password):
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 260_000
    )
    return salt.hex() + "$" + password_hash.hex()


def check_password(password, saved_hash):
    try:
        salt_text, hash_text = saved_hash.split("$")
        salt = bytes.fromhex(salt_text)
        expected_hash = bytes.fromhex(hash_text)
    except (ValueError, TypeError):
        return False

    entered_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 260_000
    )
    return hmac.compare_digest(entered_hash, expected_hash)


def valid_email(email):
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()) is not None


def register_student(name, email, password):
    if not name.strip():
        return False, "Please enter your name."
    if not valid_email(email):
        return False, "Please enter a valid email address."
    if len(password) < 8:
        return False, "Use a password with at least 8 characters."

    added = add_user(name.strip(), email, hash_password(password), "student")
    if not added:
        return False, "An account with this email already exists."
    return True, "Account created. You can now log in."


def login_user(email, password):
    user = get_user_by_email(email)
    if user is None or not check_password(password, user["password_hash"]):
        return None

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "outlet": user["outlet"],
    }


def make_worker_email(outlet):
    short_name = outlet.lower().replace("'", "")
    short_name = re.sub(r"[^a-z0-9]+", ".", short_name).strip(".")
    return "worker." + short_name + "@campuscrave.demo"


def create_demo_workers():
    """Create one demo worker account per outlet for local testing."""
    for outlet in get_outlets():
        name = outlet["name"]
        email = make_worker_email(name)
        if get_user_by_email(email) is None:
            add_user(
                name=name + " Worker",
                email=email,
                password_hash=hash_password(DEMO_WORKER_PASSWORD),
                role="worker",
                outlet=name,
            )
