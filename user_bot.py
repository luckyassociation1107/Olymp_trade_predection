from aiogram import Bot, Dispatcher, types
from config import USER_BOT_TOKEN

bot = Bot(token=USER_BOT_TOKEN)
user_dp = Dispatcher()

@user_dp.message(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("🤖 User Prediction Bot Active")