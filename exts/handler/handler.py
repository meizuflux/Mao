import traceback
from contextlib import suppress
from json import dumps

import discord
from discord.ext import commands
from humanize import naturaldelta

from utils import CustomContext, Mao


class Handler:
    def __init__(self, bot: Mao):
        self.bot = bot
        self.pool = self.bot.pool

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

        command = None

        if ctx.command:
            if ctx.command.has_error_handler():
                return

            cog: commands.Cog = ctx.cog
            if cog and cog.has_error_handler():
                return

            command = ctx.command.qualified_name

        error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandOnCooldown):
            retry = naturaldelta(error.retry_after)
            message = (
                f"**{command}** is on cooldown. Try again in {retry}.\n"
                f"You can use this command once every **{naturaldelta(error.cooldown.per)}**."
            )
            await ctx.send(message)
            return

        if isinstance(error, commands.CheckFailure):
            return await ctx.send(embed=self.bot.embed(ctx, description=str(error)))

        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                await ctx.author.send(f"{command} can only be used within a server.")

        if isinstance(error, commands.MissingRequiredArgument):
            errors = str(error).split(" ", maxsplit=1)
            msg = (
                f'`{errors[0]}` {errors[1]}\n'
                f'You can view the help for this command with `{ctx.prefix}help` `{command}`'
            )
            embed = self.bot.embed(ctx, description=msg)
            return await ctx.send(embed=embed)

        if isinstance(error, commands.DisabledCommand):
            return await ctx.send(embed=self.bot.embed(ctx, description=f'`{command}` has been disabled.'))

        if isinstance(error, commands.BadArgument):
            return await ctx.send(embed=self.bot.embed(ctx, title=str(error)))

    async def handle_library_error(self, ctx: CustomContext, error: discord.DiscordException):
        if isinstance(error, commands.CommandError):
            await self.handle_command_error(ctx, error)
        else:
            await ctx.send(str(error))

    async def handle_error(self, ctx: CustomContext, error: Exception):
        if isinstance(error, discord.DiscordException):
            await self.handle_library_error(ctx, error)
        else:
            if ctx.command:
                if ctx.command.has_error_handler():
                    return

                cog: commands.Cog = ctx.cog
                if cog and cog.has_error_handler():
                    return

            error = getattr(error, 'original', error)
            formatted = traceback.format_exception(type(error), error, error.__traceback__)

            desc = (
                f"Command: {ctx.invoked_with}\n"
                f"Full content: {ctx.message.content}\n"
                f"Guild: {ctx.guild.name} ({ctx.guild.id})\n"
                f"Channel: {ctx.channel.name} ({ctx.channel.id})\n"
                f"User: {ctx.author.name} ({ctx.author.id})\n"
                f"Jump URL: {ctx.message.jump_url}"
            )
            embed = self.bot.embed(ctx, title='AN ERROR OCCURRED', description=desc)
            await self.bot.error_webhook.send(f"```py\n" + ''.join(formatted) + f"```", embed=embed)

            await ctx.send(
                f"Oops, an error occured. Sorry about that."
                f"```py\n{''.join(formatted)}\n```"
            )


