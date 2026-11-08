import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.config import DB_PATH

Path("data").mkdir(exist_ok=True)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        language TEXT DEFAULT 'uz',
        is_admin INTEGER DEFAULT 0,
        vip_until TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        title TEXT,
        description TEXT,
        year INTEGER,
        genre TEXT,
        image_url TEXT,
        seasons TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bank_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT,
        card_number TEXT,
        owner_name TEXT,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vip_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        months INTEGER UNIQUE,
        price TEXT,
        title TEXT,
        active INTEGER DEFAULT 1
    )
    """)

    conn.commit()
    conn.close()

def ensure_default_plans():
    conn = get_conn()
    cur = conn.cursor()

    plans = [
        (1, "150000", "1 oy VIP", 1),
        (2, "260000", "2 oy VIP", 1),
        (3, "360000", "3 oy VIP", 1),
        (6, "650000", "6 oy VIP", 1),
        (12, "1200000", "12 oy VIP", 1),
    ]

    for months, price, title, active in plans:
        cur.execute("""
            INSERT OR IGNORE INTO vip_plans (months, price, title, active)
            VALUES (?, ?, ?, ?)
        """, (months, price, title, active))

    conn.commit()
    conn.close()

def get_or_create_user(telegram_id, username=None, first_name=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    if row is None:
        cur.execute("""
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
        """, (telegram_id, username, first_name))
        conn.commit()
        row = cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    else:
        cur.execute("""
            UPDATE users
            SET username = ?, first_name = ?
            WHERE telegram_id = ?
        """, (username, first_name, telegram_id))
        conn.commit()

    result = dict(row) if row else None
    conn.close()
    return result

def set_admin(telegram_id, value=1):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin = ? WHERE telegram_id = ?", (value, telegram_id))
    conn.commit()
    conn.close()

def is_admin(telegram_id):
    conn = get_conn()
    row = conn.execute("SELECT is_admin FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return bool(row and row["is_admin"])

def get_user_by_id(telegram_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def set_setting(key, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings(key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

def get_setting(key, default=""):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return default
    return row["value"]

def add_movie(code, title, description, year, genre, image_url, seasons):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO movies (code, title, description, year, genre, image_url, seasons)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (code, title, description, year, genre, image_url, json.dumps(seasons, ensure_ascii=False)))
    conn.commit()
    conn.close()

def get_movie_by_code(code):
    conn = get_conn()
    row = conn.execute("SELECT * FROM movies WHERE code = ?", (code,)).fetchone()
    conn.close()
    if not row:
        return None
    movie = dict(row)
    movie["seasons"] = json.loads(movie["seasons"] or "{}")
    return movie

def list_movies():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM movies ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        item = dict(row)
        item["seasons"] = json.loads(item["seasons"] or "{}")
        result.append(item)
    return result

def add_bank_card(label, card_number, owner_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO bank_cards (label, card_number, owner_name)
        VALUES (?, ?, ?)
    """, (label, card_number, owner_name))
    conn.commit()
    conn.close()

def list_bank_cards():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM bank_cards WHERE active = 1 ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_vip_plans():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM vip_plans WHERE active = 1 ORDER BY months ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_vip_plan(months):
    conn = get_conn()
    row = conn.execute("SELECT * FROM vip_plans WHERE months = ? AND active = 1", (months,)).fetchone()
    conn.close()
    return dict(row) if row else None

def user_has_vip(telegram_id):
    user = get_user_by_id(telegram_id)
    if not user:
        return False
    vip_until = user.get("vip_until")
    if not vip_until:
        return False
    try:
        return datetime.fromisoformat(vip_until) > datetime.now()
    except Exception:
        return False

def activate_vip(telegram_id, months):
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT vip_until FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    if not row:
        conn.close()
        return False

    now = datetime.now()
    current = row["vip_until"]
    if current:
        try:
            current_dt = datetime.fromisoformat(current)
            if current_dt > now:
                next_dt = current_dt + timedelta(days=30 * months)
            else:
                next_dt = now + timedelta(days=30 * months)
        except Exception:
            next_dt = now + timedelta(days=30 * months)
    else:
        next_dt = now + timedelta(days=30 * months)

    cur.execute("""
        UPDATE users
        SET vip_until = ?
        WHERE telegram_id = ?
    """, (next_dt.isoformat(), telegram_id))
    conn.commit()
    conn.close()
    return True