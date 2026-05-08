import os
import sqlite3
import time
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

TOKEN = os.environ.get("TOKEN")

# ========== БАЗА ДАНИХ ==========
conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER,
    chat_id INTEGER,
    username TEXT,
    role TEXT DEFAULT 'player',
    last_active INTEGER,
    ally_code TEXT,
    PRIMARY KEY (id, chat_id)
)
""")
conn.commit()

def now():
    return int(time.time())

def add_user(uid, chat_id, username):
    cur.execute("INSERT OR IGNORE INTO users (id, chat_id, username, role, last_active) VALUES (?, ?, ?, 'player', ?)",
                (uid, chat_id, username, now()))
    conn.commit()

def update_last_active(uid, chat_id):
    cur.execute("UPDATE users SET last_active=? WHERE id=? AND chat_id=?", (now(), uid, chat_id))
    conn.commit()

def get_all_users(chat_id):
    cur.execute("SELECT id FROM users WHERE chat_id=?", (chat_id,))
    return [row[0] for row in cur.fetchall()]

def is_officer(uid, chat_id):
    cur.execute("SELECT role FROM users WHERE id=? AND chat_id=?", (uid, chat_id))
    row = cur.fetchone()
    return row and row[0] == "officer"

def set_role(uid, chat_id, role):
    cur.execute("UPDATE users SET role=? WHERE id=? AND chat_id=?", (role, uid, chat_id))
    conn.commit()

def get_role_users(chat_id, role):
    cur.execute("SELECT id, username FROM users WHERE chat_id=? AND role=?", (chat_id, role))
    return cur.fetchall()

def get_inactive_users(chat_id, days):
    limit = now() - days * 86400
    cur.execute("SELECT id, username, last_active FROM users WHERE chat_id=? AND last_active < ?", (chat_id, limit))
    return cur.fetchall()

def has_officers(chat_id):
    cur.execute("SELECT COUNT(*) FROM users WHERE chat_id=? AND role='officer'", (chat_id,))
    count = cur.fetchone()[0]
    return count > 0

def get_all_chat_ids():
    cur.execute("SELECT DISTINCT chat_id FROM users")
    return [row[0] for row in cur.fetchall()]

# ========== SWGOH.GG API ==========
async def fetch_swgoh_player(ally_code: str):
    ally_code = ally_code.replace("-", "")
    if not ally_code.isdigit() or len(ally_code) not in (9,10):
        return None
    url = f"https://swgoh.gg/api/player/{ally_code}/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return {
                    "name": data.get("name", "Unknown"),
                    "galactic_power": data.get("galactic_power", 0),
                    "character_power": data.get("character_power", 0),
                    "ship_power": data.get("ship_power", 0),
                    "gac_rank": data.get("gac_rank", 0),
                    "arena_rank": data.get("arena_rank", 0),
                    "fleet_rank": data.get("fleet_arena_rank", 0),
                    "characters": data.get("characters", [])[:5],
                }
    except:
        return None

# ========== НАГАДУВАННЯ (планувальник) ==========
scheduler = BackgroundScheduler()
app = None  # буде встановлено в main()

async def send_daily_reminder():
    if app is None:
        return
    chat_ids = get_all_chat_ids()
    text = "💰 **НЕ ЗАБУДЬ ЗАДОНАТИТИ ОЧКИ ГІЛЬДІЇ!** 💰"
    for chat_id in chat_ids:
        try:
            await app.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print(f"Помилка надсилання нагадування в чат {chat_id}: {e}")

def schedule_reminder():
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(send_daily_reminder(), asyncio.get_event_loop()),
        CronTrigger(hour=20, minute=0)
    )
    scheduler.start()

# ========== КОМАНДИ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 SWGOH UA GUILD BOT\n\n"
        "👤 ОСНОВНІ КОМАНДИ:\n"
        "/register - реєстрація\n"
        "/mystat - моя статистика\n"
        "/setally <код> - прив'язати Ally Code\n"
        "/myprofile - мій профіль з swgoh.gg\n"
        "/profile @user - профіль іншого гравця\n\n"
        "👑 КОМАНДИ ОФІЦЕРІВ:\n"
        "/init - стати першим офіцером\n"
        "/raid - рейд\n"
        "/tw - Territory War\n"
        "/tb - Territory Battle\n"
        "/all - всіх покликати\n"
        "/donate - нагадати про донат\n"
        "/makeofficer @user - призначити офіцера\n"
        "/removeofficer @user - зняти офіцера\n"
        "/inactive [дні] - список неактивних\n\n"
        "📊 СТАТИСТИКА:\n"
        "/stats - статистика гільдії\n"
        "/active - активні сьогодні\n"
        "/officers - список офіцерів\n\n"
        "⏰ Щоденне нагадування про донат о 20:00"
    )

async def init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    if has_officers(chat_id):
        await update.message.reply_text("❌ У цій групі вже є офіцери. Звернись до них, щоб отримати роль.")
        return

    add_user(user_id, chat_id, username)
    set_role(user_id, chat_id, "officer")
    await update.message.reply_text("👑 Ти став першим офіцером цієї гільдії! Тепер ти можеш призначати інших через /makeofficer.")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    add_user(uid, chat_id, username)
    update_last_active(uid, chat_id)
    await update.message.reply_text("✅ Ти зареєстрований у гільдії!")

async def mystat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    cur.execute("SELECT role, last_active FROM users WHERE id=? AND chat_id=?", (uid, chat_id))
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

async def setally(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Приклад: `/setally 123456789`", parse_mode=ParseMode.MARKDOWN)
        return
    ally_code = context.args[0].replace("-", "")
    if not ally_code.isdigit() or len(ally_code) not in (9,10):
        await update.message.reply_text("❌ Невірний Ally Code (9-10 цифр)")
        return
    profile = await fetch_swgoh_player(ally_code)
    if not profile:
        await update.message.reply_text("❌ Профіль не знайдено на swgoh.gg. Перевір Ally Code.")
        return
    cur.execute("UPDATE users SET ally_code=? WHERE id=? AND chat_id=?", (ally_code, user_id, chat_id))
    conn.commit()
    await update.message.reply_text(f"✅ Ally Code `{ally_code}` прив'язаний до гравця *{profile['name']}*", parse_mode=ParseMode.MARKDOWN)

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    cur.execute("SELECT ally_code FROM users WHERE id=? AND chat_id=?", (user_id, chat_id))
    row = cur.fetchone()
    if not row or not row[0]:
        await update.message.reply_text("❌ Спочатку прив'яжи Ally Code через `/setally`", parse_mode=ParseMode.MARKDOWN)
        return
    profile = await fetch_swgoh_player(row[0])
    if not profile:
        await update.message.reply_text("❌ Не вдалося завантажити профіль. Спробуй пізніше.")
        return
    gac_division = ["Bronzium", "Chromium", "Aurodium", "Kyber"][min(3, profile['gac_rank'] // 1000)] if profile['gac_rank'] else "Unknown"
    text = (
        f"👤 *{profile['name']}*\n\n"
        f"📊 Galactic Power: `{profile['galactic_power']:,}`\n"
        f"⭐ Character GP: `{profile['character_power']:,}`\n"
        f"🚀 Ship GP: `{profile['ship_power']:,}`\n\n"
        f"🏆 GAC Division: *{gac_division}*\n"
        f"🎯 GAC Rank: `#{profile['gac_rank']}`\n"
        f"⚔️ Arena: `#{profile['arena_rank']}`\n"
        f"🛸 Fleet: `#{profile['fleet_rank']}`\n\n"
        f"⭐ Топ персонажі:\n"
    )
    for char in profile['characters']:
        text += f"• {char.get('name', '?')} ⭐{char.get('stars', 0)}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Приклад: `/profile @username`", parse_mode=ParseMode.MARKDOWN)
        return
    username = context.args[0].lstrip("@")
    chat_id = update.effective_chat.id
    cur.execute("SELECT ally_code FROM users WHERE username LIKE ? AND chat_id=?", (f"%{username}%", chat_id))
    row = cur.fetchone()
    if not row or not row[0]:
        await update.message.reply_text(f"❌ Гравець @{username} не прив'язав Ally Code або не зареєстрований.")
        return
    profile = await fetch_swgoh_player(row[0])
    if not profile:
        await update.message.reply_text("❌ Не вдалося завантажити профіль")
        return
    await update.message.reply_text(f"👤 *{profile['name']}* | GP: {profile['galactic_power']:,} | GAC: #{profile['gac_rank']}", parse_mode=ParseMode.MARKDOWN)

async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text("🚨 РЕЙД ПОЧАВСЯ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text("⚔️ TERRITORY WAR!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>🌌</a>" for u in users[:50]]
    await update.message.reply_text("🌌 TERRITORY BATTLE!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>👤</a>" for u in users[:30]]
    await update.message.reply_text("🔥 УВАГА ГІЛЬДІЇ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>💰</a>" for u in users[:50]]
    await update.message.reply_text("💰 НЕ ЗАБУДЬ ЗАДОНАТИТИ ОЧКИ ГІЛЬДІЇ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def make_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери можуть призначати офіцерів")
        return
    if not context.args:
        await update.message.reply_text("❌ Використання: /makeofficer @username або /makeofficer telegram_id")
        return
    target = context.args[0]
    if target.startswith("@"):
        username = target[1:]
        cur.execute("SELECT id FROM users WHERE username LIKE ? AND chat_id=?", (f"%{username}%", chat_id))
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
    set_role(target_id, chat_id, "officer")
    await update.message.reply_text(f"👑 Користувач призначений офіцером!")

async def remove_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери можуть знімати офіцерів")
        return
    if not context.args:
        await update.message.reply_text("❌ Використання: /removeofficer @username або /removeofficer telegram_id")
        return
    target = context.args[0]
    if target.startswith("@"):
        username = target[1:]
        cur.execute("SELECT id FROM users WHERE username LIKE ? AND chat_id=?", (f"%{username}%", chat_id))
        row = cur.fetchone()
        if not row:
            await update.message.reply_text("❌ Користувача не знайдено")
            return
        target_id = row[0]
    else:
        try:
            target_id = int(target)
        except ValueError:
            await update.message.reply_text("❌ Невірний формат")
            return
    officers = get_role_users(chat_id, "officer")
    if len(officers) == 1 and officers[0][0] == target_id:
        await update.message.reply_text("❌ Не можна зняти єдиного офіцера. Спочатку признач іншого через /makeofficer.")
        return
    set_role(target_id, chat_id, "player")
    await update.message.reply_text(f"👤 Користувач більше не офіцер.")

async def inactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_officer(update.effective_user.id, chat_id):
        await update.message.reply_text("❌ Тільки офіцери")
        return
    days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
    inactive_users = get_inactive_users(chat_id, days)
    if not inactive_users:
        await update.message.reply_text(f"ℹ️ Немає неактивних гравців за {days} днів")
        return
    text = f"💤 НЕАКТИВНІ {days}+ ДНІВ:\n\n"
    for uid, username, last_active in inactive_users[:20]:
        inactive_days = (now() - last_active) // 86400
        name = username or str(uid)
        text += f"• {name}: {inactive_days} днів\n"
    await update.message.reply_text(text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    total = len(get_all_users(chat_id))
    officers = len(get_role_users(chat_id, "officer"))
    cur.execute("SELECT COUNT(*) FROM users WHERE chat_id=? AND last_active > ?", (chat_id, now() - 86400))
    active_today = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE chat_id=? AND ally_code IS NOT NULL", (chat_id,))
    linked = cur.fetchone()[0]
    await update.message.reply_text(
        f"📊 СТАТИСТИКА ГІЛЬДІЇ\n\n"
        f"👥 Всього: {total}\n"
        f"👑 Офіцерів: {officers}\n"
        f"🔥 Активні сьогодні: {active_today}\n"
        f"🔗 Прив'язали Ally Code: {linked}"
    )

async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cur.execute("SELECT id FROM users WHERE chat_id=? AND last_active > ?", (chat_id, now() - 86400))
    users = [row[0] for row in cur.fetchall()]
    if not users:
        await update.message.reply_text("ℹ️ Немає активних за 24 години")
        return
    mentions = [f"<a href='tg://user?id={u}'>🔥</a>" for u in users[:50]]
    await update.message.reply_text(f"🔥 АКТИВНІ ГРАВЦІ ({len(users)}):\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def officers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = get_role_users(chat_id, "officer")
    if not rows:
        await update.message.reply_text("ℹ️ Немає призначених офіцерів. Використай /init, щоб стати першим.")
        return
    officer_list = []
    for uid, username in rows:
        if username:
            officer_list.append(f"👑 @{username}")
        else:
            officer_list.append(f"👑 Користувач")
    await update.message.reply_text("👑 ОФІЦЕРИ:\n" + "\n".join(officer_list))

# ========== ЗАПУСК ==========
def main():
    global app
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("init", init))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("mystat", mystat))
    app.add_handler(CommandHandler("setally", setally))
    app.add_handler(CommandHandler("myprofile", myprofile))
    app.add_handler(CommandHandler("profile", profile_cmd))

    app.add_handler(CommandHandler("raid", raid))
    app.add_handler(CommandHandler("tw", tw))
    app.add_handler(CommandHandler("tb", tb))
    app.add_handler(CommandHandler("all", all_users))
    app.add_handler(CommandHandler("donate", donate))
    app.add_handler(CommandHandler("makeofficer", make_officer))
    app.add_handler(CommandHandler("removeofficer", remove_officer))
    app.add_handler(CommandHandler("inactive", inactive))

    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("active", active))
    app.add_handler(CommandHandler("officers", officers))

    # Запускаємо планувальник нагадувань
    schedule_reminder()

    print("✅ Бот запущений! Готовий працювати в багатьох групах.")
    app.run_polling()

if __name__ == "__main__":
    main()