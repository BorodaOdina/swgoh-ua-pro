import os
import sqlite3
import time
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode

TOKEN = os.environ.get("TOKEN")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]  # ID админов группы

# Асинхронное SQLite соединение
import aiosqlite

# Константы
CACHE_TTL = 3600  # Кеш на 1 час
GAC_DIVISIONS = {
    0: "Bronzium", 1: "Bronzium", 2: "Bronzium",
    3: "Chromium", 4: "Chromium", 5: "Chromium",
    6: "Aurodium", 7: "Aurodium", 8: "Aurodium",
    9: "Kyber", 10: "Kyber", 11: "Kyber"
}

# Кеш для API запросов
cache: Dict[str, tuple[Any, float]] = {}

def get_from_cache(key: str) -> Optional[Any]:
    if key in cache:
        data, timestamp = cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
    return None

def set_to_cache(key: str, data: Any):
    cache[key] = (data, time.time())

# SQL запросы
async def init_db():
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                ally_code TEXT,
                role TEXT DEFAULT 'player',
                last_active INTEGER,
                is_banned BOOLEAN DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                title TEXT,
                schedule TEXT,
                last_sent INTEGER
            )
        """)
        await db.commit()

async def add_user(uid: int, username: str = None):
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, role, last_active) VALUES (?, ?, 'player', ?)",
            (uid, username, int(time.time()))
        )
        await db.commit()

async def update_ally_code(uid: int, ally_code: str):
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("UPDATE users SET ally_code=? WHERE id=?", (ally_code, uid))
        await db.commit()

async def get_user(uid: int):
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id, username, ally_code, role, last_active, is_banned FROM users WHERE id=?", (uid,)) as cursor:
            return await cursor.fetchone()

async def get_all_users():
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id FROM users WHERE is_banned=0") as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def get_role_users(role: str):
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id FROM users WHERE role=? AND is_banned=0", (role,)) as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def update_role(uid: int, role: str, executor_id: int):
    executor = await get_user(executor_id)
    if not executor or (executor[3] != "officer" and executor_id not in ADMIN_IDS):
        return False, "Нет прав!"
    
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
        await db.commit()
    return True, f"✅ Роль изменена на {role}"

async def update_last_active(uid: int):
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("UPDATE users SET last_active=? WHERE id=?", (int(time.time()), uid))
        await db.commit()

async def ban_user(uid: int, executor_id: int):
    executor = await get_user(executor_id)
    if not executor or (executor[3] != "officer" and executor_id not in ADMIN_IDS):
        return False
    
    async with aiosqlite.connect("db.sqlite") as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE id=?", (uid,))
        await db.commit()
    return True

# API SWGOH.gg
async def fetch_swgoh_data(ally_code: str) -> Optional[Dict]:
    cache_key = f"swgoh_{ally_code}"
    cached = get_from_cache(cache_key)
    if cached:
        return cached
    
    try:
        async with aiohttp.ClientSession() as session:
            # Поиск игрока
            async with session.get(f"https://swgoh.gg/api/player/{ally_code}/") as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                result = {
                    "name": data.get("name", "Unknown"),
                    "galactic_power": data.get("galactic_power", 0),
                    "character_power": data.get("character_power", 0),
                    "ship_power": data.get("ship_power", 0),
                    "gac_rank": data.get("gac_rank", 0),
                    "arena_rank": data.get("arena_rank", 0),
                    "fleet_arena_rank": data.get("fleet_arena_rank", 0),
                    "characters": data.get("characters", [])[:5],  # Топ 5 персонажей
                }
                set_to_cache(cache_key, result)
                return result
    except Exception as e:
        print(f"API error: {e}")
        return None

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇺🇦 **SWGOH UA Guild Bot**\n\n"
        "**Основные команды:**\n"
        "/register - регистрация в гильдии\n"
        "/setally `123456789` - привязать Ally Code\n"
        "/myprofile - мой профиль\n"
        "/profile `@user` - профиль игрока\n\n"
        "**Уведомления гильдии (только офицеры):**\n"
        "/raid - объявить рейд\n"
        "/tw - Territory War\n"
        "/tb - Territory Battle\n"
        "/donate - напомнить о донате\n"
        "/all - призвать всех\n\n"
        "**Статистика:**\n"
        "/stats - статистика гильдии\n"
        "/active - активные сегодня\n"
        "/inactive `days` - неактивные игроки\n\n"
        "**Советы:**\n"
        "/tip - случайный совет\n"
        "/gactip - совет по GAC\n\n"
        "**Администрирование (офицеры):**\n"
        "/setrole `@user officer/player` - изменить роль\n"
        "/ban `@user` - заблокировать",
        parse_mode=ParseMode.MARKDOWN
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    await add_user(uid, username)
    await update_last_active(uid)
    await update.message.reply_text("✅ Ты зарегистрирован в гильдии!\nИспользуй `/setally 123456789` чтобы привязать профиль", parse_mode=ParseMode.MARKDOWN)

async def set_ally(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Пример: `/setally 123456789`", parse_mode=ParseMode.MARKDOWN)
        return
    
    ally_code = context.args[0].replace("-", "")
    if not ally_code.isdigit() or len(ally_code) not in [9, 10]:
        await update.message.reply_text("❌ Неверный Ally Code (9-10 цифр)")
        return
    
    uid = update.effective_user.id
    await update_ally_code(uid, ally_code)
    
    # Проверка существования профиля
    profile = await fetch_swgoh_data(ally_code)
    if profile:
        await update.message.reply_text(f"✅ Ally Code привязан!\nИгрок: {profile['name']}\nGP: {profile['galactic_power']:,}")
    else:
        await update.message.reply_text("⚠️ Ally Code сохранен, но профиль на swgoh.gg не найден")

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = await get_user(uid)
    if not user:
        await update.message.reply_text("❌ Сначала /register")
        return
    
    if not user[2]:  # ally_code
        await update.message.reply_text("❌ Не привязан Ally Code. Используй `/setally`", parse_mode=ParseMode.MARKDOWN)
        return
    
    profile = await fetch_swgoh_data(user[2])
    if not profile:
        await update.message.reply_text("❌ Не удалось загрузить профиль с swgoh.gg")
        return
    
    # Определение GAC дивизиона
    gac_division = GAC_DIVISIONS.get(profile['gac_rank'] // 1000, "Unknown")
    
    text = (
        f"👤 **{profile['name']}**\n\n"
        f"📊 **Galactic Power:** {profile['galactic_power']:,}\n"
        f"⭐ **Character GP:** {profile['character_power']:,}\n"
        f"🚀 **Ship GP:** {profile['ship_power']:,}\n\n"
        f"🏆 **GAC Division:** {gac_division}\n"
        f"🎯 **GAC Rank:** #{profile['gac_rank']}\n"
        f"⚔️ **Arena Rank:** #{profile['arena_rank']}\n"
        f"🛸 **Fleet Rank:** #{profile['fleet_arena_rank']}\n\n"
        f"⭐ **Top Characters:**\n"
    )
    
    for char in profile['characters']:
        text += f"• {char.get('name', 'Unknown')} ⭐{char.get('stars', 0)}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Пример: `/profile @username`", parse_mode=ParseMode.MARKDOWN)
        return
    
    username = context.args[0].lstrip("@")
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id, ally_code FROM users WHERE username LIKE ? AND is_banned=0", (f"%{username}%",)) as cursor:
            user = await cursor.fetchone()
    
    if not user or not user[1]:
        await update.message.reply_text("❌ Игрок не найден или не привязал Ally Code")
        return
    
    profile = await fetch_swgoh_data(user[1])
    if not profile:
        await update.message.reply_text("❌ Не удалось загрузить профиль")
        return
    
    await update.message.reply_text(
        f"👤 **{profile['name']}**\nGP: {profile['galactic_power']:,}\nGAC: #{profile['gac_rank']}",
        parse_mode=ParseMode.MARKDOWN
    )

# Уведомления гильдии (только офицеры)
async def is_officer(uid: int) -> bool:
    user = await get_user(uid)
    return user and (user[3] == "officer" or uid in ADMIN_IDS)

async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Только офицеры могут объявлять рейд")
        return
    
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]  # Ограничение 50 упоминаний
    await update.message.reply_text("🚨 **РЕЙД НАЧАЛСЯ!**\nВСЕ В БОЙ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Только офицеры")
        return
    
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text("⚔️ **TERRITORY WAR!**\nВСЕ НА БИТВУ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Только офицеры")
        return
    
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>🌌</a>" for u in users[:50]]
    await update.message.reply_text("🌌 **TERRITORY BATTLE!**\nВЫПОЛНЯЕМ МИССИИ!\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Только офицеры")
        return
    
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>💰</a>" for u in users[:50]]
    await update.message.reply_text("💰 **НЕ ЗАБУДЬТЕ СДОНАТИТЬ ОЧКИ ГИЛЬДИИ!**\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_officer(update.effective_user.id):
        await update.message.reply_text("❌ Только офицеры")
        return
    
    users = await get_all_users()
    mentions = [f"<a href='tg://user?id={u}'>👤</a>" for u in users[:30]]
    await update.message.reply_text("🔥 **ВНИМАНИЕ ГИЛЬДИИ!**\n" + " ".join(mentions) + "\n\nВажное объявление в чате!", parse_mode=ParseMode.HTML)

# Статистика
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_banned=0") as cursor:
            total = (await cursor.fetchone())[0]
        
        async with db.execute("SELECT COUNT(*) FROM users WHERE role='officer' AND is_banned=0") as cursor:
            officers = (await cursor.fetchone())[0]
        
        async with db.execute("SELECT COUNT(*) FROM users WHERE last_active > ? AND is_banned=0", (int(time.time()) - 86400,)) as cursor:
            active = (await cursor.fetchone())[0]
        
        async with db.execute("SELECT COUNT(*) FROM users WHERE ally_code IS NOT NULL AND is_banned=0") as cursor:
            linked = (await cursor.fetchone())[0]
    
    await update.message.reply_text(
        f"📊 **СТАТИСТИКА ГИЛЬДИИ**\n\n"
        f"👥 Всего: {total}\n"
        f"👑 Офицеров: {officers}\n"
        f"🔥 Активны сегодня: {active}\n"
        f"🔗 Привязали Ally Code: {linked}\n"
        f"💤 Неактивны 3+ дня: {await get_inactive_count(3)}",
        parse_mode=ParseMode.MARKDOWN
    )

async def get_inactive_count(days: int) -> int:
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE last_active < ? AND is_banned=0", (int(time.time()) - days * 86400,)) as cursor:
            return (await cursor.fetchone())[0]

async def active_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id FROM users WHERE last_active > ? AND is_banned=0", (int(time.time()) - 86400,)) as cursor:
            users = [row[0] for row in await cursor.fetchall()]
    
    if not users:
        await update.message.reply_text("ℹ️ Нет активных игроков за последние 24 часа")
        return
    
    mentions = [f"<a href='tg://user?id={u}'>🔥</a>" for u in users[:50]]
    await update.message.reply_text(f"🔥 **АКТИВНЫЕ ИГРОКИ** ({len(users)}):\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def inactive_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
    
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id, username, last_active FROM users WHERE last_active < ? AND is_banned=0", (int(time.time()) - days * 86400,)) as cursor:
            users = await cursor.fetchall()
    
    if not users:
        await update.message.reply_text(f"ℹ️ Нет неактивных игроков за {days} дней")
        return
    
    text = f"💤 **НЕАКТИВНЫЕ {days}+ ДНЕЙ:**\n\n"
    for uid, username, last_active in users[:20]:
        inactive_days = (int(time.time()) - last_active) // 86400
        text += f"• {username or uid}: {inactive_days} дней\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# Советы
TIPS = [
    "🎯 Всегда донать очки гильдии сразу после сброса",
    "⚔️ В TW ставь сильнейших на защиту первыми",
    "👑 Дарт Реван - топ персонаж, фарми его",
    "💎 Копи кристаллы на двойные дропы",
    "🎮 Играй каждый раунд GAC, даже при проигрыше",
    "🛡️ В TB выполняй миссии с требуемыми персонажами"
]

GAC_TIPS = [
    "🏆 Ставь сложную защиту на переднюю линию",
    "⚡ Используй счетчик Speed в модах",
    "🎯 Атакуй сектора с меньшим количеством очков",
    "📊 Смотри профиль противника перед боем"
]

async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tip = random.choice(TIPS)
    await update.message.reply_text(f"💡 **СОВЕТ ДНЯ:**\n\n{tip}", parse_mode=ParseMode.MARKDOWN)

async def gac_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tip = random.choice(GAC_TIPS)
    await update.message.reply_text(f"🏆 **GAC СОВЕТ:**\n\n{tip}", parse_mode=ParseMode.MARKDOWN)

# Администрирование
async def set_role_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Пример: `/setrole @username officer`", parse_mode=ParseMode.MARKDOWN)
        return
    
    username = context.args[0].lstrip("@")
    new_role = context.args[1].lower()
    
    if new_role not in ["player", "officer"]:
        await update.message.reply_text("❌ Роль может быть: player или officer")
        return
    
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id FROM users WHERE username LIKE ?", (f"%{username}%",)) as cursor:
            user = await cursor.fetchone()
    
    if not user:
        await update.message.reply_text("❌ Игрок не найден")
        return
    
    success, msg = await update_role(user[0], new_role, update.effective_user.id)
    await update.message.reply_text(msg)

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Пример: `/ban @username`", parse_mode=ParseMode.MARKDOWN)
        return
    
    username = context.args[0].lstrip("@")
    async with aiosqlite.connect("db.sqlite") as db:
        async with db.execute("SELECT id FROM users WHERE username LIKE ?", (f"%{username}%",)) as cursor:
            user = await cursor.fetchone()
    
    if not user:
        await update.message.reply_text("❌ Игрок не найден")
        return
    
    if await ban_user(user[0], update.effective_user.id):
        await update.message.reply_text("✅ Игрок заблокирован")
    else:
        await update.message.reply_text("❌ Нет прав")

# Основная функция
async def main():
    await init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # Пользовательские команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("setally", set_ally))
    app.add_handler(CommandHandler("myprofile", my_profile))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("tip", tip_command))
    app.add_handler(CommandHandler("gactip", gac_tip))
    
    # Статистика
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("active", active_command))
    app.add_handler(CommandHandler("inactive", inactive_command))
    app.add_handler(CommandHandler("mystat", my_profile))  # Алиас
    
    # Команды офицеров
    app.add_handler(CommandHandler("raid", raid))
    app.add_handler(CommandHandler("tw", tw_command))
    app.add_handler(CommandHandler("tb", tb_command))
    app.add_handler(CommandHandler("donate", donate_command))
    app.add_handler(CommandHandler("all", all_command))
    
    # Администрирование
    app.add_handler(CommandHandler("setrole", set_role_command))
    app.add_handler(CommandHandler("ban", ban_command))
    
    print("Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
