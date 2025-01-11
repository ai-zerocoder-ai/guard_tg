import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
from dotenv import load_dotenv
import asyncio

# Загрузка токена из .env файла
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Токен Telegram бота не найден в .env файле.")

# Словарь для хранения состояния проверки пользователей
pending_users = {}

QUESTION = "Что оказывает наибольший вклад в парниковый эффект?"
CORRECT_ANSWER = "Водяной пар"
OPTIONS = ["Водяной пар", "Плавание", "Шахматы"]

# Логирование
logging.basicConfig(level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start, приветствие"""
    await update.message.reply_text("Бот для верификации новых пользователей запущен.")


async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка новых участников группы"""
    for member in update.message.new_chat_members:
        try:
            pending_users[member.id] = CORRECT_ANSWER
            keyboard = [[InlineKeyboardButton(option, callback_data=option)] for option in OPTIONS]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Отправляем сообщение с кнопками
            message = await context.bot.send_message(
                chat_id=update.message.chat.id,
                text=f"Добро пожаловать, {member.full_name}! В течение 20 секунд ответьте на вопрос: {QUESTION}",
                reply_markup=reply_markup
            )

            logging.info(f"Сообщение отправлено пользователю {member.full_name} ({member.id}).")
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения пользователю {member.full_name} ({member.id}): {e}")

        # Устанавливаем таймер на 20 секунд для удаления пользователя
        context.job_queue.run_once(
            kick_unverified_user, 20, chat_id=update.message.chat.id, name=str(member.id)
        )

        # Устанавливаем таймер на 30 секунд для удаления сообщения
        context.job_queue.run_once(
            delete_verification_message, 30, chat_id=update.message.chat.id,
            data={"message_id": message.message_id}
        )


async def kick_unverified_user(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление пользователя, не прошедшего проверку"""
    job = context.job
    user_id = int(job.name)
    chat_id = job.chat_id

    if pending_users.pop(user_id, None):
        await context.bot.ban_chat_member(chat_id, user_id)
        await context.bot.send_message(chat_id, f"Пользователь {user_id} не прошел проверку и был удален.")


async def delete_verification_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление сообщения с кнопками"""
    job_data = context.job.data
    message_id = job_data.get("message_id")
    chat_id = context.job.chat_id

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logging.info(f"Сообщение {message_id} успешно удалено из чата {chat_id}.")
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения {message_id} из чата {chat_id}: {e}")


async def verify_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка ответа пользователя"""
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = query.message.chat.id

    if user_id in pending_users:
        if query.data == CORRECT_ANSWER:
            await query.answer("Верно!")
            await context.bot.send_message(chat_id, f"Пользователь {query.from_user.full_name} успешно верифицирован!")
            pending_users.pop(user_id, None)
        else:
            await query.answer("Неверный ответ. Вы удалены.")
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
        await update.message.reply_text(f"Пользователь с ID {user_id} был разблокирован.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при разблокировке пользователя: {e}")


def main() -> None:
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).read_timeout(30).connect_timeout(30).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    application.add_handler(CallbackQueryHandler(verify_answer))
    application.add_handler(CommandHandler("unban", unban_user))

    # Запускаем приложение
    application.run_polling()


if __name__ == '__main__':
    main()
