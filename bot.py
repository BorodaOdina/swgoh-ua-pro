from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import sqlite3
import time
import asyncio

TOKEN = "ВСТАВЬ_СВОЙ_ТОКЕН_СЮДА"

conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    role TEXT DEFAULT 'player',
    last_active INTEGER
)
""")
conn.commit()

def now():
    return int(time.time())

def add_user(uid):
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, 'player', ?)", (uid, now()))
    conn.commit()

def touch(uid):
    cur.execute("UPDATE users SET last_active=? WHERE id=?", (now(), uid))
    conn.commit()

def get_all():
    return [r[0] for r in cur.execute("SELECT id FROM users")]

def get_role(role):
    return [r[0] for r in cur.execute("SELECT id FROM users WHERE role=?", (role,))]

def set_role(uid, role):
    cur.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    conn.commit()

def get_inactive(days):
    limit = now() - days * 86400
    return [r[0] for r in cur.execute("SELECT id FROM users WHERE last_active < ?", (limit,))]

async def start(update: Update, context:
