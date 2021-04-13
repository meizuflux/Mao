from discord.ext import commands


def init(self, **attrs):
    self.examples = attrs.pop("examples", None)
    self.user_perms = attrs.pop("user_perms", ("None",))
    self.bot_perms = attrs.pop("bot_perms", ('Send Messages',))


class Command(commands.Command):
    def __init__(self, func, name, **attrs):
        super().__init__(func, name=name, **attrs)
        init(self, **attrs)


class Group(Command, commands.Group):
    def __init__(self, func, name, **attrs):
        super().__init__(func, name=name, **attrs)
        init(self, **attrs)


def command(name=None, cls=None, **attrs):
    if not cls:
        cls = Command

    def decorator(func):
        if isinstance(func, (Command, commands.Command)):
            raise TypeError('Callback is already a command.')
        return cls(func, name=name, **attrs)

    return decorator


def group(name=None, **attrs):
    attrs.setdefault('cls', Group)
    return command(name=name, **attrs)
