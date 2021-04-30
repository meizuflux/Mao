from contextlib import suppress
from json import dumps

import discord
from discord.ext import commands
from humanize import naturaldelta

from exts.handler.serialize import Serialized
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

        if isinstance(error, commands.CheckFailure):
            return await ctx.send(embed=self.bot.embed(ctx, description=str(error)))

        if isinstance(error, commands.NoPrivateMessage):
            with suppress(discord.HTTPException):
                await ctx.author.send(f"{command} can only be used within a server.")

        if isinstance(error, commands.MissingRequiredArgument):
            errors = str(error).split(" ", maxsplit=1)
            msg = (
                f'`{errors[0]}` {errors[1]}\n'
                f'You can view the help for this command with `{ctx.clean_prefix}help` `{command}`'
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
        frame = error.__traceback__
        q = """
            INSERT INTO errors (error, traceback, frame, context) VALUES ($1, $2, $3, $4)
            """
        serialized = Serialized(error, ctx).to_dict()
        await self.pool.execute(q, serialized['error'], serialized['traceback'], serialized['frame'], [serialized['context']])
        query = """
                SELECT
                    error
                FROM 
                    errors 
                WHERE
                    frame -> 'filename' = $1
                    AND (
                        frame -> 'function' = $2
                        OR error = $3
                    )
                """
        data = await self.pool.fetchrow(query, dumps(frame.tb_frame.f_code.co_filename), dumps(frame.tb_frame.f_code.co_name), str(error))
