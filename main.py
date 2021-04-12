import os
from utils import Mao
import discord

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

if __name__ == "__main__":
    bot.run(bot.settings['core']['token'])
