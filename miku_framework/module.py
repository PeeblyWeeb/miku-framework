import logging

from discord.ext import commands

from miku_framework.bot import Bot


class Module(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"[Module] {self.__class__.__name__}")
