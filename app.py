import asyncio
from user_bot import start_user_bot
from admin_bot import start_admin_bot

async def main():
    await asyncio.gather(
        start_user_bot(),
        start_admin_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())
