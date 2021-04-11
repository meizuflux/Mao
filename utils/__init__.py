import asyncio
import logging
import os

import aiohttp
import discord
import toml
from discord.ext import commands, menus

from utils.db import Database, create_pool
from utils.errors import NotRegistered

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
        self._BotBase__cogs = commands.core._CaseInsensitiveDict()

        #  core variables
        with open("config.toml") as f:
            self.settings: dict = toml.loads(f.read())
        self.embed_color = 0xffc38f

        #   asyncio things
        self.loop = asyncio.get_event_loop()
        self.pool: Database = self.loop.run_until_complete(
            create_pool(dsn=self.settings['core']['postgres_dsn'], loop=self.loop)
        )
        self.loop.create_task(self.__prep())

        #  cache
        self.non_leveling_guilds: set = set()
        self.registered_users: set = set()

    async def __prep(self):
        await self.wait_until_ready()
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.error_webhook = discord.Webhook.from_url(
            self.settings["core"]["error_webhook"],
            adapter=discord.AsyncWebhookAdapter(self.session)
        )

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                with open("schema.sql") as f:
                    await conn.execute(f.read())

                users = await conn.fetch("SELECT user_id FROM users")
                self.registered_users = {user["user_id"] for user in users}

                await conn.executemany("INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
                                       tuple((g.id,) for g in self.guilds))

                await conn.executemany("INSERT INTO guild_config (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
                                       tuple((g.id,) for g in self.guilds))

                leveling = await conn.fetch("SELECT guild_id FROM guild_config WHERE leveling = False")
                self.non_leveling_guilds = {guild['guild_id'] for guild in leveling}
                logging.info("Finished prep")

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
        await self.pool.close()
        await super().close()

    def embed(self, ctx, author=True, **kwargs):
        color = kwargs.pop("color", self.embed_color)
        embed = discord.Embed(**kwargs, color=color)
        embed.timestamp = ctx.message.created_at
        if author:
            embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        return embed


class CustomContext(commands.Context):
    async def mystbin(self, data):
        data = bytes(data, 'utf-8')
        async with aiohttp.ClientSession() as cs:
            async with cs.post('https://mystb.in/documents', data=data) as r:
                res = await r.json()
                key = res["key"]
                return f"https://mystb.in/{key}"

    def escape(self, text: str):
        mark = [
            '`',
            '_',
            '*'
        ]
        for item in mark:
            text = text.replace(item, f'\u200b{item}')
        return


async def get_user_stats(ctx: CustomContext, user_id: int = None, items: iter = ('cash', 'vault')):
    user = user_id or ctx.author.id
    query = "SELECT " + ", ".join(items) + " FROM users WHERE guild_id = $1 AND user_id = $2"
    stats = await ctx.bot.pool.fetchrow(query, ctx.guild.id, user)
    if not stats:
        message = "That user is not registered." if user != ctx.author.id else "You are not registered."
        raise NotRegistered(message)
    return tuple(stats.get(item) for item in items)


class MaoPages(menus.MenuPages):
    def __init__(self, source, **kwargs):
        super().__init__(source=source, check_embeds=True, **kwargs)
