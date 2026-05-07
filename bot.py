import os
import asyncio
import sqlite3
import time
import random
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")

# База данных
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    role TEXT DEFAULT 'player',
    last_active INTEGER
)
""")
conn.commit()

def now():
    return int(time.time())

async def add_user(uid, username):
    cur.execute("INSERT OR IGNORE INTO users (id, username, role, last_active) VALUES (?, ?, 'player', ?)", 
                (uid, username, now()))
    conn.commit()

async def get_all_users():
    cur.execute("SELECT id FROM users")
    return [row[0] for row in cur.fetchall()]

async def is_officer(uid):
    cur.execute("SELECT role FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    return row and row[0] == "officer"

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇺🇦 SWGOH UA Бот працює!\n\n"
        "Команди:\n"
        "/register - реєстрація\n"
        "/raid - рейд\n"
        "/tw - Territory War\n"
        "/tb - Territory Battle\n"
        "/all - всіх покликати\n"
        "/stats - статистика\n"
        "/tip - порада\n"
        "/donate - нагадати про донат"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    await add_user(uid, username)
    await update.message.reply_text("✅ Ти зареєстрований у гільдії!")

async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text("🚨 РЕЙД ПОЧАВСЯ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text("⚔️ TERRITORY WAR!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>🌌</a>" for u in users[:50]]
    await update.message.reply_text("🌌 TERRITORY BATTLE!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>👤</a>" for u in users[:30]]
    await update.message.reply_text("🔥 УВАГА ГІЛЬДІЇ:\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE role='officer'")
    officers = cur.fetchone()[0]
    await update.message.reply_text(
        f"📊 СТАТИСТИКА\n"
        f"👥 Гравців: {total}\n"
        f"👑 Офіцерів: {officers}"
    )

async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tips = [
        "Фарми Дарт Ревана",
        "Копи кристали на подвійні дропи",
        "Використовуй моди зі швидкістю",
        "Завжди донать очки гільдії"
    ]
    await update.message.reply_text(f"💡 ПОРАДА: {random.choice(tips)}")

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>💰</a>" for u in users[:50]]
    await update.message.reply_text("💰 НЕ ЗАБУДЬ ЗАДОНАТИТИ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("raid", raid))
    app.add_handler(CommandHandler("tw", tw))
    app.add_handler(CommandHandler("tb", tb))
    app.add_handler(CommandHandler("all", all_users))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("tip", tip))
    app.add_handler(CommandHandler("donate", donate))
    
    print("✅ Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
