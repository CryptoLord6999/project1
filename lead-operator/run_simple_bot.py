import os
import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Имитация LLM и логики (чтобы работало без сложной настройки) ---
async def get_ai_response(text: str, history: list) -> str:
    """
    Здесь должна быть логика вызова Qwen/DashScope.
    Для первого теста делаем простую имитацию, чтобы ты увидел реакцию.
    """
    text_lower = text.lower()
    
    if "привет" in text_lower or "здравствуйте" in text_lower:
        return "Здравствуйте! Я ИИ-ассистент салона красоты. Подсказать вам по услугам или записать на удобное время?"
    
    if "цена" in text_lower or "сколько стоит" in text_lower:
        return "У нас стрижка стоит 1500₽, маникюр — 1200₽. Хотите записаться?"
    
    if "записать" in text_lower or "время" in text_lower:
        return "Отлично! На какое время вас записать? У нас свободно сегодня в 14:00 или 16:30."
    
    if "хочу человека" in text_lower or "оператор" in text_lower:
        return "Понял вас. Сейчас приглашу администратора, он подключится к диалогу через минуту."
    
    # Ответ по умолчанию
    return "Интересный вопрос! Давайте уточним: вас интересует конкретная услуга или консультация?"

# --- Логика Бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я ваш новый ИИ-оператор. \n"
        "Я могу ответить на вопросы, рассчитать стоимость и записать вас.\n"
        "Напишите что-нибудь, например: 'Сколько стоит стрижка?'"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"Сообщение от {user_id}: {user_text}")
    
    # Эмуляция "печатает..."
    await update.message.chat.send_action(action="typing")
    
    # Получаем ответ от "ИИ"
    # В реальной версии здесь будет вызов app/core/dialogue.py
    response_text = await get_ai_response(user_text, [])
    
    await update.message.reply_text(response_text)

async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token or token == "ТВОЙ_ТОКЕН_ОТ_BOTFATHER":
        print("\n❌ ОШИБКА: Вы не вставили токен бота!")
        print("1. Создайте бота у @BotFather в Telegram.")
        print("2. Скопируйте токен.")
        print("3. Запустите команду: export TELEGRAM_BOT_TOKEN='ваш_токен'")
        print("   или отредактируйте этот файл, вставив токен в переменную token.\n")
        return

    print("✅ Бот запускается... Нажмите /start в Telegram, чтобы проверить.")
    
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем.")