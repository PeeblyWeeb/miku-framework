from discord import Interaction, app_commands
from discord.ext import commands

from miku_framework import Bot, Module


class ModuleManager(Module):
    def __init__(self, bot: Bot):
        super().__init__(bot=bot)

    @commands.is_owner()
    @commands.command(
        name="sync",
        description="Synchronize application commands to discord.",
    )
    async def sync(self, ctx: commands.Context):
        assert self.bot.user

        await ctx.message.add_reaction("⏳")

        await self.bot.tree.sync()

        await ctx.message.add_reaction("✅")
        await ctx.message.remove_reaction("⏳", self.bot.user)  # we do this after to avoid jittering the chat around

    @commands.is_owner()
    @commands.command(
        name="reload",
        description="Unload all loaded modules and then reload from module folder.",
    )
    async def reload(self, ctx: commands.Context):
        assert self.bot.user
        await self.bot.load_modules()

        await ctx.message.add_reaction("✅")

    async def guild_enabled_module_autocomplete(self, interaction: Interaction[Bot], query: str):

        enabled_module_names = [module_type.__class__.__name__ for module_type in interaction.client.cogs.values()]
        guild_disabled_module_names = (
            interaction.client.config.per_guild_disabled_modules.get(str(interaction.guild_id)) or []
        )
        guild_enabled_module_names = [
            module_name for module_name in enabled_module_names if module_name not in guild_disabled_module_names
        ]

        filtered_module_names = filter(lambda name: name.startswith(query), guild_enabled_module_names)
        return [app_commands.Choice(name=module_name, value=module_name) for module_name in filtered_module_names]

    async def guild_disabled_module_autocomplete(self, interaction: Interaction[Bot], query: str):
        disabled_module_names = (
            interaction.client.config.per_guild_disabled_modules.get(str(interaction.guild_id)) or []
        )
        filtered_module_names = filter(lambda name: name.startswith(query), disabled_module_names)

        return [app_commands.Choice(name=module_name, value=module_name) for module_name in filtered_module_names]

    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.autocomplete(module_name=guild_enabled_module_autocomplete)
    @app_commands.guild_only
    @app_commands.command(
        description="Disable a specific module from being used in specifically your server.",
    )
    async def guild_disable_module(self, interaction: Interaction[Bot], module_name: str):
        if not interaction.guild:
            return

        global_module_names = [module_type.__class__.__name__ for module_type in interaction.client.cogs.values()]
        if module_name not in global_module_names:
            await interaction.response.send_message("That module doesn't exist.")
            return
        if module_name == self.__class__.__name__:
            await interaction.response.send_message("You probably don't want to disable that one.")
            return

        guild_disabled_module_names = set(
            interaction.client.config.per_guild_disabled_modules.get(str(interaction.guild_id)) or [],
        )
        guild_disabled_module_names.add(module_name)

        interaction.client.config.per_guild_disabled_modules[str(interaction.guild_id)] = list(
            guild_disabled_module_names,
        )

        await interaction.response.send_message(f"**{module_name}** is now disabled in **{interaction.guild.name}**")

    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.autocomplete(module_name=guild_disabled_module_autocomplete)
    @app_commands.guild_only
    @app_commands.command(
        description="Enable a previously disabled module for use in your server.",
    )
    async def guild_enable_module(self, interaction: Interaction[Bot], module_name: str):
        if not interaction.guild:
            return

        global_module_names = [module_type.__class__.__name__ for module_type in interaction.client.cogs.values()]
        if module_name not in global_module_names:
            await interaction.response.send_message("That module doesn't exist.")
            return

        guild_disabled_module_names = set(
            interaction.client.config.per_guild_disabled_modules.get(str(interaction.guild_id)) or [],
        )
        guild_disabled_module_names.remove(module_name)

        interaction.client.config.per_guild_disabled_modules[str(interaction.guild_id)] = list(
            guild_disabled_module_names,
        )

        await interaction.response.send_message(f"**{module_name}** is now enabled in **{interaction.guild.name}**")


async def setup(bot: Bot):
    await bot.add_cog(ModuleManager(bot))
