import logging
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Загрузка токена из .env файла
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Токен Telegram бота не найден в .env файле.")

# Словарь для хранения состояния проверки пользователей
pending_users = {}

QUESTION = "Какой химический элемент является первым в периодической системе химических элементов Д.И. Менделеева?"
CORRECT_ANSWER = "H2"
OPTIONS = ["H2", "H3", "H4"]

# Логирование
logging.basicConfig(level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start, приветствие"""
    await update.message.reply_text("Бот для верификации новых пользователей запущен.")


async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка новых участников с учетом разделов"""
    chat = update.message.chat
    topic_id = update.message.message_thread_id if chat.is_forum else None
    logging.info(f"Новый пользователь {update.message.new_chat_members[0].full_name} добавлен в чат {chat.id}, тема: {topic_id}")

    for member in update.message.new_chat_members:
        try:
            pending_users[member.id] = CORRECT_ANSWER
            keyboard = [[InlineKeyboardButton(option, callback_data=option)] for option in OPTIONS]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Отправляем сообщение о верификации в нужный раздел (или в общий чат)
            message = await context.bot.send_message(
                chat_id=chat.id,
                message_thread_id=topic_id,
                text=f"Добро пожаловать, {member.full_name}! В течение 20 секунд ответьте на вопрос: {QUESTION}",
                reply_markup=reply_markup
            )

            logging.info(f"Сообщение отправлено пользователю {member.full_name} ({member.id}) в теме {topic_id}.")
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения пользователю {member.full_name} ({member.id}): {e}")
            continue

        # Получаем `job_queue`
        job_queue = context.application.job_queue

        # Устанавливаем таймер на 20 секунд для удаления пользователя
        job_queue.run_once(kick_unverified_user, 20, chat_id=chat.id, name=str(member.id))

        # Устанавливаем таймер на 30 секунд для удаления сообщения
        job_queue.run_once(delete_verification_message, 30, chat_id=chat.id, data={"message_id": message.message_id})


async def kick_unverified_user(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление пользователя, не прошедшего проверку"""
    job = context.job
    user_id = int(job.name)
    chat_id = job.chat_id

    if pending_users.pop(user_id, None):
        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.send_message(chat_id, f"Пользователь {user_id} не прошел проверку и был забанен.")
            logging.info(f"Пользователь {user_id} забанен за непрохождение верификации.")
        except Exception as e:
            logging.error(f"Ошибка при бане пользователя {user_id}: {e}")


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

            # Убираем inline-кнопки, чтобы избежать повторных нажатий
            await query.edit_message_reply_markup(reply_markup=None)

            await context.bot.send_message(chat_id, f"Пользователь {query.from_user.full_name} успешно верифицирован!")
            pending_users.pop(user_id, None)  # Убираем из списка на бан
            logging.info(f"Пользователь {query.from_user.full_name} ({user_id}) успешно верифицирован.")
        else:
            await query.answer("Неверный ответ. Вы забанены.")
            await context.bot.ban_chat_member(chat_id, user_id)
            logging.info(f"Пользователь {user_id} дал неверный ответ и был забанен.")
    else:
        await query.answer("Вы уже прошли проверку или не являетесь новым участником.")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Разблокировка пользователя"""
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Использование: /unban <user_id>")
        return

    user_id = int(context.args[0])
    chat_id = update.effective_chat.id

    try:
        await context.bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        await update.message.reply_text(f"Пользователь {user_id} был разблокирован. Он может снова вступить в группу.")
        logging.info(f"Пользователь {user_id} разблокирован.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при разблокировке пользователя: {e}")
        logging.error(f"Ошибка при разблокировке пользователя {user_id}: {e}")


async def remove_webhook(application: Application):
    """Удаляем Webhook, если был установлен ранее"""
    await application.bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook удален перед запуском polling.")


async def init_jobs(application: Application):
    """Асинхронно инициализируем `JobQueue`"""
    application.job_queue.start()
    logging.info("JobQueue инициализирован")


def main() -> None:
    """Запуск бота"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(init_jobs)
        .build()
    )

    loop.run_until_complete(remove_webhook(application))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    application.add_handler(CallbackQueryHandler(verify_answer))
    application.add_handler(CommandHandler("unban", unban_user))

    application.run_polling()


if __name__ == '__main__':
    main()
