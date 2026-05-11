import os
import sqlite3
import time
import re
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)
from apscheduler.schedulers.background import BackgroundScheduler

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
    first_name TEXT,
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
    reminder_minute INTEGER DEFAULT 0,
    timezone INTEGER DEFAULT 3,
    last_reminder_date TEXT DEFAULT '',
    reminder_enabled INTEGER DEFAULT 1
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
                 "/raid - рейд (з позначкою всіх)\n"
                 "/tw - Territory War (з позначкою всіх)\n"
                 "/tb - Territory Battle (з позначкою всіх)\n"
                 "/all - всіх покликати\n"
                 "/energy - нагадати про енергію (з позначкою всіх)\n"
                 "/makeofficer @user - призначити офіцера\n"
                 "/removeofficer @user - зняти офіцера\n"
                 "/inactive [дні] - список неактивних\n"
                 "/setremind <година:хвилина> - змінити час нагадування\n"
                 "/toggleremind - увімкнути/вимкнути нагадування\n"
                 "/timezone <зміщення> - налаштувати часовий пояс\n"
                 "/restart - перезапустити бота\n\n"
                 "📊 СТАТИСТИКА:\n"
                 "/stats - статистика гільдії\n"
                 "/active - активні сьогодні\n"
                 "/officers - список офіцерів\n\n"
                 "⏰ Щоденне нагадування: {reminder_status}\n"
                 "Час: {remind_hour:02d}:{remind_minute:02d}\n\n"
                 "🌐 Змінити мову: /language",
        'register_ok': "✅ Ти зареєстрований у гільдії!",
        'already_registered': "✅ Ти вже зареєстрований у гільдії!",
        'not_registered': "❌ Спочатку /register",
        'only_officer': "❌ Тільки офіцери можуть використовувати цю команду",
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
        'setally_usage': "❌ Використай: `/setally 746197475`",
        'invalid_ally': "❌ Невірний Ally Code (9-10 цифр)",
        'ally_saved': "✅ Ally Code `{code}` прив'язаний!\n\n🔗 [Переглянути профіль]({url})",
        'profile_link': "👤 **Профіль гравця {name}**\n\n🔗 [Відкрити профіль]({url})",
        'profile_self': "👤 **Твій профіль SWGOH.gg**\n\n🔗 [Відкрити профіль]({url})\n\nAlly Code: `{code}`",
        'no_ally': "❌ Спочатку прив'яжи Ally Code через `/setally`",
        'user_no_ally': "❌ Гравець не прив'язав Ally Code",
        'remind_set': "✅ Час нагадування змінено на {hour:02d}:{minute:02d}",
        'remind_invalid': "❌ Використай формат: `20` або `20:30`",
        'remind_usage': "❌ Приклад: `/setremind 20` або `/setremind 20:30`",
        'ask_ally_code': "🔢 Надішли Ally Code (9-10 цифр, без дефісів).\n/cancel - скасувати",
        'cancel': "❌ Дію скасовано.",
        'timezone_set': "✅ Часовий пояс змінено на UTC{tz:+d}",
        'timezone_usage': "❌ Приклад: `/timezone 3` (для України)",
        'restart_ok': "🔄 Перезапуск бота...\nЦе може зайняти кілька секунд.",
        'restart_only_officer': "❌ Тільки офіцери можуть перезапустити бота",
        'makeofficer_not_found': "❌ Користувача {user} не знайдено в базі гільдії.\nЙому потрібно спочатку зареєструватися через /register",
        'makeofficer_success': "👑 {user} тепер офіцер гільдії!",
        'already_officer': "❌ {user} вже є офіцером",
        'makeofficer_ask': "👑 Використай @username щоб призначити офіцера:\n/makeofficer @username\n\nАбо просто напиши @username в чаті",
        'removeofficer_success': "👤 {user} більше не офіцер",
        'removeofficer_self': "❌ Ти не можеш зняти себе з посади офіцера",
        'removeofficer_last': "❌ Не можна зняти останнього офіцера. Спочатку признач іншого через /makeofficer",
        'removeofficer_ask': "👤 Надішли @username кого хочеш зняти з офіцерів:\n/removeofficer @username",
        'reminder_enabled': "✅ Щоденне нагадування увімкнено",
        'reminder_disabled': "❌ Щоденне нагадування вимкнено",
        'reminder_on': "🟢 Увімкнено",
        'reminder_off': "🔴 Вимкнено",
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
                 "/raid - рейд (с отметкой всех)\n"
                 "/tw - Territory War (с отметкой всех)\n"
                 "/tb - Territory Battle (с отметкой всех)\n"
                 "/all - призвать всех\n"
                 "/energy - напомнить об энергии (с отметкой всех)\n"
                 "/makeofficer @user - назначить офицера\n"
                 "/removeofficer @user - снять офицера\n"
                 "/inactive [дни] - список неактивных\n"
                 "/setremind <час:минута> - изменить время напоминания\n"
                 "/toggleremind - включить/выключить напоминание\n"
                 "/timezone <смещение> - настроить часовой пояс\n"
                 "/restart - перезапустить бота\n\n"
                 "📊 СТАТИСТИКА:\n"
                 "/stats - статистика гильдии\n"
                 "/active - активные сегодня\n"
                 "/officers - список офицеров\n\n"
                 "⏰ Ежедневное напоминание: {reminder_status}\n"
                 "Время: {remind_hour:02d}:{remind_minute:02d}\n\n"
                 "🌐 Сменить язык: /language",
        'register_ok': "✅ Ты зарегистрирован в гильдии!",
        'already_registered': "✅ Ты уже зарегистрирован в гильдии!",
        'not_registered': "❌ Сначала /register",
        'only_officer': "❌ Только офицеры могут использовать эту команду",
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
        'setally_usage': "❌ Используй: `/setally 746197475`",
        'invalid_ally': "❌ Неверный Ally Code (9-10 цифр)",
        'ally_saved': "✅ Ally Code `{code}` привязан!\n\n🔗 [Перейти к профилю]({url})",
        'profile_link': "👤 **Профиль игрока {name}**\n\n🔗 [Открыть профиль]({url})",
        'profile_self': "👤 **Твой профиль SWGOH.gg**\n\n🔗 [Открыть профиль]({url})\n\nAlly Code: `{code}`",
        'no_ally': "❌ Сначала привяжи Ally Code через `/setally`",
        'user_no_ally': "❌ Игрок не привязал Ally Code",
        'remind_set': "✅ Время напоминания изменено на {hour:02d}:{minute:02d}",
        'remind_invalid': "❌ Используй формат: `20` или `20:30`",
        'remind_usage': "❌ Пример: `/setremind 20` или `/setremind 20:30`",
        'ask_ally_code': "🔢 Отправь Ally Code (9-10 цифр, без дефисов).\n/cancel - отменить",
        'cancel': "❌ Действие отменено.",
        'timezone_set': "✅ Часовой пояс изменён на UTC{tz:+d}",
        'timezone_usage': "❌ Пример: `/timezone 3` (для Украины)",
        'restart_ok': "🔄 Перезапуск бота...\nЭто может занять несколько секунд.",
        'restart_only_officer': "❌ Только офицеры могут перезапустить бота",
        'makeofficer_not_found': "❌ Пользователь {user} не найден в базе гильдии.\nЕму нужно сначала зарегистрироваться через /register",
        'makeofficer_success': "👑 {user} теперь офицер гильдии!",
        'already_officer': "❌ {user} уже является офицером",
        'makeofficer_ask': "👑 Используй @username чтобы назначить офицера:\n/makeofficer @username\n\nИли просто напиши @username в чате",
        'removeofficer_success': "👤 {user} больше не офицер",
        'removeofficer_self': "❌ Ты не можешь снять себя с должности офицера",
        'removeofficer_last': "❌ Нельзя снять последнего офицера. Сначала назначь другого через /makeofficer",
        'removeofficer_ask': "👤 Отправь @username кого хочешь снять с офицеров:\n/removeofficer @username",
        'reminder_enabled': "✅ Ежедневное напоминание включено",
        'reminder_disabled': "❌ Ежедневное напоминание выключено",
        'reminder_on': "🟢 Включено",
        'reminder_off': "🔴 Выключено",
    }
}

def get_text(uid, chat_id, key, **kwargs):
    cur.execute("SELECT language FROM users WHERE id=? AND chat_id=?", (uid, chat_id))
    row = cur.fetchone()
    lang = row[0] if row else 'ua'
    text = TEXTS.get(lang, TEXTS['ua']).get(key, TEXTS['ua'][key])
    return text.format(**kwargs) if kwargs else text

def get_timezone(chat_id):
    cur.execute("SELECT timezone FROM guild_settings WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    return row[0] if row else 3

def get_local_time(chat_id):
    tz = get_timezone(chat_id)
    return time.localtime(time.time() + tz * 3600)

def set_language(uid, chat_id, lang):
    cur.execute("UPDATE users SET language=? WHERE id=? AND chat_id=?", (lang, uid, chat_id))
    conn.commit()

def now():
    return int(time.time())

def add_user(uid, chat_id, username, first_name, language='ua'):
    cur.execute("INSERT OR IGNORE INTO users (id, chat_id, username, first_name, role, last_active, language) VALUES (?, ?, ?, ?, 'player', ?, ?)",
                (uid, chat_id, username, first_name, now(), language))
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
    cur.execute("SELECT id, username, first_name FROM users WHERE chat_id=? AND role=?", (chat_id, role))
    return cur.fetchall()

def get_inactive_users(chat_id, days):
    limit = now() - days * 86400
    cur.execute("SELECT id, username, first_name, last_active FROM users WHERE chat_id=? AND last_active < ?", (chat_id, limit))
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

def is_reminder_enabled(chat_id):
    cur.execute("SELECT reminder_enabled FROM guild_settings WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    return row[0] if row else 1

def set_reminder_enabled(chat_id, enabled):
    cur.execute("SELECT chat_id FROM guild_settings WHERE chat_id=?", (chat_id,))
    if cur.fetchone():
        cur.execute("UPDATE guild_settings SET reminder_enabled=? WHERE chat_id=?", (enabled, chat_id))
    else:
        cur.execute("INSERT INTO guild_settings (chat_id, reminder_enabled) VALUES (?, ?)", (chat_id, enabled))
    conn.commit()

app = None
loop = None

async def send_daily_reminder_logic():
    """Щоденне нагадування - логіка"""
    if app is None:
        return
    chat_ids = get_all_chat_ids()
    for chat_id in chat_ids:
        try:
            if not is_reminder_enabled(chat_id):
                continue
                
            hour, minute = get_reminder_time(chat_id)
            local = get_local_time(chat_id)
            if local.tm_hour == hour and local.tm_min == minute:
                today = f"{local.tm_year}-{local.tm_mon}-{local.tm_mday}"
                cur.execute("SELECT last_reminder_date FROM guild_settings WHERE chat_id=?", (chat_id,))
                row = cur.fetchone()
                if row and row[0] == today:
                    continue
                cur.execute("UPDATE guild_settings SET last_reminder_date=? WHERE chat_id=?", (today, chat_id))
                conn.commit()
                cur.execute("SELECT language FROM users WHERE chat_id=? LIMIT 1", (chat_id,))
                row = cur.fetchone()
                lang = row[0] if row else 'ua'
                energy_text = TEXTS.get(lang, TEXTS['ua']).get('energy', "🔋 НЕ ЗАБУДЬ СДАТИ ЕНЕРГІЮ!\n")
                await app.bot.send_message(chat_id=chat_id, text=energy_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error in reminder for chat_id {chat_id}: {e}")

def schedule_reminder():
    """Запуск нагадування з BackgroundScheduler"""
    def run_coro():
        asyncio.run_coroutine_threadsafe(send_daily_reminder_logic(), loop)
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_coro, 'cron', minute='*')
    scheduler.start()

async def language_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇺🇦 Українська", callback_data="lang_ua")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌐 Оберіть мову / Выберите язык:", reply_markup=reply_markup)

async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    lang = query.data.split("_")[1]
    set_language(user_id, chat_id, lang)
    hour, minute = get_reminder_time(chat_id)
    reminder_status = get_text(user_id, chat_id, 'reminder_on') if is_reminder_enabled(chat_id) else get_text(user_id, chat_id, 'reminder_off')
    start_text = get_text(user_id, chat_id, 'start', remind_hour=hour, remind_minute=minute, reminder_status=reminder_status)
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
    reminder_status = get_text(user_id, chat_id, 'reminder_on') if is_reminder_enabled(chat_id) else get_text(user_id, chat_id, 'reminder_off')
    start_text = get_text(user_id, chat_id, 'start', remind_hour=hour, remind_minute=minute, reminder_status=reminder_status)
    await update.message.reply_text(start_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    if not context.args:
        await update.message.reply_text(get_text(user_id, chat_id, 'timezone_usage'))
        return
    try:
        tz = int(context.args[0])
        if tz < -12 or tz > 14:
            raise ValueError
    except:
        await update.message.reply_text("❌ Введіть число від -12 до 14")
        return
    cur.execute("UPDATE guild_settings SET timezone=? WHERE chat_id=?", (tz, chat_id))
    conn.commit()
    await update.message.reply_text(get_text(user_id, chat_id, 'timezone_set', tz=tz))

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'restart_only_officer'))
        return
    await update.message.reply_text(get_text(user_id, chat_id, 'restart_ok'))
    conn.close()
    await app.stop()
    await asyncio.sleep(2)
    os._exit(0)

async def init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    if has_officers(chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    
    add_user(user_id, chat_id, username, first_name)
    set_role(user_id, chat_id, "officer")
    await update.message.reply_text("👑 Ти став першим офіцером цієї гільдії! Тепер ти можеш призначати інших через /makeofficer @username")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    username = update.effective_user.username or ""
    first_name = update.effective_user.first_name or ""
    
    cur.execute("SELECT id FROM users WHERE id=? AND chat_id=?", (uid, chat_id))
    if cur.fetchone():
        update_last_active(uid, chat_id)
        await update.message.reply_text(get_text(uid, chat_id, 'already_registered'))
        return
    
    add_user(uid, chat_id, username, first_name)
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
    
    update_last_active(uid, chat_id)
    role, last = row
    diff = now() - last
    if diff < 3600:
        time_str = f"{diff // 60} хв тому"
    elif diff < 86400:
        time_str = f"{diff // 3600} год тому"
    else:
        time_str = f"{diff // 86400} днів тому"
    await update.message.reply_text(f"📊 ТВОЯ СТАТИСТИКА\n\nРоль: {role}\nОстання активність: {time_str}")

async def mention_all(chat_id, title, emoji):
    users = get_all_users(chat_id)
    if not users:
        return "❌ Немає зареєстрованих гравців"
    
    mentions = [f"<a href='tg://user?id={u}'>{emoji}</a>" for u in users[:50]]
    return title + " ".join(mentions)

async def raid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    text = await mention_all(chat_id, get_text(user_id, chat_id, 'raid'), "⚔️")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def tw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    text = await mention_all(chat_id, get_text(user_id, chat_id, 'tw'), "⚔️")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def tb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    text = await mention_all(chat_id, get_text(user_id, chat_id, 'tb'), "🌌")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    text = await mention_all(chat_id, get_text(user_id, chat_id, 'all'), "👤")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    text = await mention_all(chat_id, get_text(user_id, chat_id, 'energy'), "🔋")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def toggleremind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return
    
    current = is_reminder_enabled(chat_id)
    new_state = 0 if current else 1
    set_reminder_enabled(chat_id, new_state)
    
    if new_state:
        await update.message.reply_text(get_text(user_id, chat_id, 'reminder_enabled'))
    else:
        await update.message.reply_text(get_text(user_id, chat_id, 'reminder_disabled'))

# --- Діалогові команди ---
async def setally_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        return await process_setally(update, context, context.args[0])
    else:
        await update.message.reply_text(TEXTS['ua']['ask_ally_code'], parse_mode=ParseMode.MARKDOWN)
        return WAITING_ALLY

async def process_setally(update: Update, context: ContextTypes.DEFAULT_TYPE, ally_code_str=None):
    if ally_code_str is None:
        ally_code_str = update.message.text.strip()
    ally_code = ally_code_str.replace("-", "").replace(" ", "")
    if not ally_code.isdigit() or len(ally_code) not in (9, 10):
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
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return ConversationHandler.END
    
    if context.args:
        target = context.args[0]
        return await process_makeofficer(update, context, target)
    
    await update.message.reply_text(
        get_text(user_id, chat_id, 'makeofficer_ask'),
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_MAKEOFFICER

async def process_makeofficer(update: Update, context: ContextTypes.DEFAULT_TYPE, target=None):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if target is None:
        target = update.message.text.strip()
    
    username = target.replace("@", "").strip()
    
    cur.execute(
        "SELECT id, username, first_name FROM users WHERE chat_id=? AND (LOWER(username) = LOWER(?) OR LOWER(first_name) LIKE LOWER(?))",
        (chat_id, username, f"%{username}%")
    )
    found = cur.fetchone()
    
    if not found:
        await update.message.reply_text(
            get_text(user_id, chat_id, 'makeofficer_not_found', user=f"@{username}"),
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_MAKEOFFICER
    
    target_id, target_username, target_first_name = found
    
    if is_officer(target_id, chat_id):
        display_name = f"@{target_username}" if target_username else target_first_name
        await update.message.reply_text(
            get_text(user_id, chat_id, 'already_officer', user=display_name),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    set_role(target_id, chat_id, "officer")
    display_name = f"@{target_username}" if target_username else target_first_name
    await update.message.reply_text(
        get_text(user_id, chat_id, 'makeofficer_success', user=display_name),
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END

async def removeofficer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return ConversationHandler.END
    
    if context.args:
        target = context.args[0]
        return await process_removeofficer(update, context, target)
    
    await update.message.reply_text(
        get_text(user_id, chat_id, 'removeofficer_ask'),
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_REMOVEOFFICER

async def process_removeofficer(update: Update, context: ContextTypes.DEFAULT_TYPE, target=None):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if target is None:
        target = update.message.text.strip()
    
    username = target.replace("@", "").strip()
    
    cur.execute(
        "SELECT id, username, first_name FROM users WHERE chat_id=? AND role='officer' AND (LOWER(username) = LOWER(?) OR LOWER(first_name) LIKE LOWER(?))",
        (chat_id, username, f"%{username}%")
    )
    found = cur.fetchone()
    
    if not found:
        await update.message.reply_text(
            f"❌ Офіцера @{username} не знайдено",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_REMOVEOFFICER
    
    target_id, target_username, target_first_name = found
    display_name = f"@{target_username}" if target_username else target_first_name
    
    if target_id == user_id:
        await update.message.reply_text(get_text(user_id, chat_id, 'removeofficer_self'))
        return WAITING_REMOVEOFFICER
    
    officers = get_role_users(chat_id, "officer")
    if len(officers) == 1:
        await update.message.reply_text(get_text(user_id, chat_id, 'removeofficer_last'))
        return ConversationHandler.END
    
    set_role(target_id, chat_id, "player")
    await update.message.reply_text(
        get_text(user_id, chat_id, 'removeofficer_success', user=display_name),
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END

async def inactive_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id, update.effective_chat.id):
        await update.message.reply_text(get_text(update.effective_user.id, update.effective_chat.id, 'only_officer'))
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
        await update.message.reply_text(get_text(user_id, chat_id, 'no_inactive', days=days))
        return ConversationHandler.END
    text = get_text(user_id, chat_id, 'inactive_title', days=days)
    for uid, username, first_name, last_active in inactive_users[:20]:
        inactive_days = (now() - last_active) // 86400
        name = f"@{username}" if username else first_name or str(uid)
        text += f"• {name}: {inactive_days} днів\n"
    await update.message.reply_text(text)
    return ConversationHandler.END

async def setremind_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_officer(update.effective_user.id, update.effective_chat.id):
        await update.message.reply_text(get_text(update.effective_user.id, update.effective_chat.id, 'only_officer'))
        return ConversationHandler.END
    if context.args:
        time_str = context.args[0]
        return await process_setremind(update, context, time_str)
    else:
        await update.message.reply_text("⏰ Надішли час нагадування (наприклад, 20 або 20:30).\n/cancel - скасувати")
        return WAITING_SETREMIND

async def process_setremind(update: Update, context: ContextTypes.DEFAULT_TYPE, time_str=None):
    if time_str is None:
        time_str = update.message.text.strip()
    match = re.match(r'^(\d{1,2})(?::(\d{1,2}))?$', time_str)
    if not match:
        await update.message.reply_text(get_text(update.effective_user.id, update.effective_chat.id, 'remind_invalid'), parse_mode=ParseMode.MARKDOWN)
        return WAITING_SETREMIND
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        await update.message.reply_text("❌ Година має бути 0-23, хвилини 0-59")
        return WAITING_SETREMIND
    chat_id = update.effective_chat.id
    set_reminder_time(chat_id, hour, minute)
    await update.message.reply_text(get_text(update.effective_user.id, chat_id, 'remind_set', hour=hour, minute=minute))
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_text(update.effective_user.id, update.effective_chat.id, 'cancel'))
    return ConversationHandler.END

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
    for uid, username, first_name in rows:
        name = f"@{username}" if username else first_name or str(uid)
        officer_list.append(f"👑 {name}")
    await update.message.reply_text(get_text(user_id, chat_id, 'officers') + "\n".join(officer_list))

async def myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    cur.execute("SELECT ally_code FROM users WHERE id=? AND chat_id=?", (user_id, chat_id))
    row = cur.fetchone()
    if not row or not row[0]:
        await update.message.reply_text(get_text(user_id, chat_id, 'no_ally'), parse_mode=ParseMode.MARKDOWN)
        return
    ally_code = row[0]
    url = f"https://swgoh.gg/p/{ally_code}/"
    await update.message.reply_text(
        get_text(user_id, chat_id, 'profile_self', url=url, code=ally_code),
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
        cur.execute(
            "SELECT ally_code, username, first_name FROM users WHERE chat_id=? AND (LOWER(username) = LOWER(?) OR LOWER(first_name) LIKE LOWER(?))",
            (chat_id, username, f"%{username}%")
        )
        row = cur.fetchone()
        if not row or not row[0]:
            await update.message.reply_text(get_text(user_id, chat_id, 'user_no_ally'))
            return
        ally_code, target_username, target_first_name = row
        display_name = f"@{target_username}" if target_username else target_first_name
        url = f"https://swgoh.gg/p/{ally_code}/"
        await update.message.reply_text(
            get_text(user_id, chat_id, 'profile_link', name=display_name, url=url),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    else:
        ally_code = target.replace("-", "")
        if not ally_code.isdigit() or len(ally_code) not in (9, 10):
            await update.message.reply_text(get_text(user_id, chat_id, 'invalid_ally'))
            return
        url = f"https://swgoh.gg/p/{ally_code}/"
        await update.message.reply_text(
            f"👤 **Профіль SWGOH.gg**\n\n🔗 [Відкрити профіль]({url})\n\nAlly Code: `{ally_code}`",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

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
    app.add_handler(CommandHandler("timezone", set_timezone))
    app.add_handler(CommandHandler("restart", restart_bot))
    app.add_handler(CommandHandler("toggleremind", toggleremind))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="lang_"))
    app.add_handler(CommandHandler("init", init))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("mystat", mystat))
    app.add_handler(CommandHandler("myprofile", myprofile))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("raid", raid))
    app.add_handler(CommandHandler("tw", tw))
    app.add_handler(CommandHandler("tb", tb))
    app.add_handler(CommandHandler("all", all_users))
    app.add_handler(CommandHandler("energy", energy))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("active", active))
    app.add_handler(CommandHandler("officers", officers))

    schedule_reminder()
    logger.info("✅ Бот запущений! Готовий працювати в багатьох групах.")
    app.run_polling()

if __name__ == "__main__":
    main()
