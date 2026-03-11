import logging
import shutil
import tomllib
from pathlib import Path

import discord
from discord.ext import commands

here = Path(__file__).parent
_logger = logging.getLogger("framework.bot")


class Bot(commands.Bot):
    def __init__(self) -> None:

        self.data_dir = Path("./data")
        self.data_dir.mkdir(exist_ok=True)

        self.modules_dir = self.data_dir / "modules"
        self.modules_dir.mkdir(exist_ok=True)

        self.settings_file = self.data_dir / "settings.toml"

        super().__init__(
            command_prefix=[],
            intents=discord.Intents.all(),
        )

    async def start(self, *_, **__) -> None:
        discord.utils.setup_logging()

        self.load_settings()

        self.command_prefix = commands.when_mentioned_or(*self.settings["command_prefixes"])

        await super().start(token=self.settings["token"])

    def run(self, *_, **kwargs) -> None:
        super().run(token="", log_handler=None, **kwargs)

    async def setup_hook(self) -> None:
        await self.load_modules()

    def load_settings(self) -> None:
        if not self.settings_file.exists():
            shutil.copy(here / "default_settings.toml", self.settings_file)
        with open(self.settings_file) as f:
            self.settings = tomllib.loads(f.read())

    async def load_modules(self, modules_to_load: list[str] | None = None) -> None:
        _logger.info("All i wanted to do, was follow you. (Loading modules)")

        if not modules_to_load:
            modules_to_load = []

        # unload currently loaded modules
        for loaded_module in list(self.extensions.keys()):
            await self.unload_extension(loaded_module)

        # load modules
        for module in self.modules_dir.glob("*/__init__.py"):
            import_path = module.relative_to(".").as_posix().replace("/", ".").replace(".py", "")

            await self.load_extension(import_path)

        _logger.info(
            f"Loaded {len(self.extensions)} module(s).",
        )
