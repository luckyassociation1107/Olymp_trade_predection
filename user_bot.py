import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

BOT_TOKEN = "8361917661:AAFjCkSYgZZm5BJaxHn8vst1nDDRHhrbeIY"  # <-- your token here

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("user bot started ✅")


async def start_user_bot():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_user_bot())
