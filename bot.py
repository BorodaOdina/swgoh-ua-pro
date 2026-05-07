import os
import sqlite3
import time
import random
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")

# ========== БАЗА ДАНИХ ==========
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    role TEXT DEFAULT 'player',
    last_active INTEGER,
    ally_code TEXT
)
""")
conn.commit()

def now():
    return int(time.time())

def add_user(uid, username):
    cur.execute("INSERT OR IGNORE INTO users (id, username, role, last_active) VALUES (?, ?, 'player', ?)", 
                (uid, username, now()))
    conn.commit()

def update_last_active(uid):
    cur.execute("UPDATE users SET last_active=? WHERE id=?", (now(), uid))
    conn.commit()

def get_all_users():
    cur.execute("SELECT id FROM users")
    return [row[0] for row in cur.fetchall()]

def is_officer(uid):
    cur.execute("SELECT role FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    return row and row[0] == "officer"

def set_role(uid, role):
    cur.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    conn.commit()

def get_role_users(role):
    cur.execute("SELECT id FROM users WHERE role=?", (role,))
    return [row[0] for row in cur.fetchall()]

def get_inactive_users(days):
    limit = now() - days * 86400
    cur.execute("SELECT id, username, last_active FROM users WHERE last_active < ?", (limit,))
    return cur.fetchall()

# ========== КОМАНДЫ (ВСЕ async) ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 SWGOH UA GUILD BOT\n\n"
        "👤 ОСНОВНІ КОМАНДИ:\n"
        "/register - реєстрація\n"
        "/mystat - моя статистика\n"
        "/tip - порада по грі\n\n"
        "👑 КОМАНДИ ОФІЦЕРІВ:\n"
        "/raid - рейд\n"
        "/tw - Territory War\n"
        "/tb - Territory Battle\n"
        "/all - всіх покликати\n"
        "/donate - нагадати про донат\n"
        "/makeofficer @user - призначити офіцера\n"
        "/inactive 7 - список неактивних\n\n"
        "📊 СТАТИСТИКА:\n"
        "/stats - статистика гільдії\n"
        "/active - активні сьогодні\n"
        "/officers - список офіцерів"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    add_user(uid, username)
    update_last_active(uid)
    await update.message.reply_text("✅ Ти зареєстрований у гільдії!")

async def mystat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cur.execute("SELECT role, last_active FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    if not row:
        await update.message.reply_text("❌ Спочатку /register")
        return
    role, last = row
    diff = now() - last
    if diff < 3600:
        time_str = f"{diff // 60} хв тому"
    elif diff < 86400:
        time_str = f"{diff // 3600} год тому"
    else:
        time_str = f"{diff // 86400} днів тому"
    await update.message.reply_text(f"📊 ТВОЯ СТАТИСТИКА\n\nРоль: {role}\nОстання активність: {time_str}")

# Команди офіцерів
async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text("🚨 РЕЙД ПОЧАВСЯ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text("⚔️ TERRITORY WAR!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>🌌</a>" for u in users[:50]]
    await update.message.reply_text("🌌 TERRITORY BATTLE!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>👤</a>" for u in users[:30]]
    await update.message.reply_text("🔥 УВАГА ГІЛЬДІЇ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>💰</a>" for u in users[:50]]
    await update.message.reply_text("💰 НЕ ЗАБУДЬ ЗАДОНАТИТИ ОЧКИ ГІЛЬДІЇ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def make_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери можуть призначати офіцерів")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Використання: /makeofficer @username або /makeofficer telegram_id")
        return
    
    target = context.args[0]
    if target.startswith("@"):
        username = target[1:]
        cur.execute("SELECT id FROM users WHERE username LIKE ?", (f"%{username}%",))
        row = cur.fetchone()
        if not row:
            await update.message.reply_text("❌ Користувача не знайдено. Спочатку він має зареєструватись через /register")
            return
        target_id = row[0]
    else:
        try:
            target_id = int(target)
        except ValueError:
            await update.message.reply_text("❌ Невірний формат. Використовуй @username або ID")
            return
    
    set_role(target_id, "officer")
    await update.message.reply_text(f"👑 Користувач призначений офіцером!")

async def inactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    
    days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
    inactive_users = get_inactive_users(days)
    
    if not inactive_users:
        await update.message.reply_text(f"ℹ️ Немає неактивних гравців за {days} днів")
        return
    
    text = f"💤 НЕАКТИВНІ {days}+ ДНІВ:\n\n"
    for uid, username, last_active in inactive_users[:20]:
        inactive_days = (now() - last_active) // 86400
        text += f"• {username or uid}: {inactive_days} днів\n"
    
    await update.message.reply_text(text)

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(get_all_users())
    officers = len(get_role_users("officer"))
    cur.execute("SELECT COUNT(*) FROM users WHERE last_active > ?", (now() - 86400,))
    active_today = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE ally_code IS NOT NULL")
    linked = cur.fetchone()[0]
    
    await update.message.reply_text(
        f"📊 СТАТИСТИКА ГІЛЬДІЇ\n\n"
        f"👥 Всього: {total}\n"
        f"👑 Офіцерів: {officers}\n"
        f"🔥 Активні сьогодні: {active_today}\n"
        f"🔗 Прив'язали Ally Code: {linked}"
    )

async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT id FROM users WHERE last_active > ?", (now() - 86400,))
    users = [row[0] for row in cur.fetchall()]
    
    if not users:
        await update.message.reply_text("ℹ️ Немає активних за 24 години")
        return
    
    mentions = [f"<a href='tg://user?id={u}'>🔥</a>" for u in users[:50]]
    await update.message.reply_text(f"🔥 АКТИВНІ ГРАВЦІ ({len(users)}):\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def officers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_role_users("officer")
    if not users:
        await update.message.reply_text("ℹ️ Немає призначених офіцерів")
        return
    mentions = [f"<a href='tg://user?id={u}'>👑</a>" for u in users]
    await update.message.reply_text("👑 ОФІЦЕРИ:\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

# Поради
async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tips = [
        "🎯 Завжди донать очки гільдії одразу після скидання",
        "⚔️ У Territory War став найсильніших персонажів на захист першими",
        "👑 Дарт Реван — топ персонаж, фарми його",
        "💎 Копи кристали на подвійні дропи",
        "🏆 Гайди та моди дивись на swgoh.gg",
        "📊 Перевіряй профіль суперника перед атакою в GAC"
    ]
    await update.message.reply_text(f"💡 ПОРАДА: {random.choice(tips)}")

# ========== ЗАПУСК ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("mystat", mystat))
    app.add_handler(CommandHandler("tip", tip))
    
    app.add_handler(CommandHandler("raid", raid))
    app.add_handler(CommandHandler("tw", tw))
    app.add_handler(CommandHandler("tb", tb))
    app.add_handler(CommandHandler("all", all_users))
    app.add_handler(CommandHandler("donate", donate))
    app.add_handler(CommandHandler("makeofficer", make_officer))
    app.add_handler(CommandHandler("inactive", inactive))
    
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("active", active))
    app.add_handler(CommandHandler("officers", officers))
    
    print("✅ Бот запущений!")
    app.run_polling()

if __name__ == "__main__":
    main()
