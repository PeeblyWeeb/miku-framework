import asyncio
from argparse import ArgumentParser, Namespace
from typing import cast

from alembic import command

from miku_framework.bot import Bot
from miku_framework.module import Module


async def load_module(name: str) -> Module:
    bot = Bot(
        launch_args=Namespace(
            dev=False,
            debug=False,
        ),
    )
    await bot.setup_hook()

    module = bot.cogs.get(name)
    if not module:
        raise ModuleNotFoundError(f"No module named {name} could be found.")

    return cast("Module", module)


async def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    revision = subparsers.add_parser("revision")
    revision.add_argument("module")
    revision.add_argument("message")

    upgrade = subparsers.add_parser("upgrade")
    upgrade.add_argument("module")
    upgrade.add_argument("revision", nargs="?", default="head")

    args = parser.parse_args()

    module = await load_module(args.module)

    if not module.db_base:
        raise RuntimeError(f"Module {args.module} never initializes a database")

    if args.command == "revision":
        config = module.get_alembic_config(module.db_base)

        command.revision(
            config,
            message=args.message,
            autogenerate=True,
        )

    elif args.command == "upgrade":
        config = module.get_alembic_config(module.db_base)

        command.upgrade(
            config,
            args.revision,
        )


if __name__ == "__main__":
    asyncio.run(main())
