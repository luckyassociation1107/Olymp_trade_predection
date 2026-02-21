from aiogram import Bot, Dispatcher, types
from config import ADMIN_BOT_TOKEN

bot = Bot(token=ADMIN_BOT_TOKEN)
admin_dp = Dispatcher()

@admin_dp.message(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("🔐 Admin Control Bot Active")