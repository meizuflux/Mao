from discord.ext import commands

from utils import Mao


def setup(bot: Mao):
    bot.help_command = commands.MinimalHelpCommand()


def teardown(bot: Mao):
    bot.help_command = commands.MinimalHelpCommand
