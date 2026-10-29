"""
auth.py - Student accounts (passwords) and the owner (admin) login.

Passwords are never stored. Only a random salt + a PBKDF2-SHA256 hash is saved.
Recovery of the owner password (needs access to the laptop):
    python auth.py --reset-owner
"""

import hashlib
import hmac
import secrets
import sys
import time

import pandas as pd

import database
from database import db

ITERATIONS = 200_000
MIN_PASSWORD = 6


# ---------------- setup ----------------
def init_auth():
    """Add the password column and the settings table. Safe to call many times."""
    with db() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(students)")]
        if "password_hash" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )


# ---------------- password hashing ----------------
def _check_rules(password):
    if password is None or len(password) < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters")
    if len(password) > 100:
        raise ValueError("Password must be 100 characters or fewer")


def _hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return salt.hex() + "$" + digest.hex()


def _verify(password, stored):
    try:
        salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------------- student accounts ----------------
def register_student(name, password):
    """Create an account and return its id."""
    _check_rules(password)
    student_id = database.create_student(name)      # validates the name
    with db() as conn:
        conn.execute("UPDATE students SET password_hash = ? WHERE id = ?",
                     (_hash(password), student_id))
    return student_id


def login_student(name, password):
    """Return the student id, or raise ValueError with a generic message."""
    name = (name or "").strip()
    password = password or ""
    with db() as conn:
        row = conn.execute("SELECT id, password_hash FROM students WHERE name = ?",
                           (name,)).fetchone()
    if row is None:
        _hash(password or "x")          # similar timing for unknown names
        raise ValueError("Wrong name or password")
    if row["password_hash"] is None:
        # Old profile made before passwords existed: the first password claims it.
        _check_rules(password)
        with db() as conn:
            conn.execute("UPDATE students SET password_hash = ? WHERE id = ?",
                         (_hash(password), row["id"]))
        return row["id"]
    if not _verify(password, row["password_hash"]):
        raise ValueError("Wrong name or password")
    return row["id"]


def set_student_password(student_id, new_password):
    _check_rules(new_password)
    with db() as conn:
        conn.execute("UPDATE students SET password_hash = ? WHERE id = ?",
                     (_hash(new_password), student_id))


def delete_student(student_id):
    """Delete the account and ALL its data (foreign keys cascade)."""
    with db() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))


# ---------------- owner ----------------
def _get_setting(key):
    with db() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def owner_exists():
    return _get_setting("owner_hash") is not None


def set_owner_password(password):
    _check_rules(password)
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('owner_hash', ?)",
                     (_hash(password),))


def verify_owner(password):
    stored = _get_setting("owner_hash")
    return bool(stored) and _verify(password or "", stored)


def reset_owner_password():
    with db() as conn:
        conn.execute("DELETE FROM app_settings WHERE key = 'owner_hash'")


def students_overview():
    """Counts only: no quiz answers and no passwords."""
    with db() as conn:
        return pd.read_sql_query(
            "SELECT s.id, s.name, s.created_at, "
            "(s.password_hash IS NOT NULL) AS has_password, "
            "(SELECT COUNT(*) FROM quiz_attempts a WHERE a.student_id = s.id) AS quizzes, "
            "(SELECT MAX(taken_at) FROM quiz_attempts a WHERE a.student_id = s.id) AS last_quiz "
            "FROM students s ORDER BY s.id", conn)


# ---------------- simple lock after wrong attempts ----------------
def locked_seconds(state, key):
    return max(0, int(state.get(key + "_until", 0) - time.time()))


def register_failure(state, key, limit=5, lock_seconds=30):
    state[key + "_n"] = state.get(key + "_n", 0) + 1
    if state[key + "_n"] >= limit:
        state[key + "_until"] = time.time() + lock_seconds
        state[key + "_n"] = 0


def clear_failures(state, key):
    state[key + "_n"] = 0
    state[key + "_until"] = 0


if __name__ == "__main__":
    if "--reset-owner" in sys.argv:
        database.init_db()
        init_auth()
        reset_owner_password()
        print("Owner password removed. Open the Owner page to create a new one.")
    else:
        print("Use:  python auth.py --reset-owner")