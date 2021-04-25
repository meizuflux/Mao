import json
import typing
from collections import defaultdict

import asyncpg

from utils.context import CustomContext
from utils.errors import NotRegistered
from .__init__ import Mao


class Database(asyncpg.Pool):
    pass


class WelcomeNode:
    def __init__(self, db: 'Manager', bot: Mao):
        self.bot: Mao = bot
        self.pool: Manager = db
        self.cache: dict = {}
        self.bot.loop.create_task(self._prepare_cache())

    async def _prepare_cache(self) -> None:
        await self.bot.wait_until_ready()
        self.cache = {guild.id: {} for guild in self.bot.guilds}
        welcome_data = await self.pool.fetch("SELECT * FROM welcome")
        for guild in welcome_data:
            data = dict(guild)
            self.cache.update({data.pop('guild_id'): data})

    async def first_insert(self, data: dict) -> None:
        query = """INSERT INTO welcome (guild_id, embed, dm, channel_id, role_id, message)
                   SELECT x.guild_id, x.embed, x.dm, x.channel_id, x.role_id, x.message
                   FROM jsonb_to_record($1) AS
                   x(guild_id BIGINT, embed BOOLEAN, dm BOOLEAN, channel_id BIGINT, role_id BIGINT, message VARCHAR)
                   """
        async with self.pool.acquire() as conn:
            await conn.execute(query, str(json.dumps(data)))
            await conn.execute("UPDATE guild_config SET welcoming = True WHERE guild_id = $1", data['guild_id'])

        self.bot.cache['guilds']['welcoming'].add(data['guild_id'])
        self.cache.update({data.pop('guild_id'): data})

    async def edit_value(self, ctx: CustomContext, method: str, new: typing.Union[bool, int, str]) -> None:
        query = f"UPDATE welcome SET {method} = $1 WHERE guild_id = $2"
        await self.pool.execute(query, new, ctx.guild.id)
        self.cache[ctx.guild.id][method] = new

    async def remove_guild(self, guild_id: int):
        del self.cache[guild_id]
        await self.pool.execute("DELETE FROM welcome WHERE guild_id = $1", guild_id)

    def from_cache(self, guild_id) -> dict:
        return self.cache.get(guild_id)


class EconomyNode:
    def __init__(self, db: 'Manager', bot: Mao):
        self.bot: Mao = bot
        self.pool: Manager = db
        self.cache: dict = {}
        self.bot.loop.create_task(self._prepare_cache())

    async def _prepare_cache(self) -> None:
        await self.bot.wait_until_ready()
        self.cache = {guild.id: {} for guild in self.bot.guilds}
        user_data = await self.pool.fetch("SELECT * FROM users")
        for user in user_data:
            data = dict(user)
            self.cache[data.pop('guild_id')].update({data.pop('user_id'): data})

    def from_cache(self, guild_id, user_id) -> dict:
        ret = self.cache.get(guild_id, {}).get(user_id, {})
        return ret or None

    async def get_user(self, ctx, user_id=None) -> dict:
        user_id = user_id or ctx.author.id
        if cached := self.from_cache(ctx.guild.id, user_id):
            return cached

        message = "That user is not registered." if user_id != ctx.author.id else "You are not registered."
        raise NotRegistered(message)

    async def edit_user(self, ctx: CustomContext, method: str, value: int, **kwargs) -> None:
        if method not in ('cash', 'vault', 'xp', 'level'):
            raise TypeError("Invalid method provided.")
        conn = kwargs.pop('conn', self.pool)
        user_id = kwargs.pop('user_id', ctx.author.id)

        self.cache[ctx.guild.id][user_id][method] += value
        query = f"UPDATE users SET {method} = {method} + $1 WHERE guild_id = $2 AND user_id = $3"
        await conn.execute(query, value, ctx.guild.id, user_id)

    async def edit_pet(self, ctx: CustomContext, name: str, **kwargs) -> None:  # TODO add valid values
        conn = kwargs.pop('conn', self.pool)
        user_id = kwargs.pop('user_id', ctx.author.id)

        self.cache[ctx.guild.id][user_id]['pet_name'] = name
        query = "UPDATE users SET pet_name = $1 WHERE guild_id = $2 AND user_id = $3"
        await conn.execute(query, name, ctx.guild.id, user_id)

    async def withdraw(self, ctx: CustomContext, amount: int, **kwargs) -> None:
        conn = kwargs.pop('conn', self.pool)

        self.cache[ctx.guild.id][ctx.author.id]['cash'] += amount
        self.cache[ctx.guild.id][ctx.author.id]['vault'] -= amount

        query = "UPDATE users SET cash = cash + $1, vault = vault - $1 WHERE guild_id = $2 AND user_id = $3"
        await conn.execute(query, amount, ctx.guild.id, ctx.author.id)

    async def deposit(self, ctx: CustomContext, amount: int, **kwargs) -> None:
        conn = kwargs.pop('conn', self.pool)

        self.cache[ctx.guild.id][ctx.author.id]['cash'] -= amount
        self.cache[ctx.guild.id][ctx.author.id]['vault'] += amount

        query = "UPDATE users SET cash = cash - $1, vault = vault + $1 WHERE guild_id = $2 AND user_id = $3"
        await conn.execute(query, amount, ctx.guild.id, ctx.author.id)

    async def unregister_user(self, ctx: CustomContext) -> bool:
        try:
            del self.cache[ctx.guild.id][ctx.author.id]
        except KeyError:
            return False
        else:
            await self.pool.execute(
                "DELETE FROM users WHERE guild_id = $1 AND user_id = $2",
                ctx.guild.id, ctx.author.id
            )
            return True

    async def register_user(self, ctx: CustomContext) -> bool:
        if self.cache.get(ctx.guild.id, {}).get(ctx.author.id):
            return False
        defaults = {
            'cash': 0,
            'vault ': 500,
            'pet_name': 'happy shiba',
            'xp': 0,
            'level': 1,
        }
        self.cache[ctx.guild.id][ctx.author.id] = defaults
        await self.pool.execute("INSERT INTO users VALUES ($1, $2)", ctx.guild.id, ctx.author.id)
        return True


class Manager(asyncpg.Pool):
    def __init__(self, bot: Mao, *args, **kwargs):
        self.bot = bot
        self.cache = {}
        self.bot.loop.create_task(self.prepare_cache())
        self.economy = EconomyNode(self, self.bot)
        self.welcome = WelcomeNode(self, self.bot)
        super().__init__(*args, **kwargs)

    async def prepare_cache(self):
        await self.bot.wait_until_ready()
        self.cache = await self.guild_cache()
        self.cache['cooldowns'] = {
            'guild': {g.id: defaultdict(dict) for g in self.bot.guilds},
            'user': defaultdict(dict)
        }
        cooldowns = await self.fetch('SELECT * FROM cooldowns')
        for cooldown in cooldowns:
            if g_id := cooldown['guild_id']:
                self.cache['cooldowns']['guild'][g_id][cooldown['user_id']][cooldown['command']] = cooldown['expires']
                continue
            self.cache['cooldowns']['user'][cooldown['user_id']][cooldown['command']] = cooldown['expires']

    async def guild_cache(self):
        tables = {
            'guild_config': {}
        }
        cache = {guild.id: tables for guild in self.bot.guilds}

        async with self.acquire() as conn:
            for table in tables:
                data = await conn.fetch(f"SELECT * FROM {table}")
                for item in data:
                    item = dict(item)
                    if table == 'guild_config':
                        cache[item.pop('guild_id')]['guild_config'] = item

        return cache

    def route(self, ctx, *directions):
        ret = self.cache[ctx.guild.id]
        for place in directions:
            ret = ret.get(place, {})

        return ret or None

    async def set_cooldown(self, ctx: CustomContext, epoch: float, guild: bool):
        command = ctx.command.qualified_name
        _type = 'guild' if guild else 'user'

        if _type == 'guild':
            self.cache['cooldowns'][_type][ctx.guild.id][ctx.author.id][command] = epoch
            if not ctx.guild:
                return
            items = (ctx.guild.id, ctx.author.id, command)
            await self.execute("DELETE FROM cooldowns WHERE guild_id = $1 AND user_id = $2 AND command = $3", *items)
            values = (ctx.guild.id, ctx.author.id, command, epoch)
            await self.execute("INSERT INTO cooldowns VALUES ($1, $2, $3, $4)", *values)

        elif _type == 'user':
            self.cache['cooldowns'][_type][ctx.author.id][command] = epoch
            items = (ctx.author.id, command)
            await self.execute("DELETE FROM cooldowns WHERE guild_id IS NULL AND user_id = $1 AND command = $2", *items)
            values = (ctx.author.id, command, epoch)
            await self.execute("INSERT INTO cooldowns (user_id, command, expires) VALUES ($1, $2, $3)", *values)


def create_pool(
        bot,
        dsn=None, *,
        min_size=10,
        max_size=10,
        max_queries=50000,
        max_inactive_connection_lifetime=300.0,
        setup=None,
        init=None,
        loop=None,
        connection_class=asyncpg.connection.Connection,
        record_class=asyncpg.protocol.Record,
        **connect_kwargs
):
    return Manager(
        bot,
        dsn,
        connection_class=connection_class,
        record_class=record_class,
        min_size=min_size,
        max_size=max_size,
        max_queries=max_queries,
        loop=loop,
        setup=setup,
        init=init,
        max_inactive_connection_lifetime=max_inactive_connection_lifetime,
        **connect_kwargs
    )
