from collections import Mapping
from typing import List

import discord
from discord.ext import commands, menus

from utils import CustomContext, Mao, MaoPages


def get_sig(command, prefix):
    sig = command.usage or command.signature
    if not sig and not command.parent:
        return f'`{prefix}{command.name}`'
    if not command.parent:
        return f'`{prefix}{command.name}` `{sig}`'
    if not sig:
        return f'`{prefix}{command.parent}` `{command.name}`'
    return f'`{prefix}{command.parent}` `{command.name}` `{sig}`'


def add_formatting(command):
    fmt = '{0}' if command.short_doc else 'No help was provided for this command.'
    return fmt.format(command.short_doc)


class CogSource(menus.ListPageSource):
    def __init__(self, cog: commands.Cog, cog_commands: List[commands.Command], *, prefix):
        super().__init__(entries=cog_commands, per_page=4)
        self.cog = cog
        self.prefix = prefix

    async def format_page(self, menu, cmds: List[commands.Command]):
        ctx = menu.ctx
        page = f"{menu.current_page + 1}/{self.get_max_pages()}"
        embed = ctx.bot.embed(
            ctx,
            title=f"{self.cog.help_name} Commands | {page} ({len(self.entries)} Commands)"
        )

        for command in cmds:
            embed.add_field(
                name=get_sig(command, self.prefix),
                value=add_formatting(command).format(prefix=self.prefix),
                inline=False
            )

        if menu.current_page == 0:
            embed.description = self.cog.description

        return embed


class HelpMenu(menus.Menu):
    def __init__(self, data, prefix, **kwargs):
        super().__init__(**kwargs)
        self.message: discord.Message = None
        self.prefix = prefix
        self.data = data

    async def send_initial_message(self, ctx: CustomContext, channel: discord.TextChannel):
        description = (
            "<argument> means the argument is required",
            "[argument] means the argument is optional\n",
            f"Send `{self.prefix}help` `[command]` for more info on a command.",
            f"You can also send `{self.prefix}help` `[category]` for more info on a category."
        )
        embed = self.bot.embed(ctx, description="\n".join(description))
        embed.add_field(name="Categories", value="\n".join(self.data))

        self.message = await channel.send(embed=embed)
        return self.message

    @menus.button("\N{MONEY WITH WINGS}")
    async def economy_help(self, _):
        await self.message.delete()
        self.message = None
        await self.ctx.send_help(self.ctx.bot.get_cog("Economy"))

    @menus.button("\N{BLACK SQUARE FOR STOP}", position=menus.Last(2))
    async def stop(self, payload):
        await self.message.delete()
        self.message = None


class MaoHelp(commands.HelpCommand):
    async def filter_commands(self, commands, *, sort=True, key=None):
        if sort and key is None:
            key = lambda c: c.name

        iterator = commands if self.show_hidden else filter(lambda c: not c.hidden, commands)

        if self.verify_checks is False:
            return sorted(iterator, key=key) if sort else list(iterator)

        ret = [cmd for cmd in iterator]
        if sort:
            ret.sort(key=key)

        return ret

    async def send_error_message(self, error):
        bot = self.context.bot
        destination = self.get_destination()
        await destination.send(embed=bot.embed(self.context, description=str(error)))

    async def send_bot_help(self, data: Mapping[commands.Cog, List[commands.Command]]):
        items = {}
        for cog, cmds in data.items():
            if not hasattr(cog, 'help_name'):
                continue
            if sum(not cmd.hidden for cmd in cmds) == 0:
                continue

            items[cog.help_name] = await self.filter_commands(cmds)

        menu = HelpMenu(items, self.clean_prefix)
        await menu.start(self.context)

    async def send_cog_help(self, cog: commands.Cog):
        if not hasattr(cog, "help_name"):
            return await self.send_error_message(self.command_not_found(cog.qualified_name))
        menu = MaoPages(
            CogSource(
                cog,
                await self.filter_commands(cog.get_commands()),
                prefix=self.clean_prefix
            )
        )
        await menu.start(self.context)

    async def send_group_help(self, group: commands.Group):
        pass

    async def send_command_help(self, command: commands.Command):
        if not hasattr(command.cog, "help_name"):
            return await self.send_error_message(self.command_not_found(command.qualified_name))
        ctx = self.context
        embed = ctx.bot.embed(
            ctx,
            title=f"{command.cog.qualified_name.lower()}:{command.qualified_name}"
        )
        help = command.help or 'No help was provided for this command.'
        embed.description = help.format(prefix=self.clean_prefix)
        embed.add_field(
            name="Usage",
            value=get_sig(command, self.clean_prefix)
        )
        if aliases := command.aliases:
            embed.add_field(
                name="Aliases",
                value="`" + "`, `".join(aliases) + "`"
            )
        destination = self.get_destination()
        await destination.send(embed=embed)


def setup(bot: Mao):
    bot.help_command = MaoHelp()


def teardown(bot: Mao):
    bot.help_command = commands.HelpCommand()
