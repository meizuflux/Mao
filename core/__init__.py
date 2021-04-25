from dataclasses import dataclass

from discord.ext import commands


class Command(commands.Command):
    def __init__(self, func, name, **attrs):
        super().__init__(func, name=name, **attrs)
        self.examples: tuple = attrs.pop("examples", (None,))
        self.user_perms: tuple = attrs.pop("user_perms", ("None",))
        self.bot_perms: tuple = attrs.pop("bot_perms", ('Send Messages',))
        self.cd: Cooldown = attrs.pop("cd", None)


class Group(Command, commands.Group):
    def __init__(self, func, name, **attrs):
        super().__init__(func, name=name, **attrs)
        self.examples: tuple = attrs.pop("examples", (None,))
        self.user_perms: tuple = attrs.pop("user_perms", ("None",))
        self.bot_perms: tuple = attrs.pop("bot_perms", ('Send Messages',))
        self.cd: Cooldown = attrs.pop("cd", None)


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


@dataclass
class CustomCooldownBucket:
    rate: int
    per: int
    type: str

    def __str__(self):
        return str(self.type)


@dataclass
class Cooldown:
    rate: int
    guild: bool


def cooldown(rate, guild: bool):
    def decorator(func):
        if isinstance(func, Command):
            func.cooldown = Cooldown(rate=rate, guild=guild)
        return func

    return decorator
