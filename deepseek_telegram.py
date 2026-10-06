import os
import sys

# Включаем режим UTF-8 для Python на Windows
os.environ["PYTHONUTF8"] = "1"

import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8687096032:AAGiqqlV3V_GiE4kZoxWDUHzyeDfbBfY8R8"
DEEPSEEK_API_KEY = "sk-4e4544ef40e848b98a9017ce37923621"

# Начальный системный промт (инструкции для бота)
DEFAULT_SYSTEM_PROMPT = (
    "Ты — вежливый и полезный ассистент в Telegram-группе. "
    "Отвечай кратко, понятно и по делу."
)
# ----------------------------------------

# Инициализация клиентa DeepSeek через OpenAI SDK
client = AsyncOpenAI(
    api_key="sk-or-v1-ваш_ключ_от_openrouter",
    base_url="https://openrouter.ai/api/v1"
)

# Переменные состояния бота
system_prompt = "deepseek/deepseek-chat:free"
current_model = "deepseek-chat"  # Исходная модель

bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()


# --- Команды бота ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.reply(
        "👋 Привет! Я бот с подключенным DeepSeek AI.\n\n"
        "В группах я отвечаю на **упоминание** или **ответ (reply)** на мое сообщение.\n"
        "В личке отвечаю на любые сообщения.\n\n"
        "📌 Доступные команды:\n"
        "/prompt <текст> — Задать новый системный промт\n"
        "/getprompt — Посмотреть текущий системный промт\n"
        "/resetprompt — Сбросить системный промт на стандартный\n"
        "/mode — Переключить модель (chat / coder)\n"
        "/help — Справка по командам"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "🤖 **Команды управления ботом:**\n\n"
        "🔹 `/prompt <текст>` — Установить инструкцию для ИИ (например: `/prompt Ты злой пират`).\n"
        "🔹 `/getprompt` — Узнать текущую инструкцию.\n"
        "🔹 `/resetprompt` — Сбросить инструкцию к исходной.\n"
        "🔹 `/mode` — Переключить модель между `deepseek-chat` и `deepseek-coder`.\n"
    )
    await message.reply(help_text)

@dp.message(Command("prompt"))
async def cmd_set_prompt(message: types.Message):
    global system_prompt
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("⚠️ Укажите новый промт после команды.\nПример: `/prompt Отвечай только рифмами.`")
        return
    
    system_prompt = args[1]
    await message.reply(f"✅ **Системный промт обновлен:**\n_{system_prompt}_")

@dp.message(Command("getprompt"))
async def cmd_get_prompt(message: types.Message):
    await message.reply(f"📜 **Текущий системный промт:**\n_{system_prompt}_")

@dp.message(Command("resetprompt"))
async def cmd_reset_prompt(message: types.Message):
    global system_prompt
    system_prompt = DEFAULT_SYSTEM_PROMPT
    await message.reply("🔄 **Системный промт сброшен к стандартному!**")

@dp.message(Command("mode"))
async def cmd_switch_mode(message: types.Message):
    global current_model
    if current_model == "deepseek-chat":
        current_model = "deepseek-coder"
    else:
        current_model = "deepseek-chat"
    await message.reply(f"⚙️ **Модель переключена на:** `{current_model}`")


# --- Обработка обычных сообщений и вопросов в группах ---

async def generate_response(user_text: str) -> str:
    """Запрос к API DeepSeek"""
    try:
        response = await client.chat.completions.create(
            model=current_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"DeepSeek API Error: {e}")
        return "❌ Ошибка при обращении к DeepSeek API. Попробуйте позже."

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_message(message: types.Message):
    bot_info = await message.bot.get_me()
    
    # Проверяем, нужно ли отвечать в зависимости от типа чата:
    # 1. Личные сообщения -> отвечаем всегда
    # 2. Группа -> отвечаем, если бота упомянули или ответили на его сообщение
    is_private = message.chat.type == "private"
    is_mentioned = bot_info.username in (message.text or "")
    is_reply_to_bot = (
        message.reply_to_message is not None 
        and message.reply_to_message.from_user.id == bot_info.id
    )

    if is_private or is_mentioned or is_reply_to_bot:
        # Убираем упоминание бота из текста запроса (например: "@my_bot приветик" -> "приветик")
        clean_text = message.text.replace(f"@{bot_info.username}", "").strip()
        
        if not clean_text:
            await message.reply("Слушаю вас! Задайте вопрос.")
            return

        # Показываем статус "печатает..." во время ожидания ответа
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # Получаем ответ от DeepSeek
        ai_response = await generate_response(clean_text)
        await message.reply(ai_response)


# --- Запуск бота ---

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())