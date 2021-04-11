import asyncio
import logging
import os

import aiohttp
import asyncpg
import discord
import toml
from discord.ext import commands

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger("Walrus")
logging.basicConfig(
    format="%(levelname)s (%(name)s) |:| %(message)s |:| %(pathname)s:%(lineno)d",
    datefmt="%message/%d/%Y %-I:%M:%S",
    level=logging.INFO,
)


class Mao(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        #  core variables
        with open("config.toml") as f:
            self.settings = toml.loads(f.read())
        self.embed_color = "TBD"

        #   asyncio things
        self.loop = asyncio.get_event_loop()
        self.pool_pg: asyncpg.Pool = self.loop.run_until_complete(asyncpg.create_pool(dsn=self.settings['core']['postgres_dsn']))
        self.loop.create_task(self.__prep())

    async def __prep(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        with open("schema.sql") as f:
            await self.pool_pg.execute(f.read())

        async with self.pool_pg.acquire() as conn:
            async with conn.transaction():
                users = await conn.fetch("SELECT user_id FROM users")
                self.registered_users = {user["user_id"] for user in users}

    async def on_ready(self):
        logging.info("Connected to Discord.")

    def run(self, *args, **kwargs):
        for file in os.listdir("exts"):
            if not file.startswith("_"):
                self.load_extension(f'exts.{file[:-3]}')
        self.load_extension("jishaku")
        logger.info("Loaded extensions.")
        super().run(*args, **kwargs)

    async def close(self):
        await self.session.close()
        await self.pool_pg.close()
        await super().close()

    def embed(self, ctx, **kwargs):
        color = kwargs.pop("color", self.embed_color)
        embed = discord.Embed(**kwargs, color=color)
        embed.timestamp = ctx.message.created_at
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        return embed
