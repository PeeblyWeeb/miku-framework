import logging

from discord.ext import commands


class Module(commands.Cog):
    def __init__(self):
        self.logger = logging.getLogger(f"[Module] {self.__class__.__name__}")
