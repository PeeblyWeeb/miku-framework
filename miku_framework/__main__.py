import argparse

from .bot import Bot

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
    bot = Bot(args)

    bot.run()
