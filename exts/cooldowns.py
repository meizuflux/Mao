import time

from discord.ext import commands, tasks

from core import Command
from utils import CustomContext, Mao


class CooldownManager(commands.Cog):
    def __init__(self, bot):
        self.bot: Mao = bot
        self.destroy_expired_cooldowns.start()

    def cog_unload(self):
        self.destroy_expired_cooldowns.stop()

    @tasks.loop(hours=1)
    async def destroy_expired_cooldowns(self):
        await self.bot.pool.execute("DELETE FROM cooldowns WHERE expires < $1", time.time())

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
