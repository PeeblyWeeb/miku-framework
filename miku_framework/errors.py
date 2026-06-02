from discord import app_commands


class NotOwnerError(app_commands.AppCommandError):
    """Thrown when a non-owner user attempts to execute an owner only application command."""


class GuildDisabledModuleError(app_commands.AppCommandError):
    """Thrown when a guild administrator has opted this guild out of the module this functionality is tied to."""
