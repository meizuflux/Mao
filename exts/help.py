import asyncio
import logging
from collections import Mapping
from typing import List, Union

import discord
from discord.ext import commands, menus
from discord.ext.menus import CannotAddReactions, CannotEmbedLinks, CannotReadMessageHistory, CannotSendMessages

import core
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
        name = self.cog.qualified_name
        if hasattr(self.cog, 'help_name'):
            name = self.cog.help_name
        embed = ctx.bot.embed(
            ctx,
            title=f"{name} Commands | {page} ({len(self.entries)} Commands)"
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
        self.message = None
        self.prefix = prefix
        self.data = data

    async def _send_cog_help(self, cog_name):
        await self.message.delete()
        self.message = None
        await self.ctx.send_help(self.ctx.bot.get_cog(cog_name))

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
        await self._send_cog_help("Economy")

    @menus.button("\N{BLACK SQUARE FOR STOP}", position=menus.Last(2))
    async def stop(self, _):
        await self.message.delete()
        self.message = None


class Menu:
    def __init__(self, prefix: str, mapping: dict, *, timeout=180.0, delete_message_after=False, check_embeds=False,
                 message=None):
        self.prefix = prefix
        self.timeout = timeout
        self.delete_message_after = delete_message_after
        self.check_embeds = check_embeds
        self._can_remove_reactions = False
        self.__tasks = []
        self._running = True
        self.message = message
        self.ctx = None
        self.bot = None
        self.__me = None
        self._author_id = None
        self.buttons = mapping
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()

    def should_add_reactions(self):
        return len(self.buttons)

    def _verify_permissions(self, permissions):
        if not permissions.send_messages:
            raise CannotSendMessages()

        if self.check_embeds and not permissions.embed_links:
            raise CannotEmbedLinks()

        self._can_remove_reactions = permissions.manage_messages
        if self.should_add_reactions():
            if not permissions.add_reactions:
                raise CannotAddReactions()
            if not permissions.read_message_history:
                raise CannotReadMessageHistory()

    def reaction_check(self, payload):
        if payload.message_id != self.message.id:
            return False
        if payload.user_id not in {self.bot.owner_id, self._author_id, *self.bot.owner_ids}:
            return False
        return str(payload.emoji) in self.buttons.keys()

    async def _internal_loop(self):
        try:
            self.__timed_out = False
            loop = self.bot.loop
            # Ensure the name exists for the cancellation handling
            tasks = []
            while self._running:
                tasks = [
                    asyncio.ensure_future(self.bot.wait_for('raw_reaction_add', check=self.reaction_check)),
                    asyncio.ensure_future(self.bot.wait_for('raw_reaction_remove', check=self.reaction_check))
                ]
                done, pending = await asyncio.wait(tasks, timeout=self.timeout, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()

                if len(done) == 0:
                    raise asyncio.TimeoutError()

                # Exception will propagate if e.g. cancelled or timed out
                payload = done.pop().result()
                loop.create_task(self.update(payload))

        except asyncio.TimeoutError:
            self.__timed_out = True
        finally:
            self._event.set()

            for task in tasks:
                task.cancel()

            self.__timed_out = False

            if self.bot.is_closed():
                return

            try:
                if self.delete_message_after:
                    return await self.message.delete()
            except Exception:
                pass

    async def update(self, payload):
        if not self._running:
            return

        try:
            self.stop()
            if str(payload.emoji) != "\N{BLACK SQUARE FOR STOP}":
                await self.ctx.send_help(self.ctx.bot.get_cog(self.buttons[str(payload.emoji)]))
        except Exception as exc:
            await self.on_menu_button_error(exc)

    async def on_menu_button_error(self, exc):
        logging.exception("Unhandled exception during menu update.", exc_info=exc)

    async def start(self, ctx, *, channel=None, wait=False):
        self.bot = bot = ctx.bot
        self.ctx = ctx
        self._author_id = ctx.author.id
        channel = channel or ctx.channel
        is_guild = isinstance(channel, discord.abc.GuildChannel)
        me = channel.guild.me if is_guild else ctx.bot.user
        permissions = channel.permissions_for(me)
        self.__me = discord.Object(id=me.id)
        self._verify_permissions(permissions)
        self._event.clear()
        msg = self.message
        if msg is None:
            self.message = msg = await self.send_initial_message(ctx, channel)

        if self.should_add_reactions():
            # Start the task first so we can listen to reactions before doing anything
            for task in self.__tasks:
                task.cancel()
            self.__tasks.clear()

            self._running = True
            self.__tasks.append(bot.loop.create_task(self._internal_loop()))

            async def add_reactions_task():
                for emoji in self.buttons:
                    await msg.add_reaction(emoji)

            self.__tasks.append(bot.loop.create_task(add_reactions_task()))

            if wait:
                await self._event.wait()

    async def send_initial_message(self, ctx: CustomContext, channel: discord.TextChannel):
        description = (
            "<argument> means the argument is required",
            "[argument] means the argument is optional\n",
            f"Send `{self.prefix}help` `[command]` for more info on a command.",
            f"You can also send `{self.prefix}help` `[category]` for more info on a category."
        )
        embed = self.bot.embed(ctx, description="\n".join(description))
        embed.add_field(name="Categories", value="\n".join(f'{emoji} {name}' for emoji, name in self.buttons.items()
                                                           if emoji != '\N{BLACK SQUARE FOR STOP}'))

        self.message = await channel.send(embed=embed)
        return self.message

    def stop(self):
        """Stops the internal loop."""
        self._running = False
        for task in self.__tasks:
            task.cancel()
        self.__tasks.clear()


class MaoHelp(commands.HelpCommand):
    async def filter_commands(self, cmds, *, sort=True, key=None):
        if sort and key is None:
            key = lambda c: c.name

        iterator = cmds if self.show_hidden else list(filter(lambda c: not c.hidden, cmds))

        if self.verify_checks is False:
            return sorted(iterator, key=key) if sort else list(iterator)

        if sort:
            iterator.sort(key=key)

        return iterator

    async def send_error_message(self, error):
        bot = self.context.bot
        destination = self.get_destination()
        await destination.send(embed=bot.embed(self.context, description=str(error)))

    async def send_bot_help(self, mapping: Mapping[commands.Cog, List[Union[core.command, commands.Command]]]):
        items = {'\N{BLACK SQUARE FOR STOP}': None}
        for cog in mapping:
            if not hasattr(cog, 'help_name'):
                continue
            name = cog.help_name.split(' ', maxsplit=1)
            items[name[0]] = name[1]

        menu = Menu(prefix=self.clean_prefix, mapping=items, delete_message_after=True)
        await menu.start(self.context)

    async def send_cog_help(self, cog: commands.Cog):
        if not hasattr(cog, "help_name") and not await self.context.bot.is_owner(self.context.author):
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

    async def send_command_help(self, command: core.Command):
        if not hasattr(command.cog, "help_name") and not await self.context.bot.is_owner(self.context.author):
            return await self.send_error_message(self.command_not_found(command.qualified_name))
        ctx = self.context
        embed = ctx.bot.embed(
            ctx,
            title=f"{command.cog.qualified_name.lower()}:{command.qualified_name}"
        )
        help_string = command.help or 'No help was provided for this command.'
        embed.description = help_string.format(prefix=self.clean_prefix)
        embed.add_field(
            name="Usage",
            value=get_sig(command, self.clean_prefix),
            inline=False
        )
        embed.add_field(
            name="Permissions",
            value=(
                f"Permissions **you** need: `{'`, `'.join(command.user_perms)}`\n"
                f"Permissions **I** need: `{'`, `'.join(command.bot_perms)}`\n"
            )
        )
        if aliases := command.aliases:
            embed.add_field(
                name="Aliases",
                value="`" + "`, `".join(aliases) + "`",
                inline=False
            )
        if examples := command.examples:
            embed.add_field(
                name="Examples",
                value="\n".join(
                    f'`{self.clean_prefix}{command.qualified_name}` `{example}`' if example else f'`{self.clean_prefix}{command.qualified_name}`'
                    for example in examples
                )
            )

        destination = self.get_destination()
        await destination.send(embed=embed)


def setup(bot: Mao):
    bot.help_command = MaoHelp()


def teardown(bot: Mao):
    bot.help_command = commands.HelpCommand()
