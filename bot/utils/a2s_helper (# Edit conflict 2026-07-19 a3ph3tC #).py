# bot/utils/a2s_helper.py
"""
A2S Server Query Helper — Modern python-a2s API
Queries ATS/ETS2 dedicated servers for player count and server info.
"""

import os
import a2s
from typing import Tuple, Optional

SERVER_IP = os.getenv("A2S_HOST", "51.222.255.93")
DEFAULT_QUERY_PORT = int(os.getenv("A2S_PORT", "22006"))
TIMEOUT = 5.0


def _candidate_ports(override_port: int = None):
    ports = []
    if override_port is not None:
        ports.append(override_port)
    if DEFAULT_QUERY_PORT not in ports:
        ports.append(DEFAULT_QUERY_PORT)
    if 27016 not in ports:
        ports.append(27016)
    if 27015 not in ports:
        ports.append(27015)
    return ports


def query_server(max_players: int = 8, override_ip: str = None, override_port: int = None) -> Tuple[bool, int, Optional[int]]:
    """
    Query ATS server for status.
    
    Returns:
        (is_online, player_count, max_players)
        - is_online: True if server responded
        - player_count: Number of connected players
        - max_players: Server max capacity (None if unknown)
    """
    ip = override_ip or SERVER_IP
    last_error = None

    for port in _candidate_ports(override_port):
        try:
            addr = (ip, port)
            info = a2s.info(addr, timeout=TIMEOUT)
            players = a2s.players(addr, timeout=TIMEOUT)

            online = True
            player_count = len(players) if players else 0
            server_max = info.max_players if hasattr(info, 'max_players') and info.max_players else max_players
            return online, player_count, server_max
        except Exception as exc:
            last_error = exc

    print(f"[A2S] Could not query {ip} on ports {_candidate_ports(override_port)}: {last_error}")
    return False, 0, max_players

def get_server_info(override_ip: str = None, override_port: int = None) -> dict:
    """Get detailed server information."""
    ip = override_ip or SERVER_IP
    last_error = None

    for port in _candidate_ports(override_port):
        try:
            addr = (ip, port)
            info = a2s.info(addr, timeout=TIMEOUT)

            return {
                "server_name": getattr(info, 'server_name', 'Unknown'),
                "map": getattr(info, 'map_name', 'Unknown'),
                "player_count": getattr(info, 'player_count', 0),
                "max_players": getattr(info, 'max_players', 0),
                "password_protected": getattr(info, 'password_protected', False),
                "online": True,
            }
        except Exception as exc:
            last_error = exc

    print(f"[A2S] Could not query {ip} on ports {_candidate_ports(override_port)}: {last_error}")
    return {
        "server_name": "Offline",
        "map": "",
        "player_count": 0,
        "max_players": 0,
        "password_protected": False,
        "online": False,
    }

def build_name(prefix: str, online: bool, players: int, maxp: int) -> str:
    """Build channel/voice name from server status."""
    if not online:
        return f"{prefix} | OFFLINE"
    
    maxp = maxp or "?"
    return f"{prefix} | {players}/{maxp}"