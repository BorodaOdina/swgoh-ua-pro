import os
import sqlite3
import time
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

TOKEN = os.environ.get("TOKEN")

WAITING_ALLY = 1
WAITING_MAKEOFFICER = 2
WAITING_REMOVEOFFICER = 3
WAITING_INACTIVE_DAYS = 4
WAITING_SETREMIND = 5

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
cur.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    chat_id INTEGER PRIMARY KEY,
    reminder_hour INTEGER DEFAULT 20,
    reminder_minute INTEGER DEFAULT 0
)
""")
conn.commit()

TEXTS = {
    'ua': {
        'start': "🤖 SWGOH UA GUILD BOT\n\n"
                 "👤 ОСНОВНІ КОМАНДИ:\n"
                 "/register - реєстрація\n"
                 "/mystat - моя статистика\n"
                 "/setally <код> - прив'язати Ally Code\n"
                 "/myprofile - мій профіль swgoh.gg\n"
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
                 "/inactive [дні] - список неактивних\n"
                 "/setremind <година:хвилина> - змінити час нагадування\n\n"
                 "📊 СТАТИСТИКА:\n"
                 "/stats - статистика гільдії\n"
                 "/active - активні сьогодні\n"
                 "/officers - список офіцерів\n\n"
                 "⏰ Щоденне нагадування о {remind_hour:02d}:{remind_minute:02d}\n\n"
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
        'setally_usage': "❌ Приклад: `/setally 746197475`\nАбо просто напиши `/setally`, а потім код.",
        'invalid_ally': "❌ Невірний Ally Code (9-10 цифр)",
        'ally_saved': "✅ Ally Code `{code}` прив'язаний!\n\n🔗 [Переглянути профіль]({url})",
        'profile_link': "👤 **Профіль гравця {name}**\n\n🔗 [Відкрити профіль]({url})",
        'profile_self': "👤 **Твій профіль SWGOH.gg**\n\n🔗 [Відкрити профіль]({url})\n\nAlly Code: `{code}`",
        'no_ally': "❌ Спочатку прив'яжи Ally Code через `/setally`",
        'user_no_ally': "❌ Гравець не прив'язав Ally Code",
        'support': "💙 Підтримати розробку бота: [Monobank](https://send.monobank.ua/jar/9DMsxWr16b)\n\nДякуємо за підтримку! 🙏",
        'remind_set': "✅ Час нагадування змінено на {hour:02d}:{minute:02d}",
        'remind_invalid': "❌ Неправильний формат. Напиши годину (наприклад, 20) або годину:хвилини (наприклад, 20:30).",
        'remind_usage': "❌ Приклад: `/setremind 20` або `/setremind 20:30`",
        'ask_ally_code': "🔢 Надішли Ally Code (9-10 цифр, без дефісів).",
        'cancel': "❌ Дію скасовано.",
    },
    'ru': {
        'start': "🤖 SWGOH GUILD BOT\n\n"
                 "👤 ОСНОВНЫЕ КОМАНДЫ:\n"
                 "/register - регистрация\n"
                 "/mystat - моя статистика\n"
                 "/setally <код> - привязать Ally Code\n"
                 "/myprofile - мой профиль swgoh.gg\n"
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
                 "/inactive [дни] - список неактивных\n"
                 "/setremind <час:минута> - изменить время напоминания\n\n"
                 "📊 СТАТИСТИКА:\n"
                 "/stats - статистика гильдии\n"
                 "/active - активные сегодня\n"
                 "/officers - список офицеров\n\n"
                 "⏰ Ежедневное напоминание в {remind_hour:02d}:{remind_minute:02d}\n\n"
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
        'setally_usage': "❌ Пример: `/setally 746197475`\nИли просто напиши `/setally`, а затем код.",
        'invalid_ally': "❌ Неверный Ally Code (9-10 цифр)",
        'ally_saved': "✅ Ally Code `{code}` привязан!\n\n🔗 [Перейти к профилю]({url})",
        'profile_link': "👤 **Профиль игрока {name}**\n\n🔗 [Открыть профиль]({url})",
        'profile_self': "👤 **Твой профиль SWGOH.gg**\n\n🔗 [Открыть профиль]({url})\n\nAlly Code: `{code}`",
        'no_ally': "❌ Сначала привяжи Ally Code через `/setally`",
        'user_no_ally': "❌ Игрок не привязал Ally Code",
        'support': "💙 Поддержать разработку бота: [Monobank](https://send.monobank.ua/jar/9DMsxWr16b)\n\nСпасибо за поддержку! 🙏",
        'remind_set': "✅ Время напоминания изменено на {hour:02d}:{minute:02d}",
        'remind_invalid': "❌ Неправильный формат. Напиши час (например, 20) или час:минуты (например, 20:30).",
        'remind_usage': "❌ Пример: `/setremind 20` или `/setremind 20:30`",
        'ask_ally_code': "🔢 Отправь Ally Code (9-10 цифр, без дефисов).",
        'cancel': "❌ Действие отменено.",
    },
    'en': {
        'start': "🤖 SWGOH GUILD BOT\n\n"
                 "👤 BASIC COMMANDS:\n"
                 "/register - register in the guild\n"
                 "/mystat - my statistics\n"
                 "/setally <code> - link Ally Code\n"
                 "/myprofile - my swgoh.gg profile\n"
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
                 "/inactive [days] - list of inactive players\n"
                 "/setremind <hour:minute> - change reminder time\n\n"
                 "📊 STATISTICS:\n"
                 "/stats - guild statistics\n"
                 "/active - active today\n"
                 "/officers - list of officers\n\n"
                 "⏰ Daily reminder at {remind_hour:02d}:{remind_minute:02d}\n\n"
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
        'setally_usage': "❌ Example: `/setally 746197475`\nOr just type `/setally`, then the code.",
        'invalid_ally': "❌ Invalid Ally Code (9-10 digits)",
        'ally_saved': "✅ Ally Code `{code}` linked!\n\n🔗 [View profile]({url})",
        'profile_link': "👤 **Profile of {name}**\n\n🔗 [Open profile]({url})",
        'profile_self': "👤 **Your SWGOH.gg profile**\n\n🔗 [Open profile]({url})\n\nAlly Code: `{code}`",
        'no_ally': "❌ First link your Ally Code via `/setally`",
        'user_no_ally': "❌ Player has not linked Ally Code",
        'support': "💙 Support bot development: [Monobank](https://send.monobank.ua/jar/9DMsxWr16b)\n\nThank you for your support! 🙏",
        'remind_set': "✅ Reminder time changed to {hour:02d}:{minute:02d}",
        'remind_invalid': "❌ Invalid format. Enter hour (e.g., 20) or hour:minute (e.g., 20:30).",
        'remind_usage': "❌ Example: `/setremind 20` or `/setremind 20:30`",
        'ask_ally_code': "🔢 Send Ally Code (9-10 digits, no hyphens).",
        'cancel': "❌ Action cancelled.",
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

def get_reminder_time(chat_id):
    cur.execute("SELECT reminder_hour, reminder_minute FROM guild_settings WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    return (row[0], row[1]) if row else (20, 0)

def set_reminder_time(chat_id, hour, minute):
    cur.execute("INSERT OR REPLACE INTO guild_settings (chat_id, reminder_hour, reminder_minute) VALUES (?, ?, ?)", (chat_id, hour, minute))
    conn.commit()

scheduler = BackgroundScheduler()
app = None
loop = None

async def send_daily_reminder():
    if app is None:
        return
    now_local = time.localtime()
    current_hour = now_local.tm_hour
    current_minute = now_local.tm_min
    chat_ids = get_all_chat_ids()
    for chat_id in chat_ids:
        try:
            hour, minute = get_reminder_time(chat_id)
            if current_hour != hour or current_minute != minute:
                continue
            cur.execute("SELECT language FROM users WHERE chat_id=? LIMIT 1", (chat_id,))
            row = cur.fetchone()
            lang = row[0] if row else 'ua'
            energy_text = TEXTS.get(lang, TEXTS['ua']).get('energy', "🔋 НЕ ЗАБУДЬ СДАТИ ЕНЕРГІЮ!\n")
            await app.bot.send_message(chat_id=chat_id, text=energy_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print(f"Error in reminder: {e}")

def schedule_reminder():
    def run_coro():
        asyncio.run_coroutine_threadsafe(send_daily_reminder(), loop)
    scheduler.add_job(run_coro, CronTrigger(minute='*'))

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
    hour, minute = get_reminder_time(chat_id)
    start_text = get_text(user_id, chat_id, 'start', remind_hour=hour, remind_minute=minute)
    await query.edit_message_text(start_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    cur.execute("SELECT language FROM users WHERE id=? AND chat_id=?", (user_id, chat_id))
    row = cur.fetchone()
    if not row:
        await language_choice(update, context)
        return
    hour, minute = get_reminder_time(chat_id)
    start_text = get_text(user_id, chat_id, 'start', remind_hour=hour, remind_minute=minute)
    await update.message.reply_text(start_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

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

# --- Діалогові команди ---
async def setally_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        return await process_setally(update, context, context.args[0])
    else:
        await update.message.reply_text(TEXTS['ua']['ask_ally_code'] + "\n/cancel - скасувати")
        return WAITING_ALLY

async def process_setally(update: Update, context: ContextTypes.DEFAULT_TYPE, ally_code_str=None):
    if ally_code_str is None:
        ally_code_str = update.message.text.strip()
    ally_code = ally_code_str.replace("-", "")
    if not ally_code.isdigit() or len(ally_code) not in (9,10):
        await update.message.reply_text("❌ Невірний Ally Code (9-10 цифр). Спробуй ще раз або /cancel")
        return WAITING_ALLY
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    cur.execute("UPDATE users SET ally_code=? WHERE id=? AND chat_id=?", (ally_code, user_id, chat_id))
    conn.commit()
    url = f"https://swgoh.gg/p/{ally_code}/"
    await update.message.reply_text(
        f"✅ Ally Code `{ally_code}` прив'язаний!\n\n🔗 [Переглянути профіль]({url})",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )
    return ConversationHandler.END

async def makeofficer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id, update.effective_chat.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return ConversationHandler.END
    if context.args:
        target = context.args[0]
        return await process_makeofficer(update, context, target)
    else:
        await update.message.reply_text("👑 Надішли @username або Telegram ID користувача, якого хочеш призначити офіцером.\n/cancel - скасувати")
        return WAITING_MAKEOFFICER

async def process_makeofficer(update: Update, context: ContextTypes.DEFAULT_TYPE, target=None):
    if target is None:
        target = update.message.text.strip()
    chat_id = update.effective_chat.id
    if target.startswith("@"):
        username = target[1:]
        cur.execute("SELECT id FROM users WHERE username LIKE ? AND chat_id=?", (f"%{username}%", chat_id))
        row = cur.fetchone()
        if not row:
            await update.message.reply_text("❌ Користувача не знайдено. Спочатку він має зареєструватись через /register")
            return WAITING_MAKEOFFICER
        target_id = row[0]
    else:
        try:
            target_id = int(target)
        except ValueError:
            await update.message.reply_text("❌ Невірний формат. Використовуй @username або ID")
            return WAITING_MAKEOFFICER
    set_role(target_id, chat_id, "officer")
    await update.message.reply_text(f"👑 Користувач призначений офіцером!")
    return ConversationHandler.END

async def removeofficer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id, update.effective_chat.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return ConversationHandler.END
    if context.args:
        target = context.args[0]
        return await process_removeofficer(update, context, target)
    else:
        await update.message.reply_text("👤 Надішли @username або Telegram ID користувача, якого хочеш позбавити прав офіцера.\n/cancel - скасувати")
        return WAITING_REMOVEOFFICER

async def process_removeofficer(update: Update, context: ContextTypes.DEFAULT_TYPE, target=None):
    if target is None:
        target = update.message.text.strip()
    chat_id = update.effective_chat.id
    if target.startswith("@"):
        username = target[1:]
        cur.execute("SELECT id FROM users WHERE username LIKE ? AND chat_id=?", (f"%{username}%", chat_id))
        row = cur.fetchone()
        if not row:
            await update.message.reply_text("❌ Користувача не знайдено")
            return WAITING_REMOVEOFFICER
        target_id = row[0]
    else:
        try:
            target_id = int(target)
        except ValueError:
            await update.message.reply_text("❌ Невірний формат")
            return WAITING_REMOVEOFFICER
    officers = get_role_users(chat_id, "officer")
    if len(officers) == 1 and officers[0][0] == target_id:
        await update.message.reply_text("❌ Не можна зняти єдиного офіцера. Спочатку признач іншого через /makeofficer.")
        return WAITING_REMOVEOFFICER
    set_role(target_id, chat_id, "player")
    await update.message.reply_text(f"👤 Користувач більше не офіцер.")
    return ConversationHandler.END

async def inactive_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id, update.effective_chat.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return ConversationHandler.END
    if context.args and context.args[0].isdigit():
        days = int(context.args[0])
        return await process_inactive(update, context, days)
    else:
        await update.message.reply_text("📅 Надішли кількість днів неактивності (наприклад, 7).\n/cancel - скасувати")
        return WAITING_INACTIVE_DAYS

async def process_inactive(update: Update, context: ContextTypes.DEFAULT_TYPE, days=None):
    if days is None:
        try:
            days = int(update.message.text.strip())
        except:
            await update.message.reply_text("❌ Введи число (кількість днів).")
            return WAITING_INACTIVE_DAYS
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    inactive_users = get_inactive_users(chat_id, days)
    if not inactive_users:
        await update.message.reply_text(f"ℹ️ Немає неактивних гравців за {days} днів")
        return ConversationHandler.END
    text = f"💤 НЕАКТИВНІ {days}+ ДНІВ:\n\n"
    for uid, username, last_active in inactive_users[:20]:
        inactive_days = (now() - last_active) // 86400
        name = username or str(uid)
        text += f"• {name}: {inactive_days} днів\n"
    await update.message.reply_text(text)
    return ConversationHandler.END

async def setremind_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id, update.effective_chat.id):
        await update.message.reply_text("❌ Тільки офіцери")
        return ConversationHandler.END
    if context.args:
        time_str = context.args[0]
        return await process_setremind(update, context, time_str)
    else:
        await update.message.reply_text("⏰ Надішли час нагадування у форматі `година` (наприклад, 20) або `година:хвилина` (наприклад, 20:30).\n/cancel - скасувати", parse_mode=ParseMode.MARKDOWN)
        return WAITING_SETREMIND

async def process_setremind(update: Update, context: ContextTypes.DEFAULT_TYPE, time_str=None):
    if time_str is None:
        time_str = update.message.text.strip()
    match = re.match(r'^(\d{1,2})(?::(\d{1,2}))?$', time_str)
    if not match:
        await update.message.reply_text("❌ Неправильний формат. Напиши, наприклад, 20 або 20:30")
        return WAITING_SETREMIND
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        await update.message.reply_text("❌ Година має бути 0-23, хвилини 0-59")
        return WAITING_SETREMIND
    chat_id = update.effective_chat.id
    set_reminder_time(chat_id, hour, minute)
    await update.message.reply_text(f"✅ Час нагадування змінено на {hour:02d}:{minute:02d}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Дію скасовано.")
    return ConversationHandler.END

# --- Інші команди (без діалогу) ---
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
    officer_list = [f"👑 @{username}" if username else "👑 Користувач" for _, username in rows]
    await update.message.reply_text(get_text(user_id, chat_id, 'officers') + "\n".join(officer_list))

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    cur.execute("SELECT ally_code FROM users WHERE id=? AND chat_id=?", (user_id, chat_id))
    row = cur.fetchone()
    if not row or not row[0]:
        await update.message.reply_text("❌ Спочатку прив'яжи Ally Code через `/setally`", parse_mode=ParseMode.MARKDOWN)
        return
    ally_code = row[0]
    url = f"https://swgoh.gg/p/{ally_code}/"
    await update.message.reply_text(
        f"👤 **Твій профіль SWGOH.gg**\n\n🔗 [Відкрити профіль]({url})\n\nAlly Code: `{ally_code}`",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Приклад: `/profile @username` або `/profile 746197475`", parse_mode=ParseMode.MARKDOWN)
        return
    target = context.args[0]
    if target.startswith("@"):
        username = target[1:]
        cur.execute("SELECT ally_code FROM users WHERE username LIKE ? AND chat_id=?", (f"%{username}%", chat_id))
        row = cur.fetchone()
        if not row or not row[0]:
            await update.message.reply_text("❌ Гравець не прив'язав Ally Code")
            return
        ally_code = row[0]
        url = f"https://swgoh.gg/p/{ally_code}/"
        await update.message.reply_text(f"👤 **Профіль гравця @{username}**\n\n🔗 [Відкрити профіль]({url})", parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        ally_code = target.replace("-", "")
        if not ally_code.isdigit() or len(ally_code) not in (9,10):
            await update.message.reply_text("❌ Невірний Ally Code (9-10 цифр)")
            return
        url = f"https://swgoh.gg/p/{ally_code}/"
        await update.message.reply_text(f"👤 **Профіль SWGOH.gg**\n\n🔗 [Відкрити профіль]({url})\n\nAlly Code: `{ally_code}`", parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

def main():
    global app, loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = Application.builder().token(TOKEN).build()

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setally", setally_start)],
        states={WAITING_ALLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_setally)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("makeofficer", makeofficer_start)],
        states={WAITING_MAKEOFFICER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_makeofficer)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("removeofficer", removeofficer_start)],
        states={WAITING_REMOVEOFFICER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_removeofficer)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("inactive", inactive_start)],
        states={WAITING_INACTIVE_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_inactive)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setremind", setremind_start)],
        states={WAITING_SETREMIND: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_setremind)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_choice))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="lang_"))
    app.add_handler(CommandHandler("init", init))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("mystat", mystat))
    app.add_handler(CommandHandler("myprofile", myprofile))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("energy", energy))
    app.add_handler(CommandHandler("raid", raid))
    app.add_handler(CommandHandler("tw", tw))
    app.add_handler(CommandHandler("tb", tb))
    app.add_handler(CommandHandler("all", all_users))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("active", active))
    app.add_handler(CommandHandler("officers", officers))

    schedule_reminder()
    scheduler.start()
    print("✅ Бот запущений! Готовий працювати в багатьох групах.")
    app.run_polling()

if __name__ == "__main__":
    main()
