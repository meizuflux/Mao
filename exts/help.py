from collections import Mapping
from typing import List

import discord
from discord.ext import commands, menus

from utils import CustomContext, Mao


class HelpMenu(menus.Menu):
    def __init__(self, data, prefix, **kwargs):
        super().__init__(**kwargs)
        self.message: discord.Message = None
        self.prefix = prefix
        self.data = data

    async def _send_cog_help(self, cog_name):
        await self.message.delete()
        self.message = None
        cog = self.bot.get_cog(cog_name)


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
    async def economy_help(self, payload):
        menu = await self._send_cog_help("Economy")


class MaoHelp(commands.HelpCommand):
    async def filter_commands(self, commands, *, sort=False, key=None):
        if sort and key is None:
            key = lambda c: c.name

        iterator = commands if self.show_hidden else filter(lambda c: not c.hidden, commands)

        if self.verify_checks is False:
            return sorted(iterator, key=key) if sort else list(iterator)

        ret = [cmd for cmd in iterator]
        if sort:
            ret.sort(key=key)

        return ret

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


def setup(bot: Mao):
    bot.help_command = MaoHelp()


def teardown(bot: Mao):
    bot.help_command = commands.HelpCommand()
