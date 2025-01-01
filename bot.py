from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
from dotenv import load_dotenv

# Загрузка токена из .env файла
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Токен Telegram бота не найден в .env файле.")

# Словарь для хранения состояния проверки пользователей
pending_users = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда start, приветствие"""
    await update.message.reply_text("Бот для верификации новых пользователей запущен.")

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка новых пользователей"""
    for member in update.message.new_chat_members:
        question = "что оказывает наибольший вклад в парниковый эффект?"
        correct_answer = "Водяной пар"
        pending_users[member.id] = correct_answer

        # Вертикальная клавиатура
        keyboard = [
            [InlineKeyboardButton("Водяной пар", callback_data="Водяной пар")],
            [InlineKeyboardButton("Плавание", callback_data="Плавание")],
            [InlineKeyboardButton("Шахматы", callback_data="Шахматы")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=update.message.chat.id,
            text=f"Добро пожаловать, {member.full_name}! В течение 20 секунд ответьте на вопрос: {question}",
            reply_markup=reply_markup
        )

        # Устанавливаем таймер на 20 секунд
        context.application.job_queue.run_once(
            kick_unverified_user, 20, chat_id=update.message.chat.id, name=str(member.id)
        )

async def kick_unverified_user(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление пользователя, не прошедшего проверку"""
    job = context.job
    user_id = int(job.name)
    chat_id = job.chat_id

    if user_id in pending_users:
        await context.bot.ban_chat_member(chat_id, user_id)
        del pending_users[user_id]
        await context.bot.send_message(chat_id, f"Пользователь {user_id} не прошел проверку и был удален.")

async def verify_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка ответа пользователя"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat.id

    if user_id in pending_users:
        correct_answer = pending_users[user_id]
        if query.data == correct_answer:
            await query.answer("Верно!")
            await context.bot.send_message(chat_id, f"Пользователь {query.from_user.full_name} успешно верифицирован!")
            del pending_users[user_id]
        else:
            await query.answer("Неверный ответ. Попробуйте снова!")
            await context.bot.ban_chat_member(chat_id, user_id)
    else:
        await query.answer("Вы уже прошли проверку или не являетесь новым участником.")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Разблокировка пользователя"""
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /unban <user_id>")
        return

    user_id = context.args[0]

    try:
        chat_id = update.effective_chat.id
        await context.bot.unban_chat_member(chat_id, user_id)
        await update.message.reply_text(f"Пользователь с ID {user_id} был разблокирован и может снова пройти проверку.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при разблокировке пользователя: {e}")

def main() -> None:
    """Запуск бота"""
    # Создаём приложение с job_queue
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    application.add_handler(CallbackQueryHandler(verify_answer))
    application.add_handler(CommandHandler("unban", unban_user))

    # Запускаем приложение
    application.run_polling()

if __name__ == '__main__':
    main()
