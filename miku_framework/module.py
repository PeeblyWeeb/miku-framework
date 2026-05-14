from __future__ import annotations

import json
import logging
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Literal, final

import aiofiles
from discord import Interaction
from discord.app_commands import AppCommandError
from discord.ext import commands
from fastapi import APIRouter
from pydantic import BaseModel

if TYPE_CHECKING:
    from miku_framework.bot import Bot


class Module(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"[Module] {self.__class__.__name__}")

        storage_path = self.bot.storage_dir / self.__class__.__name__
        storage_path.mkdir(exist_ok=True)
        self.storage_path = storage_path.resolve()

        config_file = self.bot.config_dir / f"{self.__class__.__name__}.json"
        self.config_file = config_file.resolve()

        self._config: BaseModel | None = None

        self.http_router = APIRouter(
            prefix=f"/modules/{self.__class__.__name__}",
            tags=["Module Endpoints", f"{self.__class__.__name__}"],
        )

        if self.bot.launch_args.dev:
            self.logger.setLevel(logging.DEBUG)

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
