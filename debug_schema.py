# debug_schema.py
import sys
sys.path.insert(0, '.')

from bot.utils.ftp_tracker import init_db, DB_PATH

print(f"Database path: {DB_PATH}")
print(f"Database exists: {DB_PATH.exists()}")

conn = init_db()
print("\n=== Tables in Database ===")
for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
    print(f"\nTable: {row[0]}")
    print(row[1])

print("\n=== Checking 'sessions' table specifically ===")
try:
    cols = conn.execute("PRAGMA table_info(sessions)").fetchall()
    for col in cols:
        print(f"  {col}")
except Exception as e:
    print(f"Error: {e}")

conn.close()