from discord.ext import commands

from exts.handler.handler import Handler
from utils import CustomContext, Mao


class ErrorTracker(commands.Cog):
    def __init__(self, bot: Mao):
        self.bot = bot
        self.handler = Handler(self.bot)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: CustomContext, error: Exception):
        await self.handler.handle_error(ctx, error)

def setup(bot: Mao):
    bot.add_cog(ErrorTracker(bot))
