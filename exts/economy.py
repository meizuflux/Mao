import functools
import logging
import random
from dataclasses import dataclass

import discord
from asyncpg import UniqueViolationError
from discord.ext import commands, tasks

import core
from rank_card import Generator
from utils import CustomContext, Mao, get_user_stats

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

    def cog_unload(self):
        self.bulk_insert_task.stop()

    async def register_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.author.id not in self.bot.registered_users:
            return
        if message.guild.id in self.bot.non_leveling_guilds:
            return
        if random.randint(1, 3) == 2:
            return

        xp = random.randint(66, 114)
        if data := self._data_batch:
            for msg in data:
                if msg['g'] == message.guild.id and msg['u'] == message.author.id:
                    msg['xp'] += xp
                    return
        self._data_batch.append(
            {
                'g': message.guild.id,
                'u': message.author.id,
                'xp': xp
            }
        )

    async def bulk_insert(self):
        if not self._data_batch:
            return
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                query = (
                    """
                    UPDATE users SET xp = xp + $3
                    WHERE guild_id = $1 AND user_id = $2
                    """
                )
                await conn.executemany(
                    query,
                    tuple((msg['g'], msg['u'], msg['xp']) for msg in self._data_batch)
                )
        log.info(f"Inserted XP. Unique users/guilds: {len(self._data_batch)}")
        self._data_batch.clear()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.register_message(message)

    @tasks.loop(seconds=20)
    async def bulk_insert_task(self):
        await self.bulk_insert()

    @core.command(name="toggle-leveling", aliases=('toggleleveling',))
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

    @core.command()
    async def register(self, ctx: CustomContext):
        """Registers you into the user database.
        You can unregister with `{prefix}unregister`"""
        query = "INSERT INTO users (guild_id, user_id) VALUES ($1, $2);"
        try:
            await self.bot.pool.execute(query, ctx.guild.id, ctx.author.id)
        except UniqueViolationError:
            return await ctx.send("You are already registered!")
        await ctx.send("Registered you into the database.")

    @core.command(aliases=('bal', 'account'), examples=('@user', None), bot_perms=('Send Messages', 'Embed Links', 'Manage Server'))
    async def balance(self, ctx: CustomContext, user: discord.User = None):
        """View yours or someone else's balance."""
        user = user or ctx.author
        items = ('cash', 'vault', 'pet_name', 'xp', 'level')
        cash, vault, pet, xp, level = await get_user_stats(ctx, user_id=user.id, items=items)
        message = (
            f"💸 Cash → {cash}",
            f"💰 Vault → {vault}",
            f"<:doggo:820992892515778650> Pet → {pet.title()}",
            f"<:feyes:819694934209855488> XP → {xp} ({level * 1000 + xp} total)",
            f"🥗 Level → {level}"
        )
        embed = self.bot.embed(ctx, author=False, title=f"{user.name}'s balance", description="\n".join(message))
        embed.set_thumbnail(url=user.avatar_url)
        await ctx.send(embed=embed)

    @core.command(name='level-up', aliases=('lvlup', 'levelup'))
    async def level_up(self, ctx: CustomContext):
        xp, level = await get_user_stats(ctx, items=('xp', 'level'))

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

    @core.command(aliases=('xp', 'lvl', 'profile'))
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.user)
    async def level(self, ctx: CustomContext, user: discord.User = None):
        user = user or ctx.author
        xp, level = await get_user_stats(ctx, user_id=user.id, items=('xp', 'level'))
        kwargs = {
            'profile_image': ctx.author.avatar_url_as(format="png"),
            'level': level,
            'user_xp': xp,
            'next_xp': level * 1000,
            'user_name': str(ctx.author),
        }
        generator = functools.partial(Generator().generate_profile, **kwargs)
        image = await self.bot.loop.run_in_executor(None, generator)
        file = discord.File(fp=image, filename="image.png")
        await ctx.send(file=file)


def setup(bot):
    bot.add_cog(Economy(bot))
