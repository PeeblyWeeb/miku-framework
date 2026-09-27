from __future__ import annotations

import inspect
import json
import logging
import subprocess
import tomllib
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, final

import aiofiles
from alembic import command
from alembic.config import Config
from discord import Interaction
from discord.app_commands import AppCommandError
from discord.ext import commands
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

if TYPE_CHECKING:
    from miku_framework.bot import Bot

here = Path(__file__).parent
_logger = logging.getLogger("framework.module")


class ModuleDescription:
    def __init__(self, pyproject_path: Path) -> None:
        with open(pyproject_path) as f:
            pyproject = tomllib.loads(f.read())

            self.name = pyproject.get("project", {})["name"]
            self.dependencies = pyproject.get("project", {}).get("dependencies", [])

        self.import_path = pyproject_path.parent.relative_to(Path.cwd()).as_posix().replace("/", ".")

    def install_dependencies(self):
        if self.dependencies:
            _logger.info(f"Installing required dependencies for '{self.name}': {self.dependencies}")
            subprocess.run(  # noqa: S603
                ["uv", "pip", "install", *self.dependencies],  # noqa: S607
                check=True,
            )


class Module(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"[Module] {self.__class__.__name__}")

        module_path = Path(inspect.getfile(type(self))).parent
        # no .mkdir() here, because it should already exist.
        self.module_path = module_path.resolve()

        storage_path = self.bot.storage_dir / self.__class__.__name__
        storage_path.mkdir(exist_ok=True)
        self.storage_path = storage_path.resolve()

        config_file = self.bot.config_dir / f"{self.__class__.__name__}.json"
        self.config_file = config_file.resolve()
        self._config: BaseModel | None = None

        migrations_path = self.module_path / "migrations"
        # no .mkdir() here, this should be created by the module developer.
        self.migrations_path = migrations_path.resolve()

        self.db_base: type[DeclarativeBase] | None = None
        self._db_file = self.storage_path / "db.sqlite"
        self._db_engine = create_engine(
            url=f"sqlite+pysqlite:///{self._db_file.as_posix()}",
        )

        self.http_router = APIRouter(
            prefix=f"/modules/{self.__class__.__name__}",
            tags=["Module Endpoints", f"{self.__class__.__name__}"],
        )

        if self.bot.launch_args.dev:
            self.logger.setLevel(logging.DEBUG)

    def get_alembic_config(self, base: type[DeclarativeBase]) -> Config:
        config = Config()

        config.set_main_option("script_location", (here / "alembic").as_posix())
        config.set_main_option("version_locations", self.migrations_path.as_posix())
        config.attributes["migration_path"] = self.migrations_path
        config.attributes["target_metadata"] = base.metadata
        config.attributes["engine"] = self._db_engine

        return config

    def _run_database_migrations(self, base: type[DeclarativeBase]):
        config = self.get_alembic_config(base)
        command.upgrade(config, "head")

    def init_db(self, base: type[DeclarativeBase]):
        """Initializes (or loads) an sqlite database for this module using sqlalchemy.

        :param base:
            If initializing a database for the first time, used for generating and emitting DDL.

        Returns:
            An sqlalchemy sessionmaker object.

        """
        self.db_base = base
        if not self._db_file.exists():
            self.logger.info("Does not have an existing database file, creating it now..")

        self._run_database_migrations(base)

        return sessionmaker(self._db_engine)

    @property
    def http_endpoint(self):
        """Returns the corresponding HTTP endpoint for this miku module.

        Example:
            https://example.com/modules/MyTestModule

        """
        return f"{self.bot.config.http_url}/modules/{self.__class__.__name__}"

    def init_config[T: BaseModel](self, config_model: type[T]) -> T:
        if not self.config_file.exists():
            self.config_file.touch()

            with open(self.config_file, "w") as f:
                json.dump(config_model(**{}).model_dump(), f, indent=4)

        self.logger.info(f"Loaded module config from '{self.config_file}'")

        with open(self.config_file) as f:
            module_config = json.loads(f.read() or "{}")

        self._config = config_model(**module_config)
        return self._config

    async def cog_load(self) -> None:
        self.bot.web_api.include_router(self.http_router)

        return await super().cog_load()

    async def cog_unload(self) -> None:
        if self._config:
            async with aiofiles.open(self.config_file, "w") as f:
                await f.write(json.dumps(self._config.model_dump(), indent=4))

            self.logger.info(f"Saved module config to '{self.config_file}'")
        return await super().cog_unload()

    async def on_module_command_error(
        self,
        error: Exception,  # noqa: ARG002
        respond: Callable[[str], Coroutine[Any, Any, Literal[True]]],  # noqa: ARG002
    ) -> bool:
        """Executed when a command error is dispatched by discord.py.

        :param Exception error:
            The original unwrapped error.
        :param Callable[[str], Coroutine[Any, Any, Literal[True]]]) respond:
            A helper method allowing you to send a message in response to the error.

        Returns:
            (bool): Whether or not the error was successfully caught by the implementing module.

            This allows the miku framework to automatically handle errors that your handler did not catch.

        """
        return False

    @final
    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Overriding this method is discouraged in miku modules, override `on_module_command_error` instead."""
        original_error = getattr(error, "original", error)

        async def respond(message: str) -> Literal[True]:
            await ctx.reply(content=message)

            return True

        if await self.on_module_command_error(original_error, respond):
            setattr(ctx, "__mikuframework_already_handled_error", True)

            self.logger.info(f"{getattr(ctx, '__mikuframework_already_handled_error', False)}")

        await super().cog_command_error(ctx, error)

    @final
    async def cog_app_command_error(self, interaction: Interaction, error: AppCommandError) -> None:
        """Overriding this method is discouraged in miku modules, override `on_module_command_error` instead."""
        original_error = getattr(error, "original", error)

        async def respond(message: str) -> Literal[True]:
            _ = (
                interaction.edit_original_response
                if interaction.response.is_done()
                else interaction.response.send_message
            )

            await _(content=message)

            return True

        if await self.on_module_command_error(original_error, respond):
            interaction.extras["__mikuframework_already_handled_error"] = True

        await super().cog_app_command_error(interaction, error)

    def get_sublogger(self, name):
        logger = logging.getLogger(f"[Module] {self.__class__.__name__}.{name}")
        if self.bot.launch_args.dev:
            logger.setLevel(logging.DEBUG)

        return logger
