import discord
from discord.ext import commands
import asyncio
import toml
import logging

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Mao(commands.Bot):
    def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      
      #  core variables
      with open("config.toml") as f:
          self.settings = toml.loads(f.read())
      self.embed_color = "TBD"
      
      #   asyncio things
      self.loop = asyncio.get_event_loop()
      self.db = self.loop.run_until_complete(asyncpg.create_pool(dsn=self.settings['tokens']['dsn']))
      self.loop.create_task(self.__prep())
      
      
    async def __prep(self):
        self.session = aiohttp.ClientSession(loop=self.loop)
        with open("schema.sql") as f:
            await self.db.execute(f.read())
          
    async def on_ready(self):
        logging.info("Connected to Discord.")
        
    def run(token: str):
        for file in os.listdir("exts"):
            if not file.startswith("_"):
                self.load_extension(f'exts.{file[:-3]}')
        self.load_extension("jishaku")
        logging.info("Loaded extensions.)
        super().run(token=token)
        
    async def close(self):
        await self.session.close()
        await self.db.close()
        await super().close()
                     
    def embed(self, ctx, **kwargs):
        color = kwargs.pop("color", self.embed_color)
        embed = discord.Embed(**kwargs, color=color)
        embed.timestamp = ctx.message.created_at
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        return embed
          
      
      
      
