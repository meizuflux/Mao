import logging
import random
import traceback

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
        self._data_batch.append(
            {
                'guild_id': message.guild.id,
                'user_id': message.author.id,
                'xp': random.randint(66, 114)
            }
        )
        log.info(f"Registered message from {message.author}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.author.id not in self.bot.registered_users:
            return
        await self.register_message(message)

    @tasks.loop(seconds=15)
    async def bulk_insert_task(self):
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
                    tuple((msg['guild_id'], msg['user_id'], msg['xp']) for msg in self._data_batch)
                )
        log.info("Inserted XP")

    @bulk_insert_task.error
    async def your_task_error(self, error):
        formatted = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        print(formatted)

    @commands.command()
    async def data(self, ctx):
        await ctx.send(self._data_batch)


def setup(bot):
    bot.add_cog(Economy(bot))
