import os
import sqlite3
import time
import random
import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
    language TEXT DEFAULT 'ua',
    PRIMARY KEY (id, chat_id)
)
""")
conn.commit()

# ========== ТЕКСТИ КОМАНД (МОВИ) ==========
TEXTS = {
    'ua': {
        'start': "🤖 SWGOH UA GUILD BOT\n\n"
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
                 "/energy - нагадати про енергію\n"
                 "/makeofficer @user - призначити офіцера\n"
                 "/removeofficer @user - зняти офіцера\n"
                 "/inactive [дні] - список неактивних\n\n"
                 "📊 СТАТИСТИКА:\n"
                 "/stats - статистика гільдії\n"
                 "/active - активні сьогодні\n"
                 "/officers - список офіцерів\n\n"
                 "⏰ Щоденне нагадування про енергію о 20:00\n\n"
                 "🌐 Змінити мову: /language\n"
                 "💙 Підтримати проект: /support",
        'register_ok': "✅ Ти зареєстрований у гільдії!",
        'not_registered': "❌ Спочатку /register",
        'only_officer': "❌ Тільки офіцери",
        'raid': "🚨 РЕЙД ПОЧАВСЯ!\n",
        'tw': "⚔️ TERRITORY WAR!\n",
        'tb': "🌌 TERRITORY BATTLE!\n",
        'all': "🔥 УВАГА ГІЛЬДІЇ!\n",
        'energy': "🔋 НЕ ЗАБУДЬ СДАТИ ЕНЕРГІЮ ГІЛЬДІЇ!\n",
        'no_officers': "ℹ️ Немає призначених офіцерів. Використай /init, щоб стати першим.",
        'officers': "👑 ОФІЦЕРИ:\n",
        'no_active': "ℹ️ Немає активних за 24 години",
        'no_inactive': "ℹ️ Немає неактивних гравців за {days} днів",
        'inactive_title': "💤 НЕАКТИВНІ {days}+ ДНІВ:\n\n",
        'stats': "📊 СТАТИСТИКА ГІЛЬДІЇ\n\n"
                 "👥 Всього: {total}\n"
                 "👑 Офіцерів: {officers}\n"
                 "🔥 Активні сьогодні: {active_today}\n"
                 "🔗 Прив'язали Ally Code: {linked}",
        'setally_usage': "❌ Приклад: `/setally 123456789`",
        'invalid_ally': "❌ Невірний Ally Code (9-10 цифр)",
        'ally_not_found': "❌ Профіль не знайдено на swgoh.gg. Перевір Ally Code.",
        'ally_saved': "✅ Ally Code `{code}` прив'язаний до гравця *{name}*",
        'profile_not_found': "❌ Не вдалося завантажити профіль. Спробуй пізніше.",
        'no_ally': "❌ Спочатку прив'яжи Ally Code через `/setally`",
        'user_no_ally': "❌ Гравець не прив'язав Ally Code",
        'lang_changed': "🌐 Мову змінено на українську",
        'support': "💙 Підтримати розробку бота можна тут: [Monobank](https://send.monobank.ua/jar/9DMsxWr16b)\n\nДякуємо за підтримку! 🙏",
    },
    'ru': {
        'start': "🤖 SWGOH GUILD BOT\n\n"
                 "👤 ОСНОВНЫЕ КОМАНДЫ:\n"
                 "/register - регистрация\n"
                 "/mystat - моя статистика\n"
                 "/setally <код> - привязать Ally Code\n"
                 "/myprofile - мой профиль с swgoh.gg\n"
                 "/profile @user - профиль другого игрока\n\n"
                 "👑 КОМАНДЫ ОФИЦЕРОВ:\n"
                 "/init - стать первым офицером\n"
                 "/raid - рейд\n"
                 "/tw - Territory War\n"
                 "/tb - Territory Battle\n"
                 "/all - призвать всех\n"
                 "/energy - напомнить об энергии\n"
                 "/makeofficer @user - назначить офицера\n"
                 "/removeofficer @user - снять офицера\n"
                 "/inactive [дни] - список неактивных\n\n"
                 "📊 СТАТИСТИКА:\n"
                 "/stats - статистика гильдии\n"
                 "/active - активные сегодня\n"
                 "/officers - список офицеров\n\n"
                 "⏰ Ежедневное напоминание об энергии в 20:00\n\n"
                 "🌐 Сменить язык: /language\n"
                 "💙 Поддержать проект: /support",
        'register_ok': "✅ Ты зарегистрирован в гильдии!",
        'not_registered': "❌ Сначала /register",
        'only_officer': "❌ Только офицеры",
        'raid': "🚨 РЕЙД НАЧАЛСЯ!\n",
        'tw': "⚔️ TERRITORY WAR!\n",
        'tb': "🌌 TERRITORY BATTLE!\n",
        'all': "🔥 ВНИМАНИЕ ГИЛЬДИИ!\n",
        'energy': "🔋 НЕ ЗАБУДЬ СДАТЬ ЭНЕРГИЮ ГИЛЬДИИ!\n",
        'no_officers': "ℹ️ Нет назначенных офицеров. Используй /init, чтобы стать первым.",
        'officers': "👑 ОФИЦЕРЫ:\n",
        'no_active': "ℹ️ Нет активных за 24 часа",
        'no_inactive': "ℹ️ Нет неактивных игроков за {days} дней",
        'inactive_title': "💤 НЕАКТИВНЫЕ {days}+ ДНЕЙ:\n\n",
        'stats': "📊 СТАТИСТИКА ГИЛЬДИИ\n\n"
                 "👥 Всего: {total}\n"
                 "👑 Офицеров: {officers}\n"
                 "🔥 Активны сегодня: {active_today}\n"
                 "🔗 Привязали Ally Code: {linked}",
        'setally_usage': "❌ Пример: `/setally 123456789`",
        'invalid_ally': "❌ Неверный Ally Code (9-10 цифр)",
        'ally_not_found': "❌ Профиль не найден на swgoh.gg. Проверь Ally Code.",
        'ally_saved': "✅ Ally Code `{code}` привязан к игроку *{name}*",
        'profile_not_found': "❌ Не удалось загрузить профиль. Попробуй позже.",
        'no_ally': "❌ Сначала привяжи Ally Code через `/setally`",
        'user_no_ally': "❌ Игрок не привязал Ally Code",
        'lang_changed': "🌐 Язык изменён на русский",
        'support': "💙 Поддержать разработку бота можно здесь: [Monobank](https://send.monobank.ua/jar/9DMsxWr16b)\n\nСпасибо за поддержку! 🙏",
    },
    'en': {
        'start': "🤖 SWGOH GUILD BOT\n\n"
                 "👤 BASIC COMMANDS:\n"
                 "/register - register in the guild\n"
                 "/mystat - my statistics\n"
                 "/setally <code> - link Ally Code\n"
                 "/myprofile - my profile from swgoh.gg\n"
                 "/profile @user - another player's profile\n\n"
                 "👑 OFFICER COMMANDS:\n"
                 "/init - become the first officer\n"
                 "/raid - raid announcement\n"
                 "/tw - Territory War\n"
                 "/tb - Territory Battle\n"
                 "/all - mention everyone\n"
                 "/energy - remind about guild energy\n"
                 "/makeofficer @user - appoint an officer\n"
                 "/removeofficer @user - remove an officer\n"
                 "/inactive [days] - list of inactive players\n\n"
                 "📊 STATISTICS:\n"
                 "/stats - guild statistics\n"
                 "/active - active today\n"
                 "/officers - list of officers\n\n"
                 "⏰ Daily energy reminder at 8:00 PM\n\n"
                 "🌐 Change language: /language\n"
                 "💙 Support the project: /support",
        'register_ok': "✅ You are registered in the guild!",
        'not_registered': "❌ First use /register",
        'only_officer': "❌ Officers only",
        'raid': "🚨 RAID STARTED!\n",
        'tw': "⚔️ TERRITORY WAR!\n",
        'tb': "🌌 TERRITORY BATTLE!\n",
        'all': "🔥 GUILD ATTENTION!\n",
        'energy': "🔋 DON'T FORGET TO DONATE GUILD ENERGY!\n",
        'no_officers': "ℹ️ No officers assigned. Use /init to become the first.",
        'officers': "👑 OFFICERS:\n",
        'no_active': "ℹ️ No active players in the last 24 hours",
        'no_inactive': "ℹ️ No inactive players for {days} days",
        'inactive_title': "💤 INACTIVE {days}+ DAYS:\n\n",
        'stats': "📊 GUILD STATISTICS\n\n"
                 "👥 Total: {total}\n"
                 "👑 Officers: {officers}\n"
                 "🔥 Active today: {active_today}\n"
                 "🔗 Linked Ally Code: {linked}",
        'setally_usage': "❌ Example: `/setally 123456789`",
        'invalid_ally': "❌ Invalid Ally Code (9-10 digits)",
        'ally_not_found': "❌ Profile not found on swgoh.gg. Check Ally Code.",
        'ally_saved': "✅ Ally Code `{code}` linked to player *{name}*",
        'profile_not_found': "❌ Could not load profile. Try again later.",
        'no_ally': "❌ First link your Ally Code via `/setally`",
        'user_no_ally': "❌ Player has not linked Ally Code",
        'lang_changed': "🌐 Language changed to English",
        'support': "💙 Support the bot development here: [Monobank](https://send.monobank.ua/jar/9DMsxWr16b)\n\nThank you for your support! 🙏",
    }
}

def get_text(uid, chat_id, key, **kwargs):
    cur.execute("SELECT language FROM users WHERE id=? AND chat_id=?", (uid, chat_id))
    row = cur.fetchone()
    lang = row[0] if row else 'ua'
    text = TEXTS.get(lang, TEXTS['ua']).get(key, TEXTS['ua'][key])
    return text.format(**kwargs) if kwargs else text

def set_language(uid, chat_id, lang):
    cur.execute("UPDATE users SET language=? WHERE id=? AND chat_id=?", (lang, uid, chat_id))
    conn.commit()

def now():
    return int(time.time())

def add_user(uid, chat_id, username, language='ua'):
    cur.execute("INSERT OR IGNORE INTO users (id, chat_id, username, role, last_active, language) VALUES (?, ?, ?, 'player', ?, ?)",
                (uid, chat_id, username, now(), language))
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
            async with session.get(url, timeout=10) as resp:
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

# ========== НАГАДУВАННЯ ==========
scheduler = BackgroundScheduler()
app = None

async def send_daily_reminder():
    if app is None:
        return
    chat_ids = get_all_chat_ids()
    for chat_id in chat_ids:
        try:
            cur.execute("SELECT language FROM users WHERE chat_id=? LIMIT 1", (chat_id,))
            row = cur.fetchone()
            lang = row[0] if row else 'ua'
            energy_text = TEXTS.get(lang, TEXTS['ua']).get('energy', "🔋 НЕ ЗАБУДЬ СДАТИ ЕНЕРГІЮ!\n")
            await app.bot.send_message(chat_id=chat_id, text=energy_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print(f"Помилка надсилання нагадування в чат {chat_id}: {e}")

def schedule_reminder():
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(send_daily_reminder(), asyncio.get_event_loop()),
        CronTrigger(hour=20, minute=0)
    )
    scheduler.start()

# ========== КОМАНДИ ==========
async def language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌐 Оберіть мову / Выберите язык / Choose language:", reply_markup=reply_markup)

async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = query.data.split("_")[1]
    set_language(user_id, chat_id, lang)
    start_text = get_text(user_id, chat_id, 'start')
    await query.edit_message_text(start_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    cur.execute("SELECT language FROM users WHERE id=? AND chat_id=?", (user_id, chat_id))
    row = cur.fetchone()
    if not row:
        await language_choice(update, context)
        return
    await update.message.reply_text(get_text(user_id, chat_id, 'start'), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await update.message.reply_text(get_text(user_id, chat_id, 'support'), parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

async def init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    if has_officers(chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
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
    await update.message.reply_text(get_text(uid, chat_id, 'register_ok'))

async def mystat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    cur.execute("SELECT role, last_active FROM users WHERE id=? AND chat_id=?", (uid, chat_id))
    row = cur.fetchone()
    if not row:
        await update.message.reply_text(get_text(uid, chat_id, 'not_registered'))
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

# ========== SWGOH КОМАНДИ ==========
async def setally(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(get_text(user_id, chat_id, 'setally_usage'), parse_mode=ParseMode.MARKDOWN)
        return
    ally_code = context.args[0].replace("-", "")
    if not ally_code.isdigit() or len(ally_code) not in (9,10):
        await update.message.reply_text(get_text(user_id, chat_id, 'invalid_ally'))
        return
    profile = await fetch_swgoh_player(ally_code)
    if not profile:
        await update.message.reply_text(get_text(user_id, chat_id, 'ally_not_found'))
        return
    cur.execute("UPDATE users SET ally_code=? WHERE id=? AND chat_id=?", (ally_code, user_id, chat_id))
    conn.commit()
    await update.message.reply_text(get_text(user_id, chat_id, 'ally_saved', code=ally_code, name=profile['name']), parse_mode=ParseMode.MARKDOWN)

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    cur.execute("SELECT ally_code FROM users WHERE id=? AND chat_id=?", (user_id, chat_id))
    row = cur.fetchone()
    if not row or not row[0]:
        await update.message.reply_text(get_text(user_id, chat_id, 'no_ally'), parse_mode=ParseMode.MARKDOWN)
        return
    profile = await fetch_swgoh_player(row[0])
    if not profile:
        await update.message.reply_text(get_text(user_id, chat_id, 'profile_not_found'))
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
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Приклад: `/profile @username` або `/profile 123456789`", parse_mode=ParseMode.MARKDOWN)
        return
    target = context.args[0]
    ally_code = None
    if target.startswith("@"):
        username = target[1:]
        cur.execute("SELECT ally_code FROM users WHERE username LIKE ? AND chat_id=?", (f"%{username}%", chat_id))
        row = cur.fetchone()
        if row and row[0]:
            ally_code = row[0]
        else:
            await update.message.reply_text(get_text(user_id, chat_id, 'user_no_ally'))
            return
    else:
        ally_code = target.replace("-", "")
        if not ally_code.isdigit() or len(ally_code) not in (9,10):
            await update.message.reply_text(get_text(user_id, chat_id, 'invalid_ally'))
            return
    profile = await fetch_swgoh_player(ally_code)
    if not profile:
        await update.message.reply_text(get_text(user_id, chat_id, 'ally_not_found'))
        return
    await update.message.reply_text(f"👤 *{profile['name']}* | GP: {profile['galactic_power']:,} | GAC: #{profile['gac_rank']}", parse_mode=ParseMode.MARKDOWN)

# ========== КОМАНДИ ОФІЦЕРІВ ==========
async def energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>🔋</a>" for u in users[:50]]
    await update.message.reply_text(get_text(user_id, chat_id, 'energy') + " ".join(mentions), parse_mode=ParseMode.HTML)

async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text(get_text(user_id, chat_id, 'raid') + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>⚔️</a>" for u in users[:50]]
    await update.message.reply_text(get_text(user_id, chat_id, 'tw') + " ".join(mentions), parse_mode=ParseMode.HTML)

async def tb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>🌌</a>" for u in users[:50]]
    await update.message.reply_text(get_text(user_id, chat_id, 'tb') + " ".join(mentions), parse_mode=ParseMode.HTML)

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    users = get_all_users(chat_id)
    mentions = [f"<a href='tg://user?id={u}'>👤</a>" for u in users[:30]]
    await update.message.reply_text(get_text(user_id, chat_id, 'all') + " ".join(mentions), parse_mode=ParseMode.HTML)

async def make_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
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
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
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
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
    inactive_users = get_inactive_users(chat_id, days)
    if not inactive_users:
        await update.message.reply_text(get_text(user_id, chat_id, 'no_inactive', days=days))
        return
    text = get_text(user_id, chat_id, 'inactive_title', days=days)
    for uid, username, last_active in inactive_users[:20]:
        inactive_days = (now() - last_active) // 86400
        name = username or str(uid)
        text += f"• {name}: {inactive_days} днів\n"
    await update.message.reply_text(text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    total = len(get_all_users(chat_id))
    officers = len(get_role_users(chat_id, "officer"))
    cur.execute("SELECT COUNT(*) FROM users WHERE chat_id=? AND last_active > ?", (chat_id, now() - 86400))
    active_today = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE chat_id=? AND ally_code IS NOT NULL", (chat_id,))
    linked = cur.fetchone()[0]
    await update.message.reply_text(get_text(user_id, chat_id, 'stats', total=total, officers=officers, active_today=active_today, linked=linked))

async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    cur.execute("SELECT id FROM users WHERE chat_id=? AND last_active > ?", (chat_id, now() - 86400))
    users = [row[0] for row in cur.fetchall()]
    if not users:
        await update.message.reply_text(get_text(user_id, chat_id, 'no_active'))
        return
    mentions = [f"<a href='tg://user?id={u}'>🔥</a>" for u in users[:50]]
    await update.message.reply_text(f"🔥 АКТИВНІ ГРАВЦІ ({len(users)}):\n" + " ".join(mentions), parse_mode=ParseMode.HTML)

async def officers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    rows = get_role_users(chat_id, "officer")
    if not rows:
        await update.message.reply_text(get_text(user_id, chat_id, 'no_officers'))
        return
    officer_list = []
    for uid, username in rows:
        if username:
            officer_list.append(f"👑 @{username}")
        else:
            officer_list.append(f"👑 Користувач")
    await update.message.reply_text(get_text(user_id, chat_id, 'officers') + "\n".join(officer_list))

# ========== ЗАПУСК ==========
def main():
    global app
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_choice))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="lang_"))
    
    app.add_handler(CommandHandler("init", init))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("mystat", mystat))
    app.add_handler(CommandHandler("setally", setally))
    app.add_handler(CommandHandler("myprofile", myprofile))
    app.add_handler(CommandHandler("profile", profile_cmd))

    app.add_handler(CommandHandler("energy", energy))
    app.add_handler(CommandHandler("raid", raid))
    app.add_handler(CommandHandler("tw", tw))
    app.add_handler(CommandHandler("tb", tb))
    app.add_handler(CommandHandler("all", all_users))
    app.add_handler(CommandHandler("makeofficer", make_officer))
    app.add_handler(CommandHandler("removeofficer", remove_officer))
    app.add_handler(CommandHandler("inactive", inactive))

    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("active", active))
    app.add_handler(CommandHandler("officers", officers))

    schedule_reminder()

    print("✅ Бот запущений! Готовий працювати в багатьох групах.")
    app.run_polling()

if __name__ == "__main__":
    main()
