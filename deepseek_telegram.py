# -*- coding: utf-8 -*-
import os
import sys
import re
import io
import logging
import asyncio

# --- 1. ПРИНУДИТЕЛЬНАЯ НАСТРОЙКА UTF-8 (Фикс ошибок кодировки ASCII) ---
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI, APIError, AuthenticationError, InsufficientQuotaError


# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = "8687096032:AAGiqqlV3V_GiE4kZoxWDUHzyeDfbBfY8R8"

# API Ключ (DeepSeek, OpenRouter или GitHub Models)
API_KEY = "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"

# Выберите сервер (раскомментируйте нужную пару BASE_URL и DEFAULT_MODEL):

# --- Вариант 1: Официальный DeepSeek API (требует баланса на platform.deepseek.com) ---
BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek-chat"

# --- Вариант 2: Бесплатный OpenRouter (нужен ключ с openrouter.ai) ---
# BASE_URL = "https://openrouter.ai/api/v1"
# DEFAULT_MODEL = "deepseek/deepseek-chat:free"


# Начальный системный промт
DEFAULT_SYSTEM_PROMPT = (
    "Ты — вежливый и полезный ассистент в Telegram-группе. "
    "Отвечай кратко, понятно и по делу."
)
# ----------------------------------------


# Очистка ключа и URL от случайных не-ASCII символов, пробелов и переносов строк
CLEAN_API_KEY = re.sub(r'[^\x00-\x7F]+', '', API_KEY).strip()
CLEAN_BASE_URL = re.sub(r'[^\x00-\x7F]+', '', BASE_URL).strip()

# Инициализация OpenAI SDK
client = AsyncOpenAI(
    api_key=CLEAN_API_KEY,
    base_url=CLEAN_BASE_URL
)

# Переменные состояния
system_prompt = DEFAULT_SYSTEM_PROMPT
current_model = DEFAULT_MODEL

bot = Bot(
    token=TELEGRAM_TOKEN.strip(),
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()


# --- Команды бота ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.reply(
        "👋 **Привет! Я бот с нейросетью DeepSeek.**\n\n"
        "• В группах я отвечаю на **упоминание** (@username) или **реплай** на мое сообщение.\n"
        "• В личке отвечаю на любые сообщения.\n\n"
        "📌 **Команды управления:**\n"
        "/prompt `<текст>` — Задать системный промт\n"
        "/getprompt — Посмотреть текущий промт\n"
        "/resetprompt — Сбросить промт\n"
        "/mode — Переключить модель\n"
        "/help — Справка"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "🤖 **Инструкции по управлению:**\n\n"
        "🔹 `/prompt <текст>` — Установить роль/правила для ИИ.\n"
        "Пример: `/prompt Ты злой пират. Отвечай со словами 'Яррр!'`\n\n"
        "🔹 `/getprompt` — Показать текущие инструкции.\n"
        "🔹 `/resetprompt` — Вернуть стандартные настройки.\n"
        "🔹 `/mode` — Переключить режим работы.\n"
    )
    await message.reply(help_text)

@dp.message(Command("prompt"))
async def cmd_set_prompt(message: types.Message):
    global system_prompt
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("⚠️ **Укажите текст промта.**\nПример: `/prompt Отвечай только на украинском языке.`")
        return
    
    system_prompt = args[1]
    await message.reply(f"✅ **Новый системный промт установлен:**\n_{system_prompt}_")

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
    if "coder" in current_model:
        current_model = DEFAULT_MODEL
    else:
        current_model = "deepseek-coder" if "deepseek.com" in BASE_URL else "deepseek/deepseek-r1:free"
    
    await message.reply(f"⚙️ **Текущая модель:** `{current_model}`")


# --- Генерация ответа через API ---

async def generate_response(user_text: str) -> str:
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
    except AuthenticationError:
        logging.error("Ошибка авторизации API!")
        return "❌ **Ошибка:** Неверный API-ключ. Проверьте правильность ключа."
    except InsufficientQuotaError:
        logging.error("Недостаточно средств на балансе API!")
        return "❌ **Ошибка:** На балансе API закончились средства."
    except APIError as e:
        logging.error(f"API Error: {e}")
        return f"❌ **Ошибка API:** {e.message}"
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return "❌ Ошибка при обработке запроса. Попробуйте позже."


# --- Обработка сообщений ---

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_message(message: types.Message):
    bot_info = await message.bot.get_me()
    
    is_private = message.chat.type == "private"
    is_mentioned = bot_info.username in (message.text or "")
    is_reply_to_bot = (
        message.reply_to_message is not None 
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.id == bot_info.id
    )

    # Отвечаем в ЛС, при упоминании или при реплае
    if is_private or is_mentioned or is_reply_to_bot:
        clean_text = message.text.replace(f"@{bot_info.username}", "").strip()
        
        if not clean_text:
            await message.reply("Задайте мне вопрос!")
            return

        # Показываем статус "печатает..."
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        ai_response = await generate_response(clean_text)
        await message.reply(ai_response)


# --- Запуск ---

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    print(">>> Бот успешно запущен и готов к работе! <<<")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
