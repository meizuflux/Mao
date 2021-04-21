from collections import defaultdict

import asyncpg

from utils.context import CustomContext
from utils.errors import NotRegistered
from .__init__ import Mao


class Database(asyncpg.Pool):
    async def fetch_user_stats(self, ctx: CustomContext, **kwargs):
        items = kwargs.pop('items', ('cash', 'vault'))
        conn = kwargs.pop('con', self)
        user_id = kwargs.pop('user_id', ctx.author.id)

        query = "SELECT " + ", ".join(items) + " FROM users WHERE guild_id = $1 AND user_id = $2"
        stats = await conn.fetchrow(query, ctx.guild.id, user_id)
        if not stats:
            message = "That user is not registered." if user_id != ctx.author.id else "You are not registered."
            raise NotRegistered(message)
        try:
            if len(items) > 1:
                return tuple(stats.get(item) for item in items)
            return stats.get(items[0])
        finally:
            if kwargs.pop('release', False) and conn != self:
                await self.release(conn)

    async def update_user(self, ctx: CustomContext, method: str, value: int, **kwargs):
        if method not in ('cash', 'vault', 'xp', 'level'):
            raise TypeError("Invalid type provided.")
        conn = kwargs.pop('con', self)
        user_id = kwargs.pop('user_id', ctx.author.id)
        query = f"""UPDATE users SET {method} = {method} + $1 
                    WHERE guild_id = $2 AND user_id = $3"""
        await conn.execute(query, value, ctx.guild.id, user_id)
        if kwargs.pop('release', False) and conn != self:
            await self.release(conn)

    async def update_pet(self, ctx: CustomContext, name: str, **kwargs):  # TODO add valid values
        conn = kwargs.pop('con', self)
        user_id = kwargs.pop('user_id', ctx.author.id)
        query = """UPDATE users SET pet_name = $1 
                    WHERE guild_id = $2 AND user_id = $3"""
        await conn.execute(query, name, ctx.guild.id, user_id)
        if kwargs.pop('release', False) and conn != self:
            await self.release(conn)

    async def withdraw(self, ctx: CustomContext, amount: int, **kwargs):
        conn = kwargs.pop('con', self)
        query = """UPDATE users SET cash = cash + $1, vault = vault - $1
                    WHERE guild_id = $2 AND user_id = $3"""

        await conn.execute(query, amount, ctx.guild.id, ctx.author.id)
        if kwargs.pop('release', False) and conn != self:
            await self.release(conn)

    async def deposit(self, ctx: CustomContext, amount: int, **kwargs):
        conn = kwargs.pop('con', self)
        query = """UPDATE users SET cash = cash - $1, vault = vault + $1
                    WHERE guild_id = $2 AND user_id = $3"""

        await conn.execute(query, amount, ctx.guild.id, ctx.author.id)
        if kwargs.pop('release', False) and conn != self:
            await self.release(conn)


class Manager(asyncpg.Pool):
    def __init__(self, bot: Mao, *args, **kwargs):
        self.bot = bot
        self.cache = {}
        self.bot.loop.create_task(self.prepare_cache())
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
            'users': {},
            'guild_config': {}
        }
        cache = {guild.id: tables for guild in self.bot.guilds}

        async with self.acquire() as conn:
            for table in tables:
                data = await conn.fetch(f"SELECT * FROM {table}")
                for item in data:
                    item = dict(item)
                    if table == 'users':
                        cache[item.pop('guild_id')]['users'].update({item.pop('user_id'): item})
                    if table == 'guild_config':
                        cache[item.pop('guild_id')]['guild_config'] = item

            await self.release(conn)

        return cache

    async def prep_shutdown(self):
        ret = []
        for g, _data in self.cache.items():
            for u, data in _data['users'].items():
                ret.append(tuple((g, u, data['cash'], data['vault'], data['pet_name'], data['xp'], data['level'])))
        await self.executemany(
            "UPDATE users SET cash = $3, vault = $4, pet_name = $5, xp = $6, level = $7 WHERE guild_id = $1 AND user_id = $2",
            tuple(ret)
        )

    async def fetch_user_stats(self, ctx, **kwargs):
        user_id = kwargs.pop('user_id', ctx.author.id)
        if route := self.route(ctx, 'users', user_id):
            return route
        conn = kwargs.pop('conn', self)
        items = kwargs.pop('items', '*')
        query = "SELECT " + ", ".join(items) + " FROM users WHERE guild_id = $1 AND user_id = $2"
        data = dict(await conn.fetchrow(query, ctx.guild.id, user_id))
        try:
            if not data:
                message = "That user is not registered." if user_id != ctx.author.id else "You are not registered."
                raise NotRegistered(message)
            return data
        finally:
            await self.do_release(conn, kwargs.pop('release', False))

    async def edit_user(self, ctx: CustomContext, method: str, value: int, **kwargs):
        if method not in ('cash', 'vault', 'xp', 'level'):
            raise TypeError("Invalid method provided.")
        conn = kwargs.pop('conn', self)
        user_id = kwargs.pop('user_id', ctx.author.id)
        self.cache[ctx.guild.id]['users'][user_id][method] += value
        query = f"""UPDATE users SET {method} = {method} + $1 
                    WHERE guild_id = $2 AND user_id = $3"""
        await conn.execute(query, value, ctx.guild.id, user_id)
        await self.do_release(conn, kwargs.pop('release', False))

    async def edit_pet(self, ctx: CustomContext, name: str, **kwargs):  # TODO add valid values
        conn = kwargs.pop('conn', self)
        user_id = kwargs.pop('user_id', ctx.author.id)
        self.cache[ctx.guild.id]['users'][user_id]['pet_name'] = name
        query = """UPDATE users SET pet_name = $1 
                   WHERE guild_id = $2 AND user_id = $3"""
        await conn.execute(query, name, ctx.guild.id, user_id)
        await self.do_release(conn, kwargs.pop('release', False))

    async def withdraw(self, ctx: CustomContext, amount: int, **kwargs):
        self.cache[ctx.guild.id]['users'][ctx.author.id]['cash'] += amount
        self.cache[ctx.guild.id]['users'][ctx.author.id]['vault'] -= amount
        conn = kwargs.pop('conn', self)
        query = """UPDATE users SET cash = cash + $1, vault = vault - $1
                   WHERE guild_id = $2 AND user_id = $3"""
        await conn.execute(query, amount, ctx.guild.id, ctx.author.id)
        await self.do_release(conn, kwargs.pop('release', False))

    async def deposit(self, ctx: CustomContext, amount: int, **kwargs):
        self.cache[ctx.guild.id]['users'][ctx.author.id]['cash'] -= amount
        self.cache[ctx.guild.id]['users'][ctx.author.id]['vault'] += amount
        conn = kwargs.pop('conn', self)
        query = """UPDATE users SET cash = cash - $1, vault = vault + $1
                   WHERE guild_id = $2 AND user_id = $3"""
        await conn.execute(query, amount, ctx.guild.id, ctx.author.id)
        await self.do_release(conn, kwargs.pop('release', False))

    def route(self, ctx, *directions):
        ret = self.cache[ctx.guild.id]
        for place in directions:
            ret = ret.get(place, {})

        return ret or None

    async def do_release(self, conn, to_release):
        if to_release and conn != self:
            await super().release(conn)

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
    return Database(
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


def create_test_pool(
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
