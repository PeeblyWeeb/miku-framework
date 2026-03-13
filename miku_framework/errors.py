from discord import app_commands


class NotOwnerError(app_commands.AppCommandError):
    """Thrown when a non-owner user attempts to execute an owner only application command."""

    pass
