import logging
import random

import discord
from discord.ext import commands, tasks

from bot import Mao

log = logging.getLogger("Economy")


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot: Mao = bot
        self._data_batch = []
        self.bulk_insert_task.start()

    def cog_unload(self):
        self.bulk_insert_task.stop()

    async def register_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.author.id not in self.bot.registered_users:
            return
        xp = random.randint(66, 114)
        if data := self._data_batch:
            for msg in data:
                if msg['g'] == message.guild.id and msg['u'] == message.author.id:
                    msg['xp'] += xp
                    return
        self._data_batch.append(
            {
                'g': message.guild.id,
                'u': message.author.id,
                'xp': xp
            }
        )

    async def bulk_insert(self):
        if not self._data_batch:
            return
        async with self.bot.pool_pg.acquire() as conn:
            async with conn.transaction():
                query = (
                    """
                    UPDATE users SET xp = xp + $3
                    WHERE guild_id = $1 AND user_id = $2
                    """
                )
                await conn.executemany(
                    query,
                    tuple((msg['g'], msg['u'], msg['xp']) for msg in self._data_batch)
                )
        self._data_batch.clear()
        log.info("Inserted XP")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        await self.register_message(message)

    @tasks.loop(seconds=20)
    async def bulk_insert_task(self):
        await self.bulk_insert()

    @commands.command()
    async def data(self, ctx):
        await ctx.send(self._data_batch)


def setup(bot):
    bot.add_cog(Economy(bot))
