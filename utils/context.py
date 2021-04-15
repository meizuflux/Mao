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
        return

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