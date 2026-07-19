# bot/cogs/tracker.py
import asyncio
import discord
from datetime import datetime
from discord.ext import commands, tasks
from discord import app_commands
from ..utils.ftp_tracker import (
    init_db, record_join, record_leave,
    fetch_log_new_bytes, fetch_log_content, parse_events, load_offset, save_offset,
    check_and_perform_monthly_reset, get_monthly_leaderboard_top,
    get_global_leaderboard_top, get_currently_online, get_player_by_name,
    format_duration, get_persistent_message, set_persistent_message, replay_log_events
)
from ..config import cfg

class TrackerCog(commands.Cog):
    """Tracks player sessions via FTP log scraping, maintains monthly/all-time leaderboards."""

    def __init__(self, bot):
        self.bot = bot
        self.conn = None
        self._active_sessions = {}
        self._last_known_offset = load_offset()
        self._fail_count = 0

        self._recover_sessions()

        if cfg.tracker_enabled:
            self.tracker_loop.start()
        self.leaderboard_poster.start()

    def cog_unload(self):
        self.tracker_loop.cancel()
        self.leaderboard_poster.cancel()
        if self.conn:
            self.conn.close()

    def _recover_sessions(self):
        self.conn = init_db()
        for name, join_time in self.conn.execute(
            "SELECT name, join_time FROM sessions WHERE leave_time IS NULL"
        ):
            self._active_sessions[name] = join_time
            print(f"[Tracker] Recovered session: {name}")

        did_reset, old_period, new_period = check_and_perform_monthly_reset()
        if did_reset:
            print(f"[Tracker] Monthly reset on startup: {old_period} → {new_period}")

    # ========== EMBED BUILDERS ==========
    def _build_leaderboard_embed(self, global_=False):
        if global_:
            rows = get_global_leaderboard_top(20)
            embed = discord.Embed(title="🏆 All-Time Leaderboard", color=discord.Color.gold())
            embed.set_footer(text="Lifetime stats — never resets")
        else:
            rows = get_monthly_leaderboard_top(20)
            embed = discord.Embed(title="📅 Monthly Leaderboard", color=discord.Color.blue())
            embed.set_footer(text=f"Period: {datetime.utcnow().strftime('%Y-%m')} | Auto-updated")

        if not rows:
            embed.description = "*No data yet — be the first to drive!*"
            return embed

        medals = ["🥇", "🥈", "🥉"]
        desc_parts = []
        for rank, (name, secs, _, _) in enumerate(rows, 1):
            hrs = secs // 3600
            mins = (secs % 3600) // 60
            prefix = medals[rank - 1] if rank <= 3 else f"`#{rank}`"
            desc_parts.append(f"{prefix} **{name}** — {hrs}h {mins}m")

        embed.description = "\n".join(desc_parts[:20])
        return embed

    def _build_online_embed(self):
        players = get_currently_online()
        embed = discord.Embed(title="🚛 Currently Online", color=discord.Color.teal())
        if not players:
            embed.description = "Nobody's driving right now."
            return embed

        lines = []
        for p in players:
            join_time = datetime.fromisoformat(p["join_time"])
            elapsed = int((datetime.utcnow() - join_time).total_seconds())
            dur = format_duration(elapsed)
            lines.append(f"🟢 **{p['name']}** — {dur}")

        embed.description = "\n".join(lines)
        embed.set_footer(text=f"{len(players)} player(s) online")
        return embed

    # ========== PERSISTENT MESSAGE HANDLING ==========
    async def _post_or_update_leaderboard(self, channel_id, global_=False):
        if not channel_id:
            return

        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                return
        except Exception:
            return

        embed = self._build_leaderboard_embed(global_)
        key = "global_leaderboard" if global_ else "monthly_leaderboard"
        msg_id, stored_chan_id = get_persistent_message(key)

        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
                return
            except (discord.NotFound, discord.Forbidden):
                pass
            except Exception as exc:
                print(f"[Tracker] Error editing leaderboard: {exc}")

        try:
            msg = await channel.send(embed=embed)
            set_persistent_message(key, msg.id, channel_id)
            print(f"[Tracker] Posted {'global' if global_ else 'monthly'} leaderboard (msg {msg.id})")
        except Exception as exc:
            print(f"[Tracker] Failed to post leaderboard: {exc}")

    async def _update_online_message(self, channel_id):
        if not channel_id:
            return

        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                return
        except Exception:
            return

        embed = self._build_online_embed()
        msg_id, _ = get_persistent_message("online_players")

        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
                return
            except (discord.NotFound, discord.Forbidden):
                pass
            except Exception as exc:
                print(f"[Tracker] Error editing online message: {exc}")

        try:
            msg = await channel.send(embed=embed)
            set_persistent_message("online_players", msg.id, channel_id)
        except Exception as exc:
            print(f"[Tracker] Failed to post online message: {exc}")

    # ========== BACKGROUND TASKS ==========
    @tasks.loop(seconds=10)
    async def tracker_loop(self):
        if not cfg.tracker_enabled:
            return

        lines, new_size = await asyncio.to_thread(
            fetch_log_new_bytes, self._last_known_offset
        )

        if not lines:
            self._fail_count += 1
            if self._fail_count == 1:
                print("[Tracker] FTP unavailable; retrying on the next poll")
            return

        if self._fail_count:
            print("[Tracker] FTP connection restored")
        self._fail_count = 0
        events = parse_events(lines)
        had_events = len(events) > 0

        for event_type, name in events:
            if event_type == "join":
                if name not in self._active_sessions:
                    join_iso = datetime.utcnow().isoformat()
                    self._active_sessions[name] = join_iso
                    record_join(self.conn, name)
                    print(f"[Tracker] 🟢 {name} joined")

            elif event_type == "leave":
                if name in self._active_sessions:
                    join_iso = self._active_sessions.pop(name)
                    duration = record_leave(self.conn, name, join_iso)
                    dur_str = format_duration(duration)
                    print(f"[Tracker] 🔴 {name} left ({dur_str})")

        save_offset(new_size)
        self._last_known_offset = new_size
        check_and_perform_monthly_reset()

        # Update persistent leaderboard if events happened
        if had_events:
            await self._post_or_update_leaderboard(cfg.leaderboard_channel_id, global_=False)

    @tracker_loop.before_loop
    async def _before_tracker_loop(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=6)
    async def leaderboard_poster(self):
        if cfg.leaderboard_interval_hours == 0 or not cfg.leaderboard_channel_id:
            return
        await self._post_or_update_leaderboard(cfg.leaderboard_channel_id, global_=False)

    @leaderboard_poster.before_loop
    async def _before_leaderboard_poster(self):
        await self.bot.wait_until_ready()

    # ========== SLASH COMMANDS ==========
    @app_commands.command(name="top", description="Post a live-updating monthly leaderboard")
    async def cmd_top(self, interaction: discord.Interaction):
        embed = self._build_leaderboard_embed(global_=False)

        msg_id, stored_chan = get_persistent_message("monthly_leaderboard")
        channel = interaction.channel

        if msg_id and stored_chan == channel.id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
                await interaction.response.send_message("✅ Leaderboard refreshed!", ephemeral=True)
                return
            except (discord.NotFound, discord.Forbidden):
                pass

        msg = await channel.send(embed=embed)
        set_persistent_message("monthly_leaderboard", msg.id, channel.id)
        await interaction.response.send_message("✅ Leaderboard posted! It will auto-update as players join/leave.", ephemeral=True)

    @app_commands.command(name="global", description="Show top players by all-time playtime")
    async def cmd_global(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = self._build_leaderboard_embed(global_=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="playtime", description="Show playtime stats for a player")
    @app_commands.describe(player="Player name to look up")
    async def cmd_playtime(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer(ephemeral=True)
        stats = get_player_by_name(player, search_monthly=True, search_all_time=False)
        if not stats:
            await interaction.followup.send(f"❌ No stats found for **{player}**", ephemeral=True)
            return

        hrs = stats["total_seconds"] // 3600
        mins = (stats["total_seconds"] % 3600) // 60

        embed = discord.Embed(title=f"📊 {player}'s Stats", color=discord.Color.green())
        embed.add_field(name="Monthly Playtime", value=f"{hrs}h {mins}m", inline=True)
        embed.add_field(name="Sessions", value=str(stats["sessions"]), inline=True)
        embed.add_field(name="Last Seen", value=stats["last_seen"] or "Unknown", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="online", description="Show currently online players")
    async def cmd_online(self, interaction: discord.Interaction):
        embed = self._build_online_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="backfill", description="Backfill playtime stats from the available FTP log file")
    @app_commands.default_permissions(administrator=True)
    async def cmd_backfill(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            lines, _ = await asyncio.to_thread(fetch_log_content)
            if not lines:
                await interaction.followup.send("⚠️ No log content was retrieved from the FTP source.", ephemeral=True)
                return

            if self.conn is None:
                self.conn = init_db()

            processed = replay_log_events(lines, self.conn)
            await self._post_or_update_leaderboard(cfg.leaderboard_channel_id, global_=False)
            await interaction.followup.send(
                f"✅ Replayed {processed} log event(s) and refreshed the leaderboard.",
                ephemeral=True,
            )
        except Exception as exc:
            await interaction.followup.send(f"❌ Replay failed: {exc}", ephemeral=True)

    # ========== STAFF COMMANDS ==========
    @app_commands.command(name="forcereset", description="Force monthly leaderboard reset (staff only)")
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_forcereset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        did_reset, old_period, new_period = check_and_perform_monthly_reset()
        if did_reset:
            await self._post_or_update_leaderboard(cfg.leaderboard_channel_id, global_=False)
            await interaction.followup.send(
                f"✅ Reset complete! Archived `{old_period}`, started `{new_period}`", ephemeral=True
            )
        else:
            await interaction.followup.send("ℹ️ No reset needed — still in same period.", ephemeral=True)

    @app_commands.command(name="synctracker", description="Reload tracker config (staff only)")
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_synctracker(self, interaction: discord.Interaction):
        from ..config import load_cfg
        load_cfg()
        await interaction.response.send_message("✅ Tracker config reloaded!", ephemeral=True)

# ========== SETUP ==========
async def setup(bot):
    await bot.add_cog(TrackerCog(bot))