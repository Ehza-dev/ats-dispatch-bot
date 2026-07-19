import importlib
from datetime import datetime

import bot.utils.ftp_tracker as ftp_tracker
import bot.utils.a2s_helper as a2s_helper


def test_tracker_imports_without_error():
    mod = importlib.import_module("bot.cogs.tracker")
    assert hasattr(mod, "TrackerCog")


def test_record_leave_updates_open_session(tmp_path, monkeypatch):
    db_path = tmp_path / "tracker.db"
    monkeypatch.setattr(ftp_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(ftp_tracker, "STATE_PATH", tmp_path / "ftp_offset.json")

    conn = ftp_tracker.init_db()
    ftp_tracker.record_join(conn, "Alice")

    duration = ftp_tracker.record_leave(conn, "Alice", datetime.utcnow().isoformat())

    assert duration >= 0
    row = conn.execute(
        "SELECT leave_time, duration_seconds FROM sessions WHERE name = ? ORDER BY id DESC LIMIT 1",
        ("Alice",),
    ).fetchone()
    assert row[0] is not None
    assert row[1] == duration


def test_query_server_uses_configured_host_and_port(monkeypatch):
    calls = []

    class FakeInfo:
        player_count = 3
        max_players = 20
        server_name = "Test Server"
        map_name = "test"
        password_protected = False

    def fake_info(addr, timeout):
        calls.append(("info", addr, timeout))
        return FakeInfo()

    monkeypatch.setattr(a2s_helper, "a2s", type("FakeA2S", (), {"info": staticmethod(fake_info)}))
    monkeypatch.setattr(a2s_helper, "SERVER_IP", "example.test")
    monkeypatch.setattr(a2s_helper, "DEFAULT_QUERY_PORT", 22006)

    online, players, max_players = a2s_helper.query_server(8)

    assert online is True
    assert players == 3
    assert max_players == 20
    assert calls[0][1] == ("example.test", 22006)
    assert calls[0][2] == 5.0


def test_build_name_includes_online_indicator():
    assert a2s_helper.build_name("Convoy Status", True, 3, 20) == "🟢 Convoy Status | 3/20"
    assert a2s_helper.build_name("Convoy Status", False, 0, 20) == "🔴 Convoy Status | OFFLINE"
