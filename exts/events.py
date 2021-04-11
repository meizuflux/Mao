import discord
from discord.ext import commands

from utils import Mao


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot: Mao = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("INSERT INTO guilds VALUES ($1)", guild.id)
                await conn.execute("INSERT INTO guild_config VALUES ($1)", guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        await self.bot.pool.execute("DELETE FROM guilds WHERE guild_id = $1", guild.id)


def setup(bot):
    bot.add_cog(Events(bot))
