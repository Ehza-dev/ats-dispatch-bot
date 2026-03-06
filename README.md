# Discord ATS Status Bot

A modular Discord bot that monitors an ATS server, renames a status channel, and optionally moves users out of a “trap” voice channel.

## Setup

1. Clone the repo  
   ```
   bash
   git clone git@github.com:USER/REPO.git
   cd REPO
2. Create a virtual environment and install deps
  ```
  python -m venv .venv
  source .venv/bin/activate   # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
```
3. Copy the example env file and fill in your secrets
```
cp .env.example .env
# edit .env with your Discord token, API keys, channel IDs, etc.
```
4. Run the bot
```
python -m bot.main
```
