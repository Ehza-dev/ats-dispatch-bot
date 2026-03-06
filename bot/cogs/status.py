# bot/cogs/status.py
import asyncio
import discord
from discord.ext import commands, tasks
from ..utils.a2s_helper import query_server, build_name
from ..config import cfg, save_cfg

class StatusCog(commands.Cog):
    """Renames the target channel/voice based on ATS server status."""

    def __init__(self, bot):
        self.bot = bot
        self._last_name = None
        self._lock = asyncio.Lock()
        self.rename_loop.start()

    def cog_unload(self):
        self.rename_loop.cancel()

    async def _get_target(self):
        """Resolve the configured channel or category."""
        if cfg.target_channel_id:
            return self.bot.get_channel(cfg.target_channel_id) or \
                   await self.bot.fetch_channel(cfg.target_channel_id)
        if cfg.target_category_id:
            return self.bot.get_channel(cfg.target_category_id) or \
                   await self.bot.fetch_channel(cfg.target_category_id)
        return None

    async def _do_rename(self):
        async with self._lock:
            online, players, maxp = await asyncio.to_thread(
                query_server, cfg.display_max
            )
            new_name = build_name(cfg.name_prefix, online, players, maxp)

            target = await self._get_target()
            if not target:
                return  # Nothing to rename yet

            if cfg.paused:
                return  # Silently skip while paused

            if new_name != self._last_name:
                await target.edit(name=new_name)
                self._last_name = new_name

    # NOTE: `seconds=` expects an *int*, not a callable.
    @tasks.loop(seconds=cfg.interval_sec)
    async def rename_loop(self):
        try:
            await self._do_rename()
        except Exception as exc:
            print("[StatusLoop] error:", exc)

    @commands.hybrid_command(name="status")
    async def status(self, ctx):
        """Show the current ATS server status."""
        online, players, maxp = await asyncio.to_thread(
            query_server, cfg.display_max
        )
        txt = f"**{'Online' if online else 'Offline'}** — `{players}/{maxp or '?'}`"
        await ctx.send(txt, ephemeral=True)

    @commands.hybrid_command(name="forceupdate")
    async def forceupdate(self, ctx):
        """Force an immediate rename and report what happened."""
        await ctx.defer(ephemeral=True)
        await self._do_rename()
        await ctx.send("✅ Update attempted – check the channel name.", ephemeral=True)

# -----------------------------
# Async setup – required for discord.py 2.x
# -----------------------------
async def setup(bot):
    await bot.add_cog(StatusCog(bot))