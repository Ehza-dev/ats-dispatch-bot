# bot/utils/ftp_tracker.py
"""
ATS Player Tracker — FTP Log Scraping Module
Data layer only — all config pulled from bot.config.cfg
Uses player name as primary key (no Steam IDs available in ATS logs).
Deduplicates events within each poll cycle.
"""

import ftplib
import re
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import cfg

# Paths relative to bot/ directory
DB_PATH = Path(__file__).parent.parent / "tracker.db"
STATE_PATH = Path(__file__).parent.parent / "ftp_offset.json"

# Regex patterns for ATS log format
# Join: [MP] PlayerName connected, client_id = XX (guess — verify with your logs)
JOIN_RE = re.compile(
    r'\[MP\] (.+?) connected, client_id = \d+'
)
# Leave: [MP] PlayerName disconnected, client_id = XX
LEAVE_RE = re.compile(
    r'\[MP\] (.+?) disconnected, client_id = \d+'
)
# Filter out [Chat] lines — they're duplicates
CHAT_RE = re.compile(r'^.*\[MP\] \[Chat\]')

# ========== DATABASE ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS all_time_totals (
            name TEXT PRIMARY KEY,
            total_seconds INTEGER DEFAULT 0,
            session_count INTEGER DEFAULT 0,
            last_seen TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS monthly_stats (
            name TEXT PRIMARY KEY,
            total_seconds INTEGER DEFAULT 0,
            session_count INTEGER DEFAULT 0,
            last_seen TEXT,
            period TEXT NOT NULL
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS monthly_archive (
            name TEXT NOT NULL,
            total_seconds INTEGER DEFAULT 0,
            session_count INTEGER DEFAULT 0,
            period TEXT NOT NULL,
            archived_at TEXT NOT NULL,
            PRIMARY KEY (name, period)
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            join_time TEXT NOT NULL,
            leave_time TEXT,
            duration_seconds INTEGER,
            period TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    current_period = datetime.utcnow().strftime("%Y-%m")
    conn.execute(
        "INSERT OR IGNORE INTO metadata (key, value) VALUES ('current_period', ?)",
        (current_period,)
    )
    conn.execute(
        "INSERT OR IGNORE INTO metadata (key, value) VALUES ('last_reset', ?)",
        (datetime.utcnow().isoformat(),)
    )
    
    conn.commit()
    return conn

def get_current_period():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = 'current_period'"
    ).fetchone()
    conn.close()
    return row[0] if row else datetime.utcnow().strftime("%Y-%m")

def is_new_period():
    current_period = get_current_period()
    now = datetime.utcnow().strftime("%Y-%m")
    return now != current_period

def archive_monthly_data(conn):
    current_period = get_current_period()
    now = datetime.utcnow().isoformat()
    
    conn.execute("""
        INSERT INTO monthly_archive (name, total_seconds, session_count, period, archived_at)
        SELECT name, total_seconds, session_count, ?, ?
        FROM monthly_stats
    """, (current_period, now))
    
    new_period = datetime.utcnow().strftime("%Y-%m")
    conn.execute("UPDATE metadata SET value = ? WHERE key = 'current_period'", (new_period,))
    conn.execute("UPDATE metadata SET value = ? WHERE key = 'last_reset'", (now,))
    conn.execute("DELETE FROM monthly_stats")
    
    return current_period, new_period

def record_join(conn, name, period=None):
    if period is None:
        period = get_current_period()
    conn.execute(
        "INSERT INTO sessions (name, join_time, period) VALUES (?, ?, ?)",
        (name, datetime.utcnow().isoformat(), period)
    )
    conn.commit()

def record_leave(conn, name, join_time_str, period=None):
    join_time = datetime.fromisoformat(join_time_str)
    leave_time = datetime.utcnow()
    duration = int((leave_time - join_time).total_seconds())
    if period is None:
        period = get_current_period()

    row_id = conn.execute(
        "SELECT id FROM sessions WHERE name = ? AND leave_time IS NULL ORDER BY id DESC LIMIT 1",
        (name,),
    ).fetchone()

    if row_id:
        conn.execute(
            "UPDATE sessions SET leave_time = ?, duration_seconds = ? WHERE id = ?",
            (leave_time.isoformat(), duration, row_id[0]),
        )

    conn.execute("""
        INSERT INTO all_time_totals (name, total_seconds, session_count, last_seen)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(name) DO UPDATE SET
            total_seconds = total_seconds + ?,
            session_count = session_count + 1,
            last_seen = ?
    """, (name, duration, leave_time.isoformat(), duration, leave_time.isoformat()))

    conn.execute("""
        INSERT INTO monthly_stats (name, total_seconds, session_count, last_seen, period)
        VALUES (?, ?, 1, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            total_seconds = total_seconds + ?,
            session_count = session_count + 1,
            last_seen = ?
    """, (name, duration, period, period, duration, period))

    conn.commit()
    return duration

# ========== FTP ==========
def _connect_ftp(retries=2):
    last_error = None
    for attempt in range(retries):
        ftp = ftplib.FTP()
        try:
            ftp.connect(cfg.ftp_host, cfg.ftp_port, timeout=10)
            ftp.login(cfg.ftp_user, cfg.ftp_pass)
            return ftp
        except Exception as exc:
            last_error = exc
            try:
                ftp.close()
            except Exception:
                pass
            if attempt < retries - 1:
                continue
    raise last_error


def fetch_log_new_bytes(last_size):
    try:
        ftp = _connect_ftp()
        try:
            size = ftp.size(cfg.log_file) or 0
        except Exception:
            print("[Tracker] Could not get file size, assuming 0")
            size = 0

        if size <= last_size:
            ftp.quit()
            return [], last_size

        ftp.sendcmd(f"REST {last_size}")

        chunks = []
        ftp.retrbinary(f"RETR {cfg.log_file}", chunks.append)
        ftp.quit()

        content = b"".join(chunks).decode("utf-8", errors="replace")
        lines = content.splitlines()
        return lines, size

    except Exception as e:
        print(f"[Tracker] FTP error: {e}")
        return [], last_size


def fetch_log_content():
    try:
        ftp = _connect_ftp()

        try:
            size = ftp.size(cfg.log_file) or 0
        except Exception:
            print("[Tracker] Could not get file size, assuming 0")
            size = 0

        chunks = []
        ftp.retrbinary(f"RETR {cfg.log_file}", chunks.append)
        ftp.quit()

        content = b"".join(chunks).decode("utf-8", errors="replace")
        return content.splitlines(), size
    except Exception as e:
        print(f"[Tracker] FTP error: {e}")
        return [], 0


def replay_log_events(lines, conn=None, period=None):
    if conn is None:
        conn = init_db()

    active_sessions = {}
    events = parse_events(lines)
    for event_type, name in events:
        if event_type == "join":
            if name not in active_sessions:
                active_sessions[name] = datetime.utcnow().isoformat()
                record_join(conn, name, period=period)
        elif event_type == "leave":
            if name in active_sessions:
                join_iso = active_sessions.pop(name)
                record_leave(conn, name, join_iso, period=period)

    return len(events)

def parse_events(lines):
    """Parse [MP] join/leave events. Deduplicates within batch, filters [Chat] lines."""
    events = []
    seen_lines = set()  # Track exact lines already processed in this batch
    
    for line in lines:
        # Skip if already seen in this batch (dedup)
        if line.strip() in seen_lines:
            continue
        seen_lines.add(line.strip())
        
        # Skip [Chat] lines — duplicates
        if CHAT_RE.match(line):
            continue
        
        # Check for disconnect
        m = LEAVE_RE.search(line)
        if m:
            events.append(("leave", m.group(1)))
            continue
        
        # Check for connect
        m = JOIN_RE.search(line)
        if m:
            events.append(("join", m.group(1)))
            continue
    
    return events

# ========== HELPERS ==========
def format_duration(seconds):
    hrs, rem = divmod(int(seconds), 3600)
    mins, secs = divmod(rem, 60)
    if hrs > 0:
        return f"{hrs}h {mins}m"
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"

def load_offset():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text()).get("size", 0)
        except Exception:
            pass
    return 0

def save_offset(size):
    STATE_PATH.write_text(json.dumps({"size": size}))

def get_persistent_message(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = ?", (f"{key}_msg_id",)
    ).fetchone()
    chan = conn.execute(
        "SELECT value FROM metadata WHERE key = ?", (f"{key}_channel_id",)
    ).fetchone()
    conn.close()
    msg_id = int(row[0]) if row and row[0] else 0
    channel_id = int(chan[0]) if chan and chan[0] else 0
    return msg_id, channel_id

def set_persistent_message(key, msg_id, channel_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?",
        (f"{key}_msg_id", str(msg_id), str(msg_id))
    )
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?",
        (f"{key}_channel_id", str(channel_id), str(channel_id))
    )
    conn.commit()
    conn.close()

def get_leaderboard_top(n=20):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT name, total_seconds, session_count, last_seen
        FROM monthly_stats
        ORDER BY total_seconds DESC
        LIMIT ?
    """, (n,)).fetchall()
    conn.close()
    return [(name, secs, sessions, last) for name, secs, sessions, last in rows]


def get_monthly_leaderboard_top(n=20):
    """Backward-compatible alias for the monthly leaderboard helper."""
    return get_leaderboard_top(n)


def get_global_leaderboard_top(n=20):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT name, total_seconds, session_count, last_seen
        FROM all_time_totals
        ORDER BY total_seconds DESC
        LIMIT ?
    """, (n,)).fetchall()
    conn.close()
    return [(name, secs, sessions, last) for name, secs, sessions, last in rows]

def get_player_by_name(name, search_monthly=True, search_all_time=False):
    if search_monthly:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT total_seconds, session_count, last_seen
            FROM monthly_stats
            WHERE name = ?
        """, (name,)).fetchone()
        conn.close()
        if row:
            return {"type": "monthly", "total_seconds": row[0], "sessions": row[1], "last_seen": row[2]}
    
    if search_all_time:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT total_seconds, session_count, last_seen
            FROM all_time_totals
            WHERE name = ?
        """, (name,)).fetchone()
        conn.close()
        if row:
            return {"type": "all_time", "total_seconds": row[0], "sessions": row[1], "last_seen": row[2]}
    
    return None

def get_currently_online():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT name, join_time, period
        FROM sessions
        WHERE leave_time IS NULL
    """).fetchall()
    conn.close()
    return [{"name": r[0], "join_time": r[1], "period": r[2]} for r in rows]

def check_and_perform_monthly_reset():
    if not is_new_period():
        return False, None, None
    
    conn = init_db()
    old_period, new_period = archive_monthly_data(conn)
    conn.close()
    
    print(f"[Tracker] Monthly reset complete: archived {old_period}, started {new_period}")
    return True, old_period, new_period

# Track processed events by line hash (per-cog instance)
_processed_lines = set()
_last_known_offset = load_offset()
_fail_count = 0
_active_sessions = {}