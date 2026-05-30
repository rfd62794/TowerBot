import asyncio
from dotenv import load_dotenv
load_dotenv()
from infra.db import init_db
init_db()
from bot.scheduler import morning_briefing

async def show(msg): print(msg)
asyncio.run(morning_briefing(show))
