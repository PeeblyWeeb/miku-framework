import asyncio
import importlib
import logging
import shutil
import sys
import tomllib
from argparse import Namespace
from pathlib import Path

import discord
from discord.app_commands import AppCommandError
from discord.ext import commands
from watchdog.observers import Observer

from miku_framework.dev.module_watchdog import AsyncModuleWatchdog
from miku_framework.util import generate_generic_error_message

here = Path(__file__).parent
_logger = logging.getLogger("framework.bot")


class CommandTree(discord.app_commands.CommandTree):
    async def on_error(self, interaction: discord.Interaction[discord.Client], error: AppCommandError) -> None:
        if interaction.extras.get("error_handled"):
            return

        _logger.exception(f"{error.__class__.__name__}: {error}", exc_info=error)
        message = generate_generic_error_message(error)
        if interaction.response.is_done():
            await interaction.edit_original_response(content=message)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class Bot(commands.AutoShardedBot):
    def __init__(self, launch_args: Namespace) -> None:
        self.launch_args = launch_args

        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        self.data_dir = data_dir.resolve()

        core_modules_dir = here / "core_modules"
        core_modules_dir.mkdir(exist_ok=True)
        self.core_modules_dir = core_modules_dir.resolve()

        modules_dir = self.data_dir / "modules"
        modules_dir.mkdir(exist_ok=True)
        self.modules_dir = modules_dir.resolve()

        storage_dir = self.data_dir / "storage"
        storage_dir.mkdir(exist_ok=True)
        self.storage_dir = storage_dir.resolve()

        self.settings_file = (self.data_dir / "settings.toml").resolve()

        if self.launch_args.dev:
            _logger.setLevel(logging.DEBUG)

        super().__init__(
            command_prefix=[],
            intents=discord.Intents.all(),
            tree_cls=CommandTree,
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

        if self.launch_args.dev:

            async def watchdog_callback():
                _logger.debug("\n\n=== Detected module changes, reloading.. ===\n\n")

                await self.load_modules()

            self.module_observer = Observer()
            self.module_observer.schedule(
                AsyncModuleWatchdog(watchdog_callback, asyncio.get_event_loop()),
                str(self.modules_dir),
                recursive=True,
            )
            self.module_observer.start()

            _logger.debug(f"Watching for module changes in '{self.modules_dir}'")

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
            _logger.debug(f"Unloading module: {loaded_module}")

            await self.unload_extension(loaded_module)
            for module_name in list(sys.modules):
                if module_name == loaded_module or module_name.startswith(loaded_module.removesuffix(".__init__")):
                    _logger.debug(f"⤷ Unloading import: {module_name}")

                    del sys.modules[module_name]

        importlib.invalidate_caches()

        # load core modules
        for module in self.core_modules_dir.glob("*/__init__.py"):
            import_path = module.relative_to(Path.cwd()).as_posix().replace("/", ".").replace(".py", "")

            await self.load_extension(import_path)

        # load modules
        for module in self.modules_dir.glob("*/__init__.py"):
            import_path = module.relative_to(Path.cwd()).as_posix().replace("/", ".").replace(".py", "")

            await self.load_extension(import_path)

        _logger.info(
            f"Loaded {len(self.extensions)} module(s).",
        )
