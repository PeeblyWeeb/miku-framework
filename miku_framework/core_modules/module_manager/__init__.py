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


async def setup(bot: Bot):
    await bot.add_cog(ModuleManager(bot))
