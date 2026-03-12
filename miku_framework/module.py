import logging

from discord.ext import commands

from miku_framework.bot import Bot


class Module(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"[Module] {self.__class__.__name__}")

        if self.bot.launch_args.dev:
            self.logger.setLevel(logging.DEBUG)

    def get_sublogger(self, name):
        logger = logging.getLogger(f"[Module] {self.__class__.__name__}.{name}")
        if self.bot.launch_args.dev:
            logger.setLevel(logging.DEBUG)

        return logger
