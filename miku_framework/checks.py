from discord import Interaction, app_commands

from .bot import Bot
from .errors import NotOwnerError


@app_commands.check
async def is_owner(interaction: Interaction):
    assert isinstance(interaction.client, Bot)

    if await interaction.client.is_owner(interaction.user):
        return True

    raise NotOwnerError()
