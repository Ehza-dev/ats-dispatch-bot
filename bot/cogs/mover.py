# bot/cogs/mover.py
import discord
from discord.ext import commands
from ..config import cfg, save_cfg

class MoverCog(commands.Cog):
    """Moves users who join the status voice channel to a safe landing zone."""

    def __init__(self, bot):
        self.bot = bot

    async def _fetch_redirect(self):
        """Return the configured redirect voice channel, or None."""
        if not cfg.move_enabled or cfg.redirect_vc_id == 0:
            return None
        try:
            ch = self.bot.get_channel(cfg.redirect_vc_id) or \
                 await self.bot.fetch_channel(cfg.redirect_vc_id)
            return ch if isinstance(ch, discord.VoiceChannel) else None
        except Exception as e:
            print("[Mover] redirect fetch error:", e)
            return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Bail early if feature disabled or no trap channel set
        if not cfg.move_enabled or cfg.target_channel_id == 0:
            return

        # We're only interested when a non‑bot joins the *trap* VC
        if after.channel is None or after.channel.id != cfg.target_channel_id:
            return
        if member.bot:
            return

        dest = await self._fetch_redirect()
        if dest is None:
            return

        # Avoid moving onto the same channel (shouldn’t happen)
        if dest.id == after.channel.id:
            return

        print(f"[Mover] {member} → {dest.name}")
        try:
            await member.move_to(dest, reason="Status VC is not joinable")
        except Exception as e:
            print("[Mover] move failed:", e)

# -----------------------------
# Async setup – required for discord.py 2.x
# -----------------------------
async def setup(bot):
    await bot.add_cog(MoverCog(bot))