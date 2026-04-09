import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from history_store import HistoryStore


def test_history_store_persists_sessions_and_messages(tmp_path):
    db_path = tmp_path / "history.db"
    store = HistoryStore(db_path)
    session_id = store.create_session(
        file_name="demo.py",
        file_path="/tmp/demo.py",
        code="print('hi')",
        model="qwen",
        messages=[{"role": "system", "content": "sys"}],
    )
    store.append_message(session_id, "user", "hello")
    store.append_message(session_id, "assistant", "world")
    store.close()

    reopened = HistoryStore(db_path)
    sessions = reopened.load_open_sessions()
    assert len(sessions) == 1
    assert sessions[0].file_name == "demo.py"
    assert sessions[0].file_path == "/tmp/demo.py"
    assert reopened.load_messages(session_id) == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]


def test_history_store_mark_session_closed_hides_from_restore(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    session_id = store.create_session(
        file_name="demo.py",
        file_path="",
        code="print('hi')",
        model="",
        messages=[{"role": "system", "content": "sys"}],
    )
    assert [s.session_id for s in store.load_open_sessions()] == [session_id]
    store.mark_session_closed(session_id)
    assert store.load_open_sessions() == []


def test_history_store_load_recent_and_reopen_delete(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    first = store.create_session(
        title="Explain startup flow",
        file_name="first.py",
        file_path="",
        code="print('one')",
        model="m1",
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}],
        is_open=False,
    )
    second = store.create_session(
        file_name="second.py",
        file_path="",
        code="print('two')",
        model="m2",
        messages=[{"role": "system", "content": "sys"}, {"role": "assistant", "content": "latest preview"}],
        is_open=False,
    )
    recent = store.load_recent_sessions(limit=10)
    ids = [row.session_id for row in recent]
    assert ids == [second, first]
    assert recent[1].title == "Explain startup flow"
    assert recent[0].preview == "latest preview"
    store.reopen_session(first)
    assert [row.session_id for row in store.load_open_sessions()] == [first]
    store.delete_session(second)
    assert store.get_session(second) is None


def test_history_store_updates_session_titles(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    session_id = store.create_session(
        file_name="demo.py",
        file_path="/tmp/demo.py",
        code="print('hi')",
        model="qwen",
        messages=[{"role": "system", "content": "sys"}],
    )
    store.update_session_title(session_id, "Renderer Jitter Fix")
    session = store.get_session(session_id)
    recent = store.load_recent_sessions(limit=5)
    assert session is not None
    assert session.title == "Renderer Jitter Fix"
    assert recent[0].title == "Renderer Jitter Fix"


def test_history_store_ignores_and_prunes_blank_general_chats(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    blank = store.create_session(
        file_name="New Chat",
        file_path="",
        code="",
        model="",
        messages=[{"role": "system", "content": "sys"}],
        is_open=True,
    )
    pinned = store.create_session(
        file_name="EngineConfig.java",
        file_path="/tmp/EngineConfig.java",
        code="class EngineConfig {}",
        model="",
        messages=[{"role": "system", "content": "sys"}],
        is_open=True,
    )

    assert [row.session_id for row in store.load_open_sessions()] == [pinned]
    assert [row.session_id for row in store.load_recent_sessions(limit=10)] == [pinned]
    assert store.delete_blank_sessions() == 1
    assert store.get_session(blank) is None
    assert store.get_session(pinned) is not None


def test_history_store_retention_prunes_closed_only(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    old_closed = store.create_session(
        file_name="old.py",
        file_path="",
        code="x",
        model="",
        messages=[{"role": "system", "content": "sys"}],
        is_open=False,
    )
    open_session = store.create_session(
        file_name="open.py",
        file_path="",
        code="y",
        model="",
        messages=[{"role": "system", "content": "sys"}],
        is_open=True,
    )
    newest_closed = store.create_session(
        file_name="new.py",
        file_path="",
        code="z",
        model="",
        messages=[{"role": "system", "content": "sys"}],
        is_open=False,
    )

    store._conn.execute(
        "UPDATE sessions SET updated_at = '2000-01-01T00:00:00+00:00', created_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
        (old_closed,),
    )
    store._conn.commit()

    assert store.delete_closed_sessions_older_than(30) == 1
    assert store.get_session(old_closed) is None
    assert store.get_session(open_session) is not None

    assert store.cap_total_sessions(1) == 1
    assert store.get_session(newest_closed) is None
    assert store.get_session(open_session) is not None
