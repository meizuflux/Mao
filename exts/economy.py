import functools
import logging
import math
import random
import shlex
import typing
from dataclasses import dataclass

import discord
from discord.ext import commands, tasks

import core
from rank_card import Generator
from utils import Arguments, CustomContext, Mao, messages, parse_number

log = logging.getLogger("Economy")


@dataclass
class Pet:
    name: str
    description: str
    price: int
    boost: int


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot: Mao = bot
        self.help_name = f"\N{MONEY WITH WINGS} {self.__class__.__name__}"
        self._data_batch = []
        self.bulk_insert_task.start()
        self._cooldown = commands.CooldownMapping.from_cooldown(2, 5, commands.BucketType.member)

        self.economy = self.bot.pool.economy

    def cog_unload(self):
        self.bot.loop.create_task(self.bulk_insert_task)
        self.bulk_insert_task.stop()

    async def bulk_insert(self):
        if not self._data_batch:
            return
        async with self.bot.pool.acquire() as conn:
            query = (
                """
                UPDATE users SET xp = xp + $3
                WHERE guild_id = $1 AND user_id = $2
                """
            )
            await conn.executemany(
                query,
                tuple((m['guild'], m['user'], m['xp']) for m in self._data_batch)
            )
        log.info(f"Inserted XP. Messages: {len(self._data_batch)}")
        self._data_batch.clear()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.bot.wait_until_ready()
        if message.author.bot:
            return
        if message.guild.id in self.bot.cache['guilds']['non_leveling']:
            return
        if message.author.id not in self.bot.cache['registered_users']:
            return
        bucket = self._cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return
        xp = random.randint(15, 56)
        self.economy.cache[message.guild.id][message.author.id]['xp'] += xp
        self._data_batch.append(
            {
                'guild': message.guild.id,
                'user': message.author.id,
                'xp': xp
            }
        )

    @tasks.loop(seconds=20)
    async def bulk_insert_task(self):
        await self.bulk_insert()

    @core.command(
        name="toggle-leveling",
        aliases=('toggleleveling', 'toggle_leveling'),
        bot_perms=('Send Messages',)
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def toggle_leveling(self, ctx: CustomContext):
        """Enables/disables leveling on this server."""
        enabled = ctx.guild.id in self.bot.cache['guilds']['non_leveling']
        leveling, msg = not enabled, "Enabled" if not enabled else "Disabled"
        query = (
            """
            UPDATE guild_config SET leveling = $2
            WHERE guild_id = $1
            """
        )
        await self.bot.pool.execute(query, ctx.guild.id, leveling)
        await ctx.send(f"{msg} leveling on {ctx.guild.name}.")
        method = getattr(self.bot.cache['guilds']['non_leveling'], "remove" if leveling else "add")
        method(ctx.guild.id)

    @core.command(
        aliases=('register-account',)
    )
    async def register(self, ctx: CustomContext):
        """Registers you into the user database.
        You can unregister with `{prefix}unregister`"""
        worked = await self.economy.register_user(ctx)
        if not worked:
            return await ctx.send("You are already registered!")
        self.bot.cache['registered_users'].add(ctx.author.id)
        await ctx.send("Registered you into the database.")

    @core.command(
        aliases=('bal', 'account'),
        examples=('@user', None),
        bot_perms=('Send Messages', 'Embed Links', 'Use External Emojis'),
        cd=core.Cooldown(2, False)
    )
    async def balance(self, ctx: CustomContext, user: discord.User = None):
        """View yours or someone else's balance."""
        user = user or ctx.author
        data = await self.economy.get_user(ctx, user_id=user.id)
        level = data['level']
        total_xp = data['xp'] - 1000
        for num in range(level + 1):
            total_xp += num * 1000

        message = (
            f"💸 **Cash** → {data['cash']}",
            f"💰 **Vault** → {data['vault']}",
            f"🐊 **Pet** → {data['pet_name'].title()}",
            f"<:feyes:819694934209855488> **XP** → {data['xp']} ({total_xp} total)",
            f"🥗 **Level** → {level}"
        )
        embed = self.bot.embed(ctx, author=False, title=f"{user.name}'s balance", description="\n".join(message))
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)

    @core.command(
        name='level-up',
        aliases=('lvlup', 'levelup'),
        bot_perms=('Send Messages',)
    )
    async def level_up(self, ctx: CustomContext):
        """Levels you up to the next level."""
        if ctx.guild.id in self.bot.non_leveling_guilds:
            return await ctx.send("Leveling isn't enabled on your server.")
        data = await self.economy.get_user(ctx)
        level = data['level']
        cost = level * 1000
        xp_needed = max((level * 1000) - data['xp'], 0)

        if xp_needed != 0:
            return await ctx.send(f"You need {xp_needed} more XP in order to level up to level {level + 1}")

        query = (
            """
            UPDATE users SET level = level + 1, xp = $3
            WHERE guild_id = $1 AND user_id = $2
            """
        )
        await self.bot.pool.execute(query, ctx.guild.id, ctx.author.id, data['xp'] - cost)
        await ctx.send(f"Leveled you up to level {level + 1}!")

    @core.command(
        aliases=('xp', 'lvl', 'profile'),
        examples=('@user', None),
        bot_perms=('Send Messages', 'Attach Files')
    )
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    async def level(self, ctx: CustomContext, user: discord.User = None):
        """View a user's level on the server.
        Leveling must be toggled on in order for this to work."""
        if ctx.guild.id in self.bot.non_leveling_guilds:
            return await ctx.send("Leveling isn't enabled on your server.")
        user = user or ctx.author
        data = await self.economy.get_user(ctx, user_id=user.id)
        kwargs = {
            'profile_image': user.avatar_url_as(format="png"),
            'level': data['level'],
            'user_xp': data['xp'],
            'next_xp': data['level'] * 1000,
            'user_name': str(user),
        }
        generator = functools.partial(Generator().generate_profile, **kwargs)
        image = await self.bot.loop.run_in_executor(None, generator)
        file = discord.File(fp=image, filename="image.png")
        await ctx.send(file=file)

    @core.command(cd=core.Cooldown(rate=300, guild=True))
    async def work(self, ctx: CustomContext):
        """Work for a little bit of money eh?"""
        amount = random.randint(170, 567)
        await self.economy.edit_user(ctx, method='cash', value=amount)
        await ctx.send(embed=self.bot.embed(ctx, description=messages.work_message(amount)))

    @core.command(
        aliases=('wd', 'with'),
        examples=('half', '56%', '18', 'all')
    )
    async def withdraw(self, ctx: CustomContext, amount: str):
        """Withdraw money from your vault."""
        async with self.bot.pool.acquire() as conn:
            data = await self.economy.get_user(ctx)
            amount = parse_number(argument=amount, total=data['vault'])
            await self.economy.withdraw(ctx, amount=amount, conn=conn, release=True)
        await ctx.send(embed=self.bot.embed(ctx, description=f"You withdraw **${amount}** from your vault."))

    @core.command(
        aliases=('dep',),
        examples=('half', '56%', '18', 'all')
    )
    async def deposit(self, ctx: CustomContext, amount: str):
        """Withdraw money from your vault."""
        async with self.bot.pool.acquire() as conn:
            data = await self.economy.get_user(ctx)
            amount = parse_number(argument=amount, total=data['cash'])
            await self.economy.deposit(ctx, amount=amount, conn=conn, release=True)
        await ctx.send(embed=self.bot.embed(ctx, description=f"You deposit **${amount}** to your vault."))

    @core.command(
        cd=core.Cooldown(86400, True)
    )
    async def daily(self, ctx: CustomContext):
        """Collect money daily."""
        async with self.bot.pool.acquire() as conn:
            data = await self.economy.get_user(ctx)
            boost = data['level'] * 0.02
            await self.economy.edit_user(ctx, 'cash', int(500 * (boost + 1)), conn=conn, release=True)
        embed = self.bot.embed(
            ctx,
            description=f"You collect **$500**. "
                        f"Because you are level {data['level']}, you earn an extra **${int(500 * boost)}**"
        )
        await ctx.send(embed=embed)

    @core.command(
        aliases=('lb', 'top', 'highest'),
        examples=(
                '1 --cash',
                '--vault',
                '5',
        ),
        usage="[page=1] [--cash | --vault | --level]",
        cd=core.Cooldown(5, False)
    )
    async def leaderboard(self, ctx: CustomContext, page: typing.Optional[int] = 1, flags: str = None):
        queries = {
            'count': "SELECT COUNT(user_id) FROM users",
            'total': {
                'query': "SELECT user_id, cash + vault AS total FROM users WHERE guild_id = $1 ORDER BY cash + vault     DESC OFFSET $2 LIMIT 10",
                'line': "**{num}.** **{name}** » **${total}**"
            },
            'cash': {
                'query': "SELECT user_id, cash AS total FROM users WHERE guild_id = $1 ORDER BY cash DESC OFFSET $2 LIMIT 10",
                'line': "**{num}.** **{name}** » **${total}**"
            },
            'vault': {
                'query': "SELECT user_id, vault AS total FROM users WHERE guild_id = $1 ORDER BY vault DESC OFFSET $2 LIMIT 10",
                'line': "**{num}.** **{name}** » **${total}**"
            },
            'xp': {
                'query': "SELECT user_id, level, xp FROM users WHERE guild_id = $1 ORDER BY level DESC OFFSET $2 LIMIT 10",
                'line': "**{num}.** **{name}** » Level: **{level}** Total XP: **{total_xp}**"
            }
        }
        flag = 'total'
        if flags:
            parser = Arguments(allow_abbrev=False, add_help=False)
            parser.add_argument("-c", "-cash", "--cash", action="store_true", default=False)
            parser.add_argument("-v", "-vault", "--vault", action="store_true", default=False)
            parser.add_argument("-level", "-xp", "--level", "--xp", action="store_true", default=False)
            try:
                args = parser.parse_args(shlex.split(flags))
            except RuntimeError as e:
                return await ctx.send(embed=self.bot.embed(ctx, description=str(e)))

            if args.cash:
                flag = 'cash'
            if args.vault:
                flag = 'vault'
            if args.level:
                flag = 'xp'
        query = queries[flag]['query']
        line_type = queries[flag]['line']

        async with self.bot.pool.acquire() as conn:
            count = await conn.fetchval(queries['count'])

            max_pages = math.ceil(count / 10)
            page = min(page, max_pages)

            data = await conn.fetch(query, ctx.guild.id, (page * 10) - 10)

        lines = []
        for num, user in enumerate(data, start=1):
            kwargs = {
                'num': num,
                'name': discord.utils.escape_markdown(str(await self.bot.try_user(user['user_id']))),
                'total_xp': None,
                'level': None,
                'total': None
            }
            if flag == 'xp':
                kwargs['level'] = user['level']
                kwargs['total_xp'] = user['xp'] - 1000
                for num in range(user['level'] + 1):
                    kwargs['total_xp'] += num * 1000
            if flag in ('cash', 'vault', 'total'):
                kwargs['total'] = user['total']
            lines.append(line_type.format_map(kwargs))
        lines.append(f"\nPage {page}/{max_pages}")

        embed = self.bot.embed(ctx, title=f"{ctx.guild.name} Leaderboard", description="\n".join(lines))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Economy(bot))
