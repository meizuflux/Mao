import logging
import random

import discord
from discord.ext import commands, tasks

from utils import Mao

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
        if message.guild.id not in self.bot.leveling_guilds:
            return
        if random.randint(1, 3) == 2:
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

    @commands.command(aliases=('toggle-leveling', 'toggleleveling'))
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def toggle_leveling(self, ctx):
        enabled = await self.bot.pool_pg.fetchval("SELECT leveling FROM guild_config WHERE guild_id = $1", ctx.author)
        leveling, msg = not enabled, "Enabled" if not enabled else "Disabled"
        await self.bot.pool_pg.execute("UPDATE guild_config SET leveling = $2 WHERE guild_id = $1", ctx.guild.id, leveling)
        await ctx.send("")

def setup(bot):
    bot.add_cog(Economy(bot))
