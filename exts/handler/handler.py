import discord
from discord.ext import commands
from humanize import naturaldelta

from utils import CustomContext, Mao
from contextlib import suppress


class Handler:
    def __init__(self, bot: Mao):
        self.bot = bot

    async def handle_command_error(self, ctx: CustomContext, error: commands.CommandError):
        owner_reinvoke = (
            commands.MissingAnyRole,
            commands.MissingPermissions,
            commands.MissingRole,
            commands.CommandOnCooldown,
            commands.DisabledCommand,
        )
        if isinstance(error, owner_reinvoke):
            await ctx.reinvoke()
            return

        if ctx.command.has_error_handler():
            return

        cog: commands.Cog = ctx.cog
        if cog and cog.has_error_handler():
            return

        error = getattr(error, 'original', error)
        command = ctx.command.qualified_name

        if isinstance(error, commands.CommandOnCooldown):
            retry = naturaldelta(error.retry_after)
            message = (
                f"**{command}** is on cooldown. Try again in {retry}.\n"
                f"You can use this command once every **{naturaldelta(error.cooldown.per)}**."
            )
            await ctx.send(message)
            return

        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                await ctx.author.send(f"{command} can only be used within a server.")

    async def handle_library_error(self, ctx: CustomContext, error: discord.DiscordException):
        if isinstance(error, commands.CommandError):
            await self.handle_command_error(ctx, error)
        else:
            await ctx.send(str(error))

    async def handle_error(self, ctx: CustomContext, error: Exception):
        if isinstance(error, discord.DiscordException):
            await self.handle_library_error(ctx, error)
