async def makeofficer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_officer(user_id, chat_id):
        await update.message.reply_text(get_text(user_id, chat_id, 'only_officer'))
        return ConversationHandler.END
    
    # Якщо це відповідь на повідомлення — одразу призначаємо
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username or ""
        target_first_name = target_user.first_name or ""
        
        # Завжди оновлюємо або створюємо запис в базі
        cur.execute("SELECT id FROM users WHERE id=? AND chat_id=?", (target_id, chat_id))
        if not cur.fetchone():
            add_user(target_id, chat_id, target_username, target_first_name)
        else:
            # Оновлюємо username
            cur.execute("UPDATE users SET username=?, first_name=? WHERE id=? AND chat_id=?", 
                       (target_username, target_first_name, target_id, chat_id))
            conn.commit()
        
        if is_officer(target_id, chat_id):
            display_name = f"@{target_username}" if target_username else target_first_name
            await update.message.reply_text(
                f"❌ {display_name} вже є офіцером"
            )
            return ConversationHandler.END
        
        set_role(target_id, chat_id, "officer")
        display_name = f"@{target_username}" if target_username else target_first_name
        await update.message.reply_text(f"👑 {display_name} тепер офіцер гільдії!")
        return ConversationHandler.END
    
    if context.args:
        target = context.args[0]
        return await process_makeofficer(update, context, target)
    
    await update.message.reply_text(
        "👑 Щоб призначити офіцера:\n"
        "1️⃣ Дайте **відповідь на повідомлення** гравця командою /makeofficer\n"
        "2️⃣ Або напишіть /makeofficer @username\n\n"
        "/cancel - скасувати",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_MAKEOFFICER

async def process_makeofficer(update: Update, context: ContextTypes.DEFAULT_TYPE, target=None):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if target is None:
        target = update.message.text.strip()
    
    username = target.replace("@", "").strip()
    
    # Шукаємо точний збіг по username
    cur.execute(
        "SELECT id, username, first_name FROM users WHERE chat_id=? AND LOWER(username) = LOWER(?)",
        (chat_id, username)
    )
    found = cur.fetchone()
    
    # Якщо не знайшли — шукаємо частковий збіг
    if not found:
        cur.execute(
            "SELECT id, username, first_name FROM users WHERE chat_id=? AND LOWER(username) LIKE LOWER(?)",
            (chat_id, f"%{username}%")
        )
        found = cur.fetchone()
    
    if not found:
        await update.message.reply_text(
            f"❌ @{username} не знайдено в базі.\n\n"
            "💡 **Найпростіший спосіб:** дайте відповідь на повідомлення гравця командою /makeofficer\n\n"
            "Або нехай гравець зареєструється: /register",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_MAKEOFFICER
    
    target_id, target_username, target_first_name = found
    
    if is_officer(target_id, chat_id):
        display_name = f"@{target_username}" if target_username else target_first_name
        await update.message.reply_text(f"❌ {display_name} вже є офіцером")
        return ConversationHandler.END
    
    set_role(target_id, chat_id, "officer")
    display_name = f"@{target_username}" if target_username else target_first_name
    await update.message.reply_text(f"👑 {display_name} тепер офіцер гільдії!")
    return ConversationHandler.END
