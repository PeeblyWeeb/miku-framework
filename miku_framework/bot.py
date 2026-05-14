import asyncio
import importlib
import json
import logging
import os
import socket
import sys
from argparse import Namespace
from asyncio import subprocess
from pathlib import Path

import discord
import sentry_sdk
import uvicorn
from discord.app_commands import AppCommandError
from discord.ext import commands
from fastapi import FastAPI
from watchdog.observers import Observer

from miku_framework.config import FrameworkConfig
from miku_framework.dev.module_watchdog import AsyncModuleWatchdog
from miku_framework.util import generate_generic_error_message

here = Path(__file__).parent
_logger = logging.getLogger("framework.bot")


class CommandTree(discord.app_commands.CommandTree):
    async def on_error(self, interaction: discord.Interaction[discord.Client], error: AppCommandError) -> None:
        if interaction.extras.get("__mikuframework_already_handled_error"):
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

        config_dir = self.data_dir / "config"
        config_dir.mkdir(exist_ok=True)
        self.config_dir = config_dir.resolve()

        self.config_file = (self.config_dir / "framework.json").resolve()

        if self.launch_args.dev:
            _logger.setLevel(logging.DEBUG)

        super().__init__(
            command_prefix=[],
            intents=discord.Intents.all(),
            tree_cls=CommandTree,
        )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if getattr(ctx, "__mikuframework_already_handled_error", False):
            return
        original_error = getattr(error, "original", error)

        _logger.exception(f"{original_error.__class__.__name__}: {original_error}", exc_info=original_error)
        message = generate_generic_error_message(original_error)
        await ctx.reply(message)

    async def start(self, *_, **__) -> None:
        self.load_settings()

        self.command_prefix = commands.when_mentioned_or(*self.config.command_prefixes)

        if not (token := os.getenv("DISCORD_TOKEN")):
            _logger.error("Missing DISCORD_TOKEN in environment, the application can not continue.")
            return
        await super().start(token=token)

    def run(self, *_, **kwargs) -> None:
        super().run(token="", log_handler=None, **kwargs)

    async def close(self) -> None:
        self.save_settings()

        return await super().close()

    def _setup_http(self):
        self.config.http_url = self.config.http_url.rstrip("/")

        self.web_api = FastAPI(
            debug=self.launch_args.dev,
            title="Miku Framework API",
        )
        self._http_server = uvicorn.Server(
            uvicorn.Config(
                app=self.web_api,
                host=self.config.http_host,
                port=self.config.http_port,
                log_config=None,
            ),
        )
        self._http_task = None

    async def developer_hotreload(self):
        # reset http server
        await self._http_server.shutdown()
        self._setup_http()

        await self.load_modules()

        self._http_task = asyncio.create_task(self._http_server.serve())

    async def setup_hook(self) -> None:
        if dsn := os.getenv("SENTRY_DSN"):
            environment = os.getenv("SENTRY_ENVIRONMENT") or "development"

            _logger.info(f"Initializing sentry with environment '{environment}'")
            sentry_sdk.init(
                dsn=dsn,
                server_name=socket.gethostname(),
                environment=environment,
                # Add data like request headers and IP for users,
                # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
                send_default_pii=True,
                # Enable sending logs to Sentry
                enable_logs=True,
                # Set traces_sample_rate to 1.0 to capture 100%
                # of transactions for tracing.
                traces_sample_rate=1.0,
            )
        else:
            _logger.warning("Missing SENTRY_DSN in environment, sentry will not be initialized.")

        self._setup_http()

        await self.load_modules()

        self._http_task = asyncio.create_task(self._http_server.serve())

        if self.launch_args.dev:

            async def watchdog_callback():
                _logger.debug("\n\n=== Detected module changes, reloading.. ===\n\n")

                await self.developer_hotreload()

            self.module_observer = Observer()
            self.module_observer.schedule(
                AsyncModuleWatchdog(watchdog_callback, asyncio.get_event_loop()),
                str(self.modules_dir),
                recursive=True,
            )
            self.module_observer.start()

            _logger.debug(f"Watching for module changes in '{self.modules_dir}'")

    def load_settings(self) -> None:
        self.config_file.touch(exist_ok=True)
        with open(self.config_file) as f:
            config = json.loads(f.read() or "{}")
        self.config: FrameworkConfig = FrameworkConfig(**config)

        _logger.info(f"Loaded framework settings from '{self.config_file}'")

    def save_settings(self) -> None:
        with open(self.config_file, "w") as f:
            f.write(json.dumps(self.config.model_dump(), indent=4))
        _logger.info(f"Saved framework settings to '{self.config_file}'")

    async def load_module_from_path(self, path: Path):
        requirements_file = path / "requirements.txt"
        entrypoint = (path / "__init__.py").relative_to(Path.cwd()).as_posix().replace("/", ".").replace(".py", "")

        if requirements_file.exists():
            _logger.info(f"Ensuring dependencies for module '{path.name}'")

            proc = await subprocess.create_subprocess_exec(
                "uv",
                "pip",
                "install",
                "-r",
                requirements_file.absolute(),
                stderr=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                _logger.error(f"Failed to install dependencies for module '{path.name}':\n{stderr.decode()}")
                return

        await self.load_extension(entrypoint)

    async def load_modules(self) -> None:
        _logger.info("All i wanted to do, was follow you. (Loading modules)")

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
            await self.load_module_from_path(module.parent)

        # load modules
        for module in self.modules_dir.glob("*/__init__.py"):
            await self.load_module_from_path(module.parent)

        _logger.info(
            f"Loaded {len(self.extensions)} module(s).",
        )
