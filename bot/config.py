# bot/config.py
import os, json
from dataclasses import dataclass

CONFIG_PATH = "./config.json"

@dataclass
class BotConfig:
    target_channel_id: int = int(os.getenv("STATUS_CHANNEL_ID", "0"))
    target_category_id: int = int(os.getenv("STATUS_CATEGORY_ID", "0"))
    name_prefix: str = os.getenv("NAME_PREFIX", "ats-status")
    display_max: int = int(os.getenv("DISPLAY_MAXPLAYERS", "0"))
    paused: bool = False
    move_enabled: bool = True
    interval_sec: int = max(int(os.getenv("INTERVAL_SEC", "60")), 15)
    redirect_vc_id: int = int(os.getenv("REDIRECT_VC_ID", "0"))   # <-- destination VC

# Global singleton – import this everywhere
cfg = BotConfig()

def load_cfg() -> BotConfig:
    """Read config.json (or create a fresh one) and sync it into `cfg`."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            setattr(cfg, k, v)
    else:
        save_cfg()
    return cfg

def save_cfg() -> None:
    """Persist the current `cfg` to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg.__dict__, f, indent=2)

# Load at import time so every module sees the same object
load_cfg()