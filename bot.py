import os
import sqlite3
import time
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🇺🇦 SWGOH UA PRO активний. Використай /реєстрація")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    add_user(uid)
    touch(uid)
    await update.message.reply_text("✅ Ти зареєстрований у гільдії")

async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all()
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users]
    await update.message.reply_text("🚨 РЕЙД ПОЧАВСЯ!\n" + " ".join(mentions), parse_mode="HTML")

async def tw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚔️ Territory War активовано!")

async def tb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌌 Territory Battle почалась!")

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all()
    mentions = [f"<a href='tg://user?id={u}'>👤</a>" for u in users]
    await update.message.reply_text("🔥 УВАГА ГІЛЬДІЇ:\n" + " ".join(mentions), parse_mode="HTML")

async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all()
    active_users = []
    for u in users:
        cur.execute("SELECT last_active FROM users WHERE id=?", (u,))
        last = cur.fetchone()[0]
        if now() - last < 86400:
            active_users.append(u)
    mentions = [f"<a href='tg://user?id={u}'>🔥</a>" for u in active_users]
    await update.message.reply_text("🔥 АКТИВНІ ГРАВЦІ:\n" + " ".join(mentions), parse_mode="HTML")

async def officers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_role("officer")
    mentions = [f"<a href='tg://user?id={u}'>👑</a>" for u in users]
    await update.message.reply_text("👑 ОФІЦЕРИ:\n" + " ".join(mentions), parse_mode="HTML")

async def make_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = int(context.args[0])
    set_role(uid, "officer")
    await update.message.reply_text("👑 Офіцера призначено")

async def auto_loop(app):
    while True:
        await asyncio.sleep(3600)
        inactive = get_inactive(3)
        if inactive:
            mentions = [f"<a href='tg://user?id={u}'>💤</a>" for u in inactive]
            try:
                await app.bot.send_message(chat_id=inactive[0], text="⚠️ НЕАКТИВНІ ГРАВЦІ:\n" + " ".join(mentions), parse_mode="HTML")
            except:
                pass

async def post_init(app):
    asyncio.create_task(auto_loop(app))

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("реєстрація", register))
app.add_handler(CommandHandler("рейд", raid))
app.add_handler(CommandHandler("тв", tw))
app.add_handler(CommandHandler("тб", tb))
app.add_handler(CommandHandler("усі", all_users))
app.add_handler(CommandHandler("активні", active))
app.add_handler(CommandHandler("офіцери", officers))
app.add_handler(CommandHandler("makeofficer", make_officer))
app.post_init = post_init
app.run_polling()
