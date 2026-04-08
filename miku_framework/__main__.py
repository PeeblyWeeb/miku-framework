import argparse
import logging

import discord
from dotenv import load_dotenv

from .bot import Bot

_logger = logging.getLogger("framework.init")

parser = argparse.ArgumentParser(
    prog="miku-framework",
)
parser.add_argument(
    "--dev",
    "--debug",
    action="store_true",
)

args = parser.parse_args()

if __name__ == "__main__":
    load_dotenv()
    discord.utils.setup_logging()

    _logger.info(f"Running with arguments: {args}")
    bot = Bot(args)
    bot.run()
