import asyncpg

from utils.errors import NotRegistered
from utils.context import CustomContext


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

    async def update_pet(self, ctx: CustomContext, name: str, **kwargs): # TODO add valid values
        conn = kwargs.pop('con', self)
        user_id = kwargs.pop('user_id', ctx.author.id)
        query = """UPDATE users SET pet_name = $1 
                    WHERE guild_id = $2 AND user_id = $3"""
        await conn.execute(query, name, ctx.guild.id, user_id)
        if kwargs.pop('release', False) and conn != self:
            await self.release(conn)

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
