import asyncio

from discord.ext import commands


class CustomContext(commands.Context):
    def escape(self, text: str):
        mark = [
            '`',
            '_',
            '*'
        ]
        for item in mark:
            text = text.replace(item, f'\u200b{item}')
        return text

    # https://github.com/InterStella0/stella_bot/blob/master/utils/useful.py#L199-L205
    def plural(self, text, size):
        logic = size == 1
        target = (("(s)", ("s", "")), ("(is/are)", ("are", "is")))
        for x, y in target:
            text = text.replace(x, y[logic])
        return text

    async def mystbin(self, data):
        data = bytes(data, 'utf-8')
        async with self.bot.session.post('https://mystb.in/documents', data=data) as r:
            res = await r.json()
            key = res["key"]
            return f"https://mystb.in/{key}"

    async def confirm(self, text: str = 'Are you sure you want to do this?'):
        message = await self.send(text)
        await message.add_reaction('✅')
        await message.add_reaction('❌')

        def terms(p):
            return p.member == self.author and str(p.emoji) in ('✅', '❌')

        try:
            payload = await self.bot.wait_for('raw_reaction_add', timeout=15, check=terms)
        except asyncio.TimeoutError:
            return False, message
        else:
            if str(payload.emoji) == '✅':
                return True, message
            if str(payload.emoji) == '❌':
                return False, message
