# bot/config.py
import os, json
from dataclasses import dataclass, field

CONFIG_PATH = "./config.json"

@dataclass
class BotConfig:
    # ===== Existing =====
    target_channel_id: int = int(os.getenv("STATUS_CHANNEL_ID", "0"))
    target_category_id: int = int(os.getenv("STATUS_CATEGORY_ID", "0"))
    name_prefix: str = os.getenv("NAME_PREFIX", "ats-status")
    display_max: int = int(os.getenv("DISPLAY_MAXPLAYERS", "0"))
    paused: bool = False
    move_enabled: bool = True
    interval_sec: int = max(int(os.getenv("INTERVAL_SEC", "60")), 15)
    redirect_vc_id: int = int(os.getenv("REDIRECT_VC_ID", "0"))

    # ===== Tracker: Secrets (from .env only — never written to config.json) =====
    ftp_host: str = os.getenv("FTP_HOST", "")
    ftp_port: int = int(os.getenv("FTP_PORT", "8821"))
    ftp_user: str = os.getenv("FTP_USER", "")
    ftp_pass: str = os.getenv("FTP_PASS", "")
    log_file: str = os.getenv("LOG_FILE", "")
    tracker_webhook_url: str = os.getenv("TRACKER_WEBHOOK_URL", "")

    # ===== Tracker: Runtime (persisted in config.json, editable at runtime) =====
    tracker_enabled: bool = True
    poll_interval: int = int(os.getenv("TRACKER_POLL_INTERVAL", "10"))
    leaderboard_channel_id: int = int(os.getenv("LEADERBOARD_CHANNEL_ID", "0"))
    leaderboard_interval_hours: int = int(os.getenv("LEADERBOARD_INTERVAL_HOURS", "6"))
    tracker_announce_channel_id: int = int(os.getenv("TRACKER_ANNOUNCE_CHANNEL_ID", "0"))

# Global singleton – import this everywhere
cfg = BotConfig()

def load_cfg() -> BotConfig:
    """Read config.json (or create a fresh one) and sync it into `cfg`.
    Skip secret fields so .env values are never overwritten by JSON."""
    SECRET_KEYS = {
        "ftp_host", "ftp_port", "ftp_user", "ftp_pass", "log_file",
        "tracker_webhook_url",
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in SECRET_KEYS:
                continue  # Never load secrets from JSON
            setattr(cfg, k, v)
    else:
        save_cfg()
    return cfg

def save_cfg() -> None:
    """Persist the current `cfg` to disk, excluding secret fields."""
    SECRET_KEYS = {
        "ftp_host", "ftp_port", "ftp_user", "ftp_pass", "log_file",
        "tracker_webhook_url",
    }
    safe = {k: v for k, v in cfg.__dict__.items() if k not in SECRET_KEYS}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2)

# Load at import time so every module sees the same object
load_cfg()