import time

from discord.ext import commands

from core import Command
from utils import CustomContext, Mao


class CooldownManager(commands.Cog):
    def __init__(self, bot):
        self.bot: Mao = bot

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: CustomContext):
        if not isinstance(ctx.command, Command):
            return
        if not ctx.command.cd:
            return
        epoch = time.time() + ctx.command.cd.rate
        await self.bot.pool.set_cooldown(ctx, epoch, ctx.command.cd.guild)


def setup(bot):
    bot.add_cog(CooldownManager(bot))
