import logging
from collections.abc import Callable, Coroutine
from typing import Any, Literal, final

from discord import Interaction
from discord.app_commands import AppCommandError
from discord.ext import commands

from miku_framework.bot import Bot


class Module(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.logger = logging.getLogger(f"[Module] {self.__class__.__name__}")

        storage_path = self.bot.storage_dir / self.__class__.__name__
        storage_path.mkdir(exist_ok=True)
        self.storage_path = storage_path.resolve()

        if self.bot.launch_args.dev:
            self.logger.setLevel(logging.DEBUG)

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
        """Overriding this method is discouraged in miku framework modules, override `on_module_error` instead."""
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
        """Overriding this method is discouraged in miku framework modules, override `on_module_error` instead."""
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
