import asyncio
from user_bot import user_dp
from admin_bot import admin_dp

async def main():
    await asyncio.gather(
        user_dp.start_polling(),
        admin_dp.start_polling()
    )

if __name__ == "__main__":
    asyncio.run(main())
