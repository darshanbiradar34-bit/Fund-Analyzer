"""
db.py
------
SQLite-backed storage for user accounts, watchlists, and alert
conditions. Uses only the Python standard library (sqlite3, hashlib,
secrets) - no extra dependency, no external database service.

*** IMPORTANT DEPLOYMENT CAVEAT ***
On Render's free tier (and most PaaS free tiers), the filesystem is
EPHEMERAL - it resets on every redeploy and periodically on restarts.
That means this SQLite file (and everyone's accounts/watchlists in it)
can be wiped without warning on the free tier. This is fine for
kicking the tyres, but for anything you want to actually persist:
  - Upgrade to a Render paid plan and attach a persistent disk, OR
  - Move to a hosted database (Render/Railway/Supabase all offer a
    free Postgres tier) - would need swapping this module's queries
    from sqlite3 to something like psycopg2, which is a bigger change.
This module is written so that swap is contained to this one file -
nothing elsewhere in the app talks to the database directly.

Password storage: PBKDF2-HMAC-SHA256 with a random per-user salt,
100,000 iterations - a reasonable stdlib-only approach, though a
dedicated password-hashing library (argon2, bcrypt) would be a
worthwhile upgrade if this ever handles real money-adjacent accounts
at scale.
"""

import sqlite3
import hashlib
import secrets
import time
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data.db"

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def init_db():
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                item_type TEXT NOT NULL,          -- 'stock' or 'fund'
                notes TEXT,
                added_at INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                item_type TEXT NOT NULL,
                condition_type TEXT NOT NULL,     -- 'price_above','price_below','rsi_above','rsi_below'
                threshold REAL NOT NULL,
                created_at INTEGER NOT NULL,
                triggered_at INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000).hex()


# ---------------------------------------------------------------------------
# Users / sessions
# ---------------------------------------------------------------------------

def create_user(username: str, password: str) -> dict:
    """Returns {'ok': True, 'user_id': ...} or {'ok': False, 'error': ...}."""
    username = username.strip()
    if len(username) < 3:
        return {"ok": False, "error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"ok": False, "error": "Password must be at least 6 characters."}

    salt = secrets.token_bytes(16)
    pw_hash = _hash_password(password, salt)

    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username, pw_hash, salt.hex(), int(time.time())),
            )
            return {"ok": True, "user_id": cur.lastrowid}
    except sqlite3.IntegrityError:
        return {"ok": False, "error": "That username is already taken."}


def verify_user(username: str, password: str):
    """Returns user_id on success, None on failure."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, password_hash, salt FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    if row is None:
        return None
    salt = bytes.fromhex(row["salt"])
    if _hash_password(password, salt) == row["password_hash"]:
        return row["id"]
    return None


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, int(time.time())),
        )
    return token


def get_user_id_from_session(token: str):
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute("SELECT user_id, created_at FROM sessions WHERE token = ?", (token,)).fetchone()
    if row is None:
        return None
    if int(time.time()) - row["created_at"] > SESSION_TTL_SECONDS:
        delete_session(token)
        return None
    return row["user_id"]


def get_username(user_id: int):
    with _connect() as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["username"] if row else None


def delete_session(token: str):
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def add_watchlist_item(user_id: int, symbol: str, item_type: str, notes: str = "") -> dict:
    symbol = symbol.strip().upper()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM watchlist WHERE user_id = ? AND symbol = ? AND item_type = ?",
            (user_id, symbol, item_type),
        ).fetchone()
        if existing:
            return {"ok": False, "error": f"{symbol} is already on your watchlist."}
        cur = conn.execute(
            "INSERT INTO watchlist (user_id, symbol, item_type, notes, added_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, symbol, item_type, notes, int(time.time())),
        )
        return {"ok": True, "id": cur.lastrowid}


def list_watchlist(user_id: int) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, symbol, item_type, notes, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_watchlist_item(user_id: int, item_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE id = ? AND user_id = ?", (item_id, user_id))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

VALID_CONDITION_TYPES = {"price_above", "price_below", "rsi_above", "rsi_below"}


def add_alert(user_id: int, symbol: str, item_type: str, condition_type: str, threshold: float) -> dict:
    if condition_type not in VALID_CONDITION_TYPES:
        return {"ok": False, "error": f"Unknown condition type '{condition_type}'."}
    symbol = symbol.strip().upper()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alerts (user_id, symbol, item_type, condition_type, threshold, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, symbol, item_type, condition_type, threshold, int(time.time())),
        )
        return {"ok": True, "id": cur.lastrowid}


def list_alerts(user_id: int) -> list:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, symbol, item_type, condition_type, threshold, created_at, triggered_at
               FROM alerts WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def remove_alert(user_id: int, alert_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id))
        return cur.rowcount > 0


def mark_alert_triggered(alert_id: int):
    with _connect() as conn:
        conn.execute("UPDATE alerts SET triggered_at = ? WHERE id = ?", (int(time.time()), alert_id))


def get_untriggered_alerts_for_symbol(user_id: int, symbol: str) -> list:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, condition_type, threshold FROM alerts
               WHERE user_id = ? AND symbol = ? AND triggered_at IS NULL""",
            (user_id, symbol.upper()),
        ).fetchall()
    return [dict(r) for r in rows]
