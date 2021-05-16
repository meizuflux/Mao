import os
import time
from datetime import datetime

import discord
from discord.ext import commands

from core import Command, CustomCooldownBucket
from utils import Mao

intents = discord.Intents.default()
intents.members = True

intents.integrations = False
intents.webhooks = False
intents.invites = False
intents.voice_states = False
intents.typing = False

flags = discord.MemberCacheFlags.from_intents(intents)

bot = Mao(
    command_prefix="mao ",
    case_insensitive=True,
    intents=intents,
    member_cache_flags=flags,
    max_messages=750,
    owner_ids={809587169520910346}
)

os.environ['JISHAKU_NO_UNDERSCORE'] = "True"
os.environ['JISHAKU_NO_DM_TRACEBACK'] = "True"
os.environ['JISHAKU_HIDE'] = "True"


@bot.check_once
async def ratelimit(ctx):
    if isinstance(ctx.command, Command) and ctx.command.cd:
        _type = 'guild' if ctx.command.cd.guild else 'user'
        try:
            if _type == 'guild':
                if not ctx.guild:
                    raise commands.NoPrivateMessage()
                expires = bot.pool.cache['cooldowns'][_type][ctx.guild.id][ctx.author.id][ctx.command.qualified_name]

            elif _type == 'user':
                expires = bot.pool.cache['cooldowns'][_type][ctx.author.id][ctx.command.qualified_name]

            if expires > time.time():
                raise commands.CommandOnCooldown(
                    CustomCooldownBucket(rate=1, per=ctx.command.cd.rate, type=_type),
                    (datetime.utcfromtimestamp(expires) - datetime.utcnow()).seconds
                )
        except KeyError:
            pass
    return True

if __name__ == "__main__":
    bot.run(bot.settings['core']['token'])
