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
        question = "Какой газ оказывает наибольший вклад в общий естественный парниковый эффект Земли?"
        correct_answer = "Водяной пар"
        pending_users[member.id] = correct_answer

        keyboard = [[
            InlineKeyboardButton("Водяной пар", callback_data="Водяной пар"),
            InlineKeyboardButton("Метан", callback_data="Метан"),
            InlineKeyboardButton("CO2", callback_data="CO2"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=update.message.chat.id,
            text=f"Добро пожаловать, {member.full_name}! Пожалуйста, ответьте на вопрос: {question}",
            reply_markup=reply_markup
        )

        # Устанавливаем таймер на 2 минуты
        context.application.job_queue.run_once(
            kick_unverified_user, 120, chat_id=update.message.chat.id, name=str(member.id)
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
            await context.bot.send_message(chat_id, f"Пользователь {query.from_user.full_name} успешно проверен!")
            del pending_users[user_id]
        else:
            await query.answer("Неверный ответ. Попробуйте снова!")
            await context.bot.ban_chat_member(chat_id, user_id)
    else:
        await query.answer("Вы уже прошли проверку или не являетесь новым участником.")

def main() -> None:
    """Запуск бота"""
    # Создаём приложение с job_queue
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    application.add_handler(CallbackQueryHandler(verify_answer))

    # Запускаем приложение
    application.run_polling()

if __name__ == '__main__':
    main()
