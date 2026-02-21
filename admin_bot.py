import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

ADMIN_BOT_TOKEN = "8320896381:AAGJoHkAV-Dfz9u6lbGRFeyOc83ye-4vXgo"  # <-- admin token

bot = Bot(token=ADMIN_BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def admin_start(message: Message):
    await message.answer("admin bot started 🔐")


async def start_admin_bot():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_admin_bot())
