from asyncpg import UniqueViolationError
from asyncpg.transaction import Transaction
from discord.ext import commands

import core
from utils import CustomContext, Mao


class TagName(commands.clean_content):
    async def convert(self, ctx, argument):
        converted = await super().convert(ctx, argument)
        lower = converted.lower().strip()

        if not lower:
            raise commands.BadArgument('where tag')

        if len(lower) > 256:
            raise commands.BadArgument('too long')

        word = lower.partition(' ')

        # get tag command.
        root = ctx.bot.get_command('tag')
        if word[0] in root.all_commands:
            raise commands.BadArgument("this is a no no word")

        return lower


class Tags(commands.Cog):
    def __init__(self, bot: Mao):
        self.bot: Mao = bot
        self.pool = self.bot.pool

    async def create_tag(self, ctx: CustomContext, name: str, content: str):
        # sourcery skip: move-assign
        query = """
                WITH tag_create AS (
                    INSERT INTO
                        tags (guild_id, owner_id, name, content)
                    VALUES
                        ($1, $2, $3, $4)
                    RETURNING
                        tag_id
                )
                INSERT INTO
                    tag_search (tag_id, guild_id, owner_id, name)
                VALUES
                    ((SELECT tag_id FROM tag_create), $1, $2, $3)
                """
        async with self.pool.acquire() as conn:
            transaction: Transaction = conn.transaction()
            await transaction.start()
            try:
                await conn.execute(query, ctx.guild.id, ctx.author.id, name, content)
            except UniqueViolationError as e:
                await transaction.rollback()
                await ctx.send("bro that tag already exists lol")
            except Exception as error:
                await transaction.rollback()
                await ctx.send("An error occurred whilst creating this tag: ```py\n{0.__class__.__name__}: {0}```".format(error))
            else:
                await transaction.commit()
                await ctx.send(f"yep created tag {name}")

    async def get_tag(self, ctx, name):  # sourcery skip: move-assign
        query = """
                SELECT 
                    tags.name, tags.content
                FROM
                    tag_search
                INNER JOIN
                    tags ON
                        tags.tag_id = tag_search.tag_id
                WHERE
                    tag_search.guild_id = $1 AND LOWER(tag_search.name) = $2
                """
        async with self.pool.acquire() as conn:
            tag = await conn.fetchrow(query, ctx.guild.id, name.lower())
            if not tag:
                raise commands.BadArgument("bruh you gotta create dis")
            return dict(tag)

    @core.group(cd=core.Cooldown(2, False), invoke_without_command=True)
    async def tag(self, ctx: CustomContext, *, tag_name: TagName()):
        tag = await self.get_tag(ctx, tag_name)
        await ctx.send(tag['content'])

        query = "UPDATE tags SET uses = uses + 1 WHERE name = $2 AND guild_id = $1"
        await self.pool.execute(query, ctx.guild.id, tag['name'])

    @tag.command()
    async def create(self, ctx: CustomContext, name, *, content: commands.clean_content):
        await self.create_tag(ctx, name, str(content))


def setup(bot: Mao):
    bot.add_cog(Tags(bot))
