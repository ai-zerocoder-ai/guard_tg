import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# Загрузка переменных окружения из .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Не найден токен Telegram в файле .env")

# Словарь для хранения состояния проверки пользователей
pending_users = {}

def start(update: Update, context: CallbackContext) -> None:
    """Команда start, приветствие"""
    update.message.reply_text("Бот для верификации новых пользователей.")

def new_member(update: Update, context: CallbackContext) -> None:
    """Обработка новых пользователей"""
    for member in update.message.new_chat_members:
        question = "Какой газ оказывает наибольший вклад в парниковый эффект?"
        correct_answer = "Водяной пар"
        pending_users[member.id] = correct_answer

        keyboard = [[
            InlineKeyboardButton("Водяной пар", callback_data="Водяной пар"),
            InlineKeyboardButton("Метан", callback_data="Метан"),
            InlineKeyboardButton("Углекислый газ", callback_data="Углекислый газ"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.bot.send_message(
            chat_id=update.message.chat.id,
            text=f"Добро пожаловать, {member.full_name}! Пожалуйста, ответьте на вопрос: {question}",
            reply_markup=reply_markup
        )

        # Устанавливаем таймер на 2 минуты
        context.job_queue.run_once(
            kick_unverified_user, 120, context=(update.message.chat.id, member.id)
        )

def kick_unverified_user(context: CallbackContext):
    """Удаление пользователя, не прошедшего проверку"""
    chat_id, user_id = context.job.context
    if user_id in pending_users:
        context.bot.kick_chat_member(chat_id, user_id)
        del pending_users[user_id]
        context.bot.send_message(chat_id, f"Пользователь {user_id} не прошел проверку и был удален.")

def verify_answer(update: Update, context: CallbackContext) -> None:
    """Проверка ответа пользователя"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat.id

    if user_id in pending_users:
        correct_answer = pending_users[user_id]
        if query.data == correct_answer:
            context.bot.answer_callback_query(query.id, "Верно!")
            context.bot.send_message(chat_id, f"Пользователь {query.from_user.full_name} успешно проверен!")
            del pending_users[user_id]
        else:
            context.bot.answer_callback_query(query.id, "Неверный ответ. Попробуйте снова!")
            context.bot.kick_chat_member(chat_id, user_id)
    else:
        context.bot.answer_callback_query(query.id, "Вы уже прошли проверку или не являетесь новым участником.")

def main():
    """Запуск бота"""
    updater = Updater(BOT_TOKEN)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, new_member))
    dp.add_handler(CallbackQueryHandler(verify_answer))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
