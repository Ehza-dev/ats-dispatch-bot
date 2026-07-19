# bot/cogs/status.py
import asyncio
import discord
from discord.ext import commands, tasks
from ..utils.a2s_helper import query_server, build_name
from ..config import cfg, save_cfg


async def _send_reply(ctx, message, ephemeral=True):
    """Send a reply that works for both slash commands and prefix commands."""
    try:
        if isinstance(ctx, discord.Interaction):
            if not ctx.response.is_done():
                await ctx.response.send_message(message, ephemeral=ephemeral)
        else:
            await ctx.send(message)
    except (discord.NotFound, discord.HTTPException, RuntimeError):
        pass


class StatusCog(commands.Cog):
    """Renames the target channel/voice based on ATS server status."""

    def __init__(self, bot):
        self.bot = bot
        self._last_name = None
        self._lock = asyncio.Lock()
        self._last_edit = 0.0
        self._rate_limited_until = 0.0
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

    async def _do_rename(self, force=False):
        async with self._lock:
            now = asyncio.get_running_loop().time()
            if self._rate_limited_until and now < self._rate_limited_until:
                return False, f"rate_limited:{self._rate_limited_until - now:.1f}s"

            try:
                online, players, maxp = await asyncio.to_thread(
                    query_server, cfg.display_max
                )
                new_name = build_name(cfg.name_prefix, online, players, maxp)

                target = await self._get_target()
                if not target:
                    return False, "target_missing"

                if cfg.paused:
                    return False, "paused"

                if new_name == self._last_name and not force:
                    return False, "unchanged"

                if not force:
                    if now - self._last_edit < 20:
                        return False, "rate_limited"

                await target.edit(name=new_name)
                self._last_name = new_name
                self._last_edit = now
                return True, new_name
            except discord.errors.RateLimited as exc:
                self._rate_limited_until = now + max(60.0, float(exc.retry_after or 60))
                print(f"[Status] Discord rate limited; backing off for {self._rate_limited_until - now:.1f}s")
                return False, f"rate_limited:{self._rate_limited_until - now:.1f}s"
            except (discord.Forbidden, discord.HTTPException, discord.NotFound, AttributeError, RuntimeError) as exc:
                return False, f"discord_error:{exc}"

    # Keep the rename loop at a conservative cadence to avoid Discord rate limits.
    @tasks.loop(seconds=10)
    async def rename_loop(self):
        try:
            await self._do_rename()
        except Exception:
            pass

    @commands.hybrid_command(name="status")
    async def status(self, ctx):
        """Show the current ATS server status."""
        online, players, maxp = await asyncio.to_thread(
            query_server, cfg.display_max
        )
        indicator = "🟢" if online else "🔴"
        txt = f"{indicator} **{'Online' if online else 'Offline'}** — `{players}/{maxp or '?'}`"
        await _send_reply(ctx, txt, ephemeral=True)

    @commands.hybrid_command(name="forceupdate")
    async def forceupdate(self, ctx):
        """Force an immediate rename and report what happened."""
        try:
            changed, reason = await self._do_rename(force=True)
            if changed:
                await _send_reply(ctx, "✅ Update sent – check the channel name.", ephemeral=True)
            else:
                await _send_reply(ctx, f"⚠️ No rename was applied. Reason: {reason}", ephemeral=True)
        except Exception:
            await _send_reply(ctx, "❌ Update failed. Check the target channel configuration.", ephemeral=True)

# -----------------------------
# Async setup – required for discord.py 2.x
# -----------------------------
async def setup(bot):
    await bot.add_cog(StatusCog(bot))