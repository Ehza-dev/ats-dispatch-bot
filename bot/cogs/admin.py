# bot/cogs/admin.py
import discord                     # <- top‑level import for channel types
from discord.ext import commands
from ..config import cfg, save_cfg

class AdminCog(commands.Cog):
    """Administrative commands for configuring the bot."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="setchannel")
    async def setchannel(self, ctx, channel: discord.abc.GuildChannel):
        """Pick the channel (or voice) that will be renamed."""
        cfg.target_channel_id = channel.id
        cfg.target_category_id = 0
        save_cfg()
        await ctx.send(f"✅ Target set to {channel.mention}", ephemeral=True)

    @commands.hybrid_command(name="setprefix")
    async def setprefix(self, ctx, *, prefix: str):
        prefix = prefix.strip()
        if not (2 <= len(prefix) <= 30):
            await ctx.send("❗ Prefix must be 2‑30 characters.", ephemeral=True)
            return
        cfg.name_prefix = prefix
        save_cfg()
        await ctx.send(f"✅ Prefix updated to `{prefix}`", ephemeral=True)

    @commands.hybrid_command(name="setmax")
    async def setmax(self, ctx, maxplayers: int):
        if not (0 <= maxplayers <= 200):
            await ctx.send("❗ Max must be 0‑200.", ephemeral=True)
            return
        cfg.display_max = maxplayers
        save_cfg()
        await ctx.send(f"✅ Max override set to `{maxplayers}`.", ephemeral=True)

    @commands.hybrid_command(name="pause")
    async def pause(self, ctx):
        cfg.paused = True
        save_cfg()
        await ctx.send("⏸️ Automatic renaming paused.", ephemeral=True)

    @commands.hybrid_command(name="resume")
    async def resume(self, ctx):
        cfg.paused = False
        save_cfg()
        await ctx.send("▶️ Automatic renaming resumed.", ephemeral=True)

    @commands.hybrid_command(name="movetoggle")
    async def movetoggle(self, ctx, enabled: bool):
        cfg.move_enabled = enabled
        save_cfg()
        await ctx.send(f"🔀 Move‑from‑status VC {'enabled' if enabled else 'disabled'}.", ephemeral=True)

# -----------------------------
# Async setup function – required by discord.py 2.x
# -----------------------------
async def setup(bot):
    await bot.add_cog(AdminCog(bot))