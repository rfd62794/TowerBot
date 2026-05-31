from dotenv import load_dotenv
load_dotenv()

from infra.db import init_db
init_db()

from bot.autonomous import run_autonomous_task
import asyncio

async def test():
    await run_autonomous_task('itch_reddit_check', print)

asyncio.run(test())
