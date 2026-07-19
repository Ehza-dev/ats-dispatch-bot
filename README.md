# Discord ATS Status Bot

A modular Discord bot that:
- queries an ATS server for player counts,
- renames a target channel or category with status info,
- optionally moves users who join the status voice channel,
- and exposes a Trucky webhook route for job speed lookups.

## Features

- `!setchannel <channel>` — select the channel or voice channel to rename
- `!setprefix <prefix>` — update the status name prefix
- `!setmax <maxplayers>` — set the maximum player display override
- `!pause` / `!resume` — pause and resume automatic renaming
- `!movetoggle <true|false>` — enable or disable the move-from-status voice feature
- `!status` — display the current ATS server status
- `!forceupdate` — force an immediate rename attempt

## Trucky webhook support

- The bot registers an aiohttp route at `/trucky/webhook`
- Incoming POST requests trigger a Trucky job lookup
- Results are posted into the channel set by `TRUCKY_LOGS_CHANNEL_ID`

## Setup

1. Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. Copy the example env file and fill in your values:

```powershell
copy .env.example .env
```

3. Edit `.env` with your Discord bot token, Trucky access token, channel IDs, and ATS settings.

4. Start the bot:

```powershell
python bot\main.py
```

## Configuration

The bot loads initial values from `.env` and persists runtime settings to `config.json`.

Key environment variables:

- `DISCORD_TOKEN` — your Discord bot token
- `TRUCKY_ACCESS_TOKEN` — Trucky API access token
- `TRUCKY_LOGS_CHANNEL_ID` — Discord channel ID where webhook replies are posted
- `STATUS_CHANNEL_ID` — channel or voice channel ID to rename
- `STATUS_CATEGORY_ID` — category ID to rename if no channel is configured
- `REDIRECT_VC_ID` — destination voice channel for moved users
- `A2S_HOST` / `A2S_PORT` — ATS server query host and port
- `DISPLAY_MAXPLAYERS` — maximum player count shown in the status name
- `INTERVAL_SEC` — rename interval in seconds
- `NAME_PREFIX` — prefix used for the renamed channel name
