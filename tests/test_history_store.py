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
