import functools
import logging
import random
from dataclasses import dataclass

import discord
from asyncpg import UniqueViolationError
from discord.ext import commands, tasks

import core
from rank_card import Generator
from utils import CustomContext, Mao, messages, parse_number

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

    def cog_unload(self):
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
        self._data_batch.append(
            {
                'guild': message.guild.id,
                'user': message.author.id,
                'xp': random.randint(15, 56)
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
        enabled = await self.bot.pool.fetchval("SELECT leveling FROM guild_config WHERE guild_id = $1", ctx.guild.id)
        leveling, msg = not enabled, "Enabled" if not enabled else "Disabled"
        query = (
            """
            UPDATE guild_config SET leveling = $2
            WHERE guild_id = $1
            """
        )
        await self.bot.pool.execute(query, ctx.guild.id, leveling)
        await ctx.send(f"{msg} leveling on {ctx.guild.name}.")
        method = getattr(self.bot.non_leveling_guilds, "remove" if leveling else "add")
        method(ctx.guild.id)

    @core.command(
        aliases=('register-account',)
    )
    async def register(self, ctx: CustomContext):
        """Registers you into the user database.
        You can unregister with `{prefix}unregister`"""
        query = "INSERT INTO users (guild_id, user_id) VALUES ($1, $2);"
        try:
            await self.bot.pool.execute(query, ctx.guild.id, ctx.author.id)
        except UniqueViolationError:
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
        items = ('cash', 'vault', 'pet_name', 'xp', 'level')
        cash, vault, pet, xp, level = await self.bot.pool.fetch_user_stats(ctx, user_id=user.id, items=items)
        total_xp = xp
        for num in range(level + 1):
            total_xp += num * 1000
        message = (
            f"💸 **Cash** → {cash}",
            f"💰 **Vault** → {vault}",
            f"🐊 **Pet** → {pet.title()}",
            f"<:feyes:819694934209855488> **XP** → {xp} ({total_xp - 1000} total)",
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
        xp, level = await self.bot.pool.fetch_user_stats(ctx, items=('xp', 'level'))

        cost = level * 1000
        xp_needed = max((level * 1000) - xp, 0)

        if xp_needed != 0:
            return await ctx.send(f"You need {xp_needed} more XP in order to level up to level {level + 1}")

        query = (
            """
            UPDATE users SET level = level + 1, xp = $3
            WHERE guild_id = $1 AND user_id = $2
            """
        )
        await self.bot.pool.execute(query, ctx.guild.id, ctx.author.id, xp - cost)
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
        xp, level = await self.bot.pool.fetch_user_stats(ctx, user_id=user.id, items=('xp', 'level'))
        kwargs = {
            'profile_image': user.avatar_url_as(format="png"),
            'level': level,
            'user_xp': xp,
            'next_xp': level * 1000,
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
        await self.bot.pool.update_user(ctx, method='wallet', amount=amount)
        await ctx.send(embed=self.bot.embed(ctx, description=messages.work_message(amount)))

    @core.command(
        aliases=('wd', 'with'),
        examples=('half', '56%', '18', 'all')
    )
    async def withdraw(self, ctx: CustomContext, amount: str):
        "Withdraw money from your vault."
        async with self.bot.pool.acquire() as conn:
            vault = await self.bot.pool.fetch_user_stats(ctx, items=('vault',), con=conn)
            amount = parse_number(argument=amount, total=vault)
            await self.bot.pool.withdraw(ctx, amount=amount, con=conn, release=True)
        await ctx.send(embed=self.bot.embed(ctx, description=f"You withdraw **${amount}** from your vault."))

    @core.command(
        aliases=('dep',),
        examples=('half', '56%', '18', 'all')
    )
    async def deposit(self, ctx: CustomContext, amount: str):
        """Withdraw money from your vault."""
        async with self.bot.pool.acquire() as conn:
            cash = await self.bot.pool.fetch_user_stats(ctx, items=('cash',), con=conn)
            amount = parse_number(argument=amount, total=cash)
            await self.bot.pool.deposit(ctx, amount=amount, con=conn, release=True)
        await ctx.send(embed=self.bot.embed(ctx, description=f"You deposit **${amount}** to your vault."))

    @core.command(
        cd=core.Cooldown(86400, True)
    )
    async def daily(self, ctx: CustomContext):
        """Collect money daily."""
        async with self.bot.test_db.acquire() as conn:
            data = await self.bot.test_db.fetch_user_stats(ctx, items=('level',), conn=conn)
            boost = data['level'] * 0.05
            await self.bot.test_db.edit_user(ctx, 'cash', int(500 * (boost + 1)), conn=conn, release=True)
        await ctx.send(embed=self.bot.embed(ctx, desciption=f"You collect **$500**. Because you are level {data['level']}, you earn an extra **${int(500 * boost)}**"))


def setup(bot):
    bot.add_cog(Economy(bot))
