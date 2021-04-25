import asyncio

import discord
from discord.ext import commands
from tabulate import tabulate

import core
from utils import CustomContext, Mao

DEFAULT_MESSAGE = 'Welcome ${member.name} to ${server}! You are member ${server.member_count}.'


class BoolConverter(commands.Converter):
    async def convert(self, ctx, argument: str) -> bool:
        lowered = argument.lower()
        if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
            return True
        elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
            return False
        return 'unknown'


class Welcoming(commands.Cog):
    def __init__(self, bot: Mao):
        self.bot: Mao = bot
        self.welcome = self.bot.pool.welcome

    @staticmethod
    def env(member: discord.Member, guild: discord.Guild, what_to_get: str = 'values'):
        env = {
            'member': {
                'value': str(member),
                'description': 'The member\'s name + discriminator'
            },
            'member.name': {
                'value': member.name,
                'description': 'The member\'s name'
            },
            'member.discriminator': {
                'value': member.discriminator,
                'description': 'The member\'s discriminator'
            },
            'member.mention': {
                'value': member.mention,
                'description': 'Mentions the member.'
            },
            'server': {
                'value': str(guild),
                'description': 'The server\'s name'
            },
            'server.member_count': {
                'value': sum(not user.bot for user in guild.members),
                'description': 'The number of members in the server.'
            },
            'server.bot_count': {
                'value': sum(user.bot for user in guild.members),
                'description': 'The number of bots in the server'
            },
            'server.total_count': {
                'value': guild.member_count,
                'description': 'The total number of members + bots in the server.'
            },
            'server.created_at': {
                'value': guild.created_at.strftime('%A, %B %d, %Y'),
                'description': 'The time when the server was created'
            },
            'server.owner': {
                'value': str(guild.owner),
                'description': 'The server owner\'s name + discriminator'
            },
            'server.owner.name': {
                'value': guild.owner.name,
                'description': 'The server owner\'s name'
            },
            'server.roles': {
                'value': len(guild.roles),
                'description': 'The amount of roles in the server'
            },
            'server.boosts': {
                'value': len(guild.roles),
                'description': 'The number of boosts in the server'
            },
        }
        if what_to_get == 'values':
            return {name: data['value'] for name, data in env.items()}
        if what_to_get == 'all':
            return env
        if what_to_get == 'description':
            return {name: data['description'] for name, data in env.items()}

    @core.command()
    @commands.guild_only()
    async def welcome(self, ctx: CustomContext, member: discord.Member = None):
        member: discord.Member = member or ctx.author
        env = self.env(member=member, guild=ctx.guild)
        message = 'Hey ${member.mention}! Welcome to ${server}! We have ${server.member_count} members and ${server.bot_count} bots. We have ${server.roles} roles.'
        for var, value in env.items():
            message = message.replace('${' + var + '}', str(value))
        await ctx.send(message)

    @core.command()
    @commands.guild_only()
    async def values(self, ctx: CustomContext):
        env = self.env(member=ctx.author, guild=ctx.guild, what_to_get='all')
        data = [{var: data} for var, data in env.items()]
        items = []
        for i in data:
            for j in i:
                l1 = [j]
                for k in i[j]:
                    l1.append(i[j][k])
                items.append(l1)
        table = tabulate(
            items,
            headers=['variable', 'value', 'description']
        )
        link = await ctx.mystbin(table)
        embed = self.bot.embed(ctx,
                               description=f"Here's a list of valid variables you can use when setting up your welcome message. "
                                           f"It is too large to show on Discord so I pasted it to a nifty website.\n\n{link}")
        await ctx.send(embed=embed)

    @core.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setup(self, ctx: CustomContext):
        if ctx.guild.id in self.bot.cache['guilds']['welcoming']:
            answer, message = await ctx.confirm(
                text='It looks like someone already ran through the setup process in this server, '
                     'are you sure you want to continue? This will erase all existing data.')
            if not answer:
                return await message.edit(content='Cancelled the setup process.')
            else:
                await message.delete()
                await self.bot.pool.execute("DELETE FROM welcome WHERE guild_id = $1", ctx.guild.id)
        data = {
            'guild_id': ctx.guild.id,
            'embed': None,
            'dm': None,
            'channel_id': None,
            'message': None
        }

        embed = self.bot.embed(ctx,
                               description=(
                                   'This will guide you through the process for setting up welcome messages on your server.\n'
                                   'Type `start` to begin the setup process, or type `cancel` to abandon the process.\n'
                                   'Failing to answer any question within 60 seconds will cancel the process.'
                               ))
        timeout = 60
        embed.set_footer(text='You have 60 seconds to answer each question.')
        message = await ctx.send(embed=embed)

        async def cancel():
            await message.delete()
            embed.description = 'Cancelled the setup process.'
            return await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            start = await self.bot.wait_for('message', timeout=timeout, check=check)
            if start.content.lower() == 'cancel':
                return await cancel()
            if start.content.lower() != 'start':
                return await cancel()

            embed.description = f'Please type the message you would like to send when a member joins.\n' \
                                f'Example: ```{DEFAULT_MESSAGE}```\nYou can use the `values` command to view a full list of valid variables.'
            await message.edit(embed=embed)
            set_message_message = await self.bot.wait_for('message', timeout=timeout, check=check)
            if start.content.lower() == 'cancel':
                return await cancel()
            data['message'] = set_message_message.content

            embed.description = 'Would you like to send this message in an embed? (yes/no)'
            await message.edit(embed=embed)
            embed_message = await self.bot.wait_for('message', timeout=timeout, check=check)
            if start.content.lower() == 'cancel':
                return await cancel()
            converted = await BoolConverter().convert(ctx, embed_message.content)
            if converted == 'unknown':
                await message.delete()
                return await ctx.send('I was unable to discern a yes/no from your response.')
            data['embed'] = True if converted else False

            embed.description = 'Would you like to send this message to the user directly?'
            await message.edit(embed=embed)
            dm_message = await self.bot.wait_for('message', timeout=timeout, check=check)
            if start.content.lower() == 'cancel':
                return await cancel()
            converted = await BoolConverter().convert(ctx, dm_message.content)
            if converted == 'unknown':
                await message.delete()
                return await ctx.send('I was unable to discern a yes/no from your response.')
            data['dm'] = True if converted else False

            if not data['dm']:
                embed.description = 'Since you don\'t want to send the message to the user directly, please send the channel you would like to send the message in.'
                await message.edit(embed=embed)
                channel_message = await self.bot.wait_for('message', timeout=timeout, check=check)
                if start.content.lower() == 'cancel':
                    return await cancel()
                try:
                    channel: discord.TextChannel = await commands.TextChannelConverter().convert(ctx, channel_message.content)
                except commands.ChannelNotFound:
                    await message.delete()
                    return await ctx.send('I was unable to discern a channel from your response.')
                data['channel_id'] = channel.id

        except asyncio.TimeoutError:
            await message.delete()
            await ctx.send(f'You failed to answer one of the questions within 60 seconds, so I cancelled the process.')
        else:
            msg = (
                'Setup process has been completed. Here are the values you provided:\n'
                f"`Message:` {data['message']}\n"
                f"`Send in an embed:` `{'yes' if data['embed'] else 'no'}`\n"
                f"`Send in a direct message:` `{'yes' if data['dm'] else 'no'}`\n"
                f"`Send in an embed:` `{'yes' if data['embed'] else 'no'}`\n"
            )
            if data['channel_id']:
                msg += f"`Channel ID to send to:` `{data['channel_id']}`"
            await ctx.send(msg)
            await self.welcome.first_insert(data)


def setup(bot: Mao):
    bot.add_cog(Welcoming(bot))
