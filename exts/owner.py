import contextlib
import io
import textwrap
import traceback
import import_expression

import discord
from discord.ext import commands
from jishaku.codeblocks import codeblock_converter
from tabulate import tabulate

import core
from utils import CustomContext, Mao, Timer, codeblock


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot: Mao = bot
        self.pool = self.bot.pool

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @core.command()
    async def eval(self, ctx: CustomContext, *, argument: codeblock_converter):
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'guild': ctx.guild,
            'message': ctx.message,
            'channel': ctx.channel
        }

        env.update(globals())
        stdout = io.StringIO()

        code = textwrap.indent(argument.content, '    ')
        imports = 'import discord\nfrom discord.ext import commands\n'
        to_execute = f"{imports}async def execute():\n{code}"

        try:
            import_expression.exec(to_execute, env, locals())
        except Exception as err:
            return await ctx.send(
                f"```py\n"
                f"{err.__class__.__name__}: {err}```"
            )

        try:
            with contextlib.redirect_stdout(stdout):
                ret = await locals()['execute']()
        except:
            value = stdout.getvalue()
            return await ctx.send(
                f"```py\n"
                f"{value}{traceback.format_exc()}```"
            )
        value = stdout.getvalue()
        try:
            await ctx.message.add_reaction('<:prettythumbsup:806390638044119050>')
        except (discord.HTTPException, discord.Forbidden):
            pass

        if not ret:
            if value:
                await ctx.send(
                    f"```py\n"
                    f"{value}```"
                )
        else:
            kwargs = {}
            if isinstance(ret, discord.Embed):
                kwargs['embed'] = ret
            if isinstance(ret, discord.File):
                kwargs['file'] = ret
            await ctx.send(
                f"```py\n"
                f"{value}{ret}```",
                **kwargs
            )

    @core.group()
    async def sql(self, ctx: CustomContext):
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @sql.command(aliases=('e',))
    async def execute(self, ctx: CustomContext, *, query: str):
        with Timer() as timer:
            ret = await self.pool.execute(query.strip('`'))
        await ctx.send(f"`{ret}`\n**Executed in {timer.ms}ms**")

    @sql.command(aliases=('f',))
    async def fetch(self, ctx: CustomContext, *, query: str):
        with Timer() as timer:
            ret = await self.pool.fetch(query.strip('`'))
        table = tabulate(
            (dict(row) for row in ret),
            headers='keys',
            tablefmt='github'
        )
        if len(table) > 1000:
            table = await ctx.mystbin(table)
        await ctx.send(f"{codeblock(table)}\n**Retrieved {len(ret)} rows in {timer.ms:.2f}ms**")

    @sql.command(aliases=('fv',))
    async def fetchval(self, ctx: CustomContext, *, query: str):
        with Timer() as timer:
            ret = await self.pool.fetchval(query.strip('`'))
        await ctx.send(f"{codeblock(f'{ret!r}')}\n**Retrieved in {timer.ms}ms**")


def setup(bot: Mao):
    bot.add_cog(Admin(bot))
