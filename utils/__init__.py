import argparse
import asyncio
import logging
import os

import aiohttp
import discord
import toml
from discord.ext import commands, menus

from utils.context import CustomContext
from utils.db import *
from utils.errors import NotRegistered
from utils.timer import Timer

try:
    import uvloop # just a faster event loop
except ImportError:
    pass  # we're on windows
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger("Mao")
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
        with open("D:/coding/Mao/" + "/config.toml") as f:
            self.settings: dict = toml.loads(f.read())
        self.embed_color = 0xffc38f

        #   asyncio things
        self.loop = asyncio.get_event_loop()
        self._prepped = asyncio.Event()
        self.pool: Manager = self.loop.run_until_complete(
            create_pool(bot=self, dsn=self.settings['core']['postgres_dsn'], loop=self.loop)
        )
        
        self.loop.create_task(self.__prep())

        #  cache
        self.cache = {
            'registered_users': set(),
            'guilds': {
                'non_leveling': set(),
                'welcoming': set()
            }
        }
        self.non_leveling_guilds: set = set()
        self.registered_users: set = set()
        self._cd = commands.CooldownMapping.from_cooldown(5, 5, commands.BucketType.user)

        # management stuff
        self.encrypt_key = self.settings['misc']['encrypt_key'].encode('utf-8')

        #  bot management
        self.maintenance = False
        self.context = CustomContext

    async def __prep(self):
        self.session: aiohttp.ClientSession = aiohttp.ClientSession(loop=self.loop)
        self.error_webhook = discord.Webhook.from_url(
            self.settings["core"]["error_webhook"],
            adapter=discord.AsyncWebhookAdapter(self.session)
        )       
        async with self.pool.acquire() as conn:
            with open("D:/coding/Mao/" + "schema.sql") as f:
                    await conn.execute(f.read())
            await self.wait_until_ready()
            users = await conn.fetch("SELECT user_id FROM users")
            self.cache['registered_users'] = {user["user_id"] for user in users}

            await conn.executemany(
                "INSERT INTO guilds (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
                tuple((g.id,) for g in self.guilds)
            )

            await conn.executemany(
                "INSERT INTO guild_config (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
                tuple((g.id,) for g in self.guilds)
            )

            guilds = await conn.fetch("SELECT * FROM guild_config")
            for g in guilds:
                if not g['leveling']:
                    self.cache['guilds']['non_leveling'].add(g['guild_id'])
                if g['welcoming']:
                    self.cache['guilds']['welcoming'].add(g['guild_id'])
            self._prepped.set()
            logger.info("Finished prep")

    async def on_ready(self):
        logger.info("Connected to Discord.")

    async def get_context(self, message: discord.Message, *, cls=None):
        """Method to override "ctx"."""
        return await super().get_context(message, cls=cls or self.context)

    async def process_commands(self, message: discord.Message):
        if message.author.bot:
            return
        await self.wait_until_ready()
        bucket = self._cd.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    def run(self, *args, **kwargs):
        extensions = (
            'exts.cooldowns', 'exts.economy', 'exts.events', 'exts.tags',
            'exts.help', 'exts.owner', 'exts.handler', 'jishaku'
        )
        for file in extensions:
            try:
                self.load_extension(file)
            except Exception as err:  # if we don't catch this, the bot crashes. no please
                logger.error(f"{file} failed to load: {err.__class__.__name__}: {err}")
        logger.info("Loaded extensions.")
        super().run(*args, **kwargs)

    async def close(self):
        await self.session.close()
        await self.pool.close()
        await super().close()

    def embed(self, ctx=None, author=True, **kwargs):
        color = kwargs.pop("color", self.embed_color)
        embed = discord.Embed(**kwargs, color=color)
        if ctx:
            embed.timestamp = ctx.message.created_at
            if author:
                embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        return embed

    async def try_user(self, user_id: int) -> discord.User:
        """Method to try and fetch a user from cache then fetch from API."""
        user = self.get_user(user_id)
        if not user:
            user = await self.fetch_user(user_id)
        return user


class MaoPages(menus.MenuPages):
    def __init__(self, source, **kwargs):
        super().__init__(source=source, check_embeds=True, **kwargs)

    @menus.button('\N{BLACK SQUARE FOR STOP}\ufe0f', position=menus.Last(2))
    async def end_menu(self, _):
        await self.message.delete()
        self.stop()


def parse_number(argument: str, total: int) -> int:
    argument = argument.replace(",", "")
    if "e" in argument and argument.replace("e", "").isdigit():
        parts = argument.split("e")
        try:
            num = "0" * int(parts[1])
            amount = int(parts[0] + num)
        except ValueError:
            raise commands.BadArgument("Invalid amount provided.")
        except MemoryError:
            raise commands.BadArgument(
                "Woah, the number you provided was so large it broke Python. Try again with a smaller number.")

    elif argument.endswith("%"):
        argument = argument.strip("%")
        if not argument.isdigit():
            raise commands.BadArgument("That's... not a valid percentage.")
        argument = round(float(argument))
        if argument > 100:
            raise commands.BadArgument("You can't do more than 100%.")
        percentage = lambda percent, total_amount: (percent * total_amount) / 100
        amount = percentage(argument, total)

    elif argument == 'half':
        amount = total / 2

    elif argument in ('max', 'all'):
        amount = total
    elif argument.isdigit():
        amount = int(argument)
    else:
        raise commands.BadArgument("Invalid amount provided.")

    try:
        amount = int(round(amount))
    except OverflowError:
        raise commands.BadArgument(
            "Woah, the number you provided was so large it broke Python. Try again with a smaller number.")

    if amount == 0:
        raise commands.BadArgument("The amount you provided resulted in 0.")

    if amount > total:
        raise commands.BadArgument("That's more money than you have.")

    if amount > 100000000000:
        raise commands.BadArgument("Transfers of money over one hundred billion are prohibited.")

    return amount


def codeblock(t, *, lang='py'):
    return f'```{lang}\n{t}```'


class plural:
    def __init__(self, value):
        self.value = value

    #  modified code from stella
    def __format__(self, text):
        logic = self.value == 1
        target = (
            ("(s)", ("s", "")),
            ("(es)", ("es", "")),
            ("(is/are)", ("are", "is")),
            ("(is/ese)", ("ese", "is"))
        )
        for x, y in target:
            text = text.replace(x, y[logic])
        return text


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)
