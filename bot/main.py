# bot/main.py
import os
import discord                     # needed for Intents
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------
# Intents – make sure we have everything the bot actually uses.
# --------------------------------------------------------------
intents = discord.Intents.none()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True   # <-- required for reading normal messages

bot = commands.Bot(command_prefix="!", intents=intents)


# ------------------------------------------------------------------
# Async cog loader – skips __init__.py (which isn't a cog)
# ------------------------------------------------------------------
async def load_all_cogs():
    cog_dir = os.path.join(os.path.dirname(__file__), "cogs")
    for fname in os.listdir(cog_dir):
        if not fname.endswith(".py") or fname.startswith("__"):
            continue                      # skip __init__.py and non‑py files
        ext = f"bot.cogs.{fname[:-3]}"
        try:
            await bot.load_extension(ext)   # await the coroutine!
            print(f"[+] Loaded cog: {ext}")
        except Exception as exc:
            print(f"[!] Failed to load {ext}: {exc!r}")


@bot.event
async def on_ready():
    from .config import cfg
    # Print config without exposing secrets
    safe_cfg = {k: v for k, v in cfg.__dict__.items() 
                if not any(s in k.lower() for s in ['pass', 'token', 'secret', 'webhook'])}
    print(f"🚀 {bot.user} is online – config: {safe_cfg}")
    
    # Sync slash commands with Discord (only once per session)
    try:
        print("[*] Syncing slash commands...")
        synced = await bot.tree.sync()
        print(f"[✓] Synced {len(synced)} slash command(s) globally")
    except Exception as exc:
        print(f"[!] Failed to sync commands: {exc!r}")


@bot.event
async def setup_hook():
    await load_all_cogs()


bot.run(os.getenv("DISCORD_TOKEN"))