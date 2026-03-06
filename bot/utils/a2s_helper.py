# bot/utils/a2s_helper.py
import os, socket, a2s
from ..config import cfg

def query_server(display_max: int):
    """
    Query the A2S server and return a tuple:
    (online: bool, players: int, maxplayers: int)
    """
    addr = (os.getenv("A2S_HOST"), int(os.getenv("A2S_PORT")))
    try:
        info = a2s.info(addr, timeout=2.5)
        players = getattr(info, "player_count", 0)
        maxplayers = getattr(info, "max_players", 0)

        # ATS sometimes caps max at 8 – override if we have a user‑defined max
        if display_max > 0 and maxplayers <= 8:
            maxplayers = display_max

        return True, players, maxplayers
    except (socket.timeout, OSError, Exception) as e:
        print(f"[A2S] query failed ({addr}): {e!r}")
        return False, 0, (display_max if display_max > 0 else 0)

def build_name(prefix: str, online: bool, players: int, maxplayers: int) -> str:
    """Pretty‑print the channel name."""
    if not online:
        return f"🔴 {prefix}: offline"
    mp = str(maxplayers) if maxplayers > 0 else "?"
    return f"🟢 {prefix}: {players}/{mp}"