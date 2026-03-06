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
# Async cog loader – skips __init__.py (which isn’t a cog)
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
    print(f"🚀 {bot.user} is online – config: {cfg}")


@bot.event
async def setup_hook():
    await load_all_cogs()


bot.run(os.getenv("DISCORD_TOKEN"))