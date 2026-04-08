from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from config import HISTORY_DB_PATH


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class SessionRecord:
    session_id: int
    file_name: str
    file_path: str
    code: str
    model: str
    is_open: bool
    created_at: str
    updated_at: str


class HistoryStore:
    """Small SQLite-backed store for persisted chat sessions."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or HISTORY_DB_PATH).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL DEFAULT '',
                code TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                is_open INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                seq INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_open_updated
                ON sessions(is_open, updated_at DESC, id DESC);

            CREATE INDEX IF NOT EXISTS idx_messages_session_seq
                ON messages(session_id, seq);
            """
        )
        self._conn.commit()

    def create_session(
        self,
        *,
        file_name: str,
        file_path: str,
        code: str,
        model: str,
        messages: Iterable[dict[str, str]],
        is_open: bool = True,
    ) -> int:
        now = _utcnow()
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (file_name, file_path, code, model, is_open, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (file_name, file_path, code, model, int(is_open), now, now),
        )
        session_id = int(cursor.lastrowid)
        self._insert_messages(cursor, session_id, messages)
        self._conn.commit()
        return session_id

    def _insert_messages(
        self,
        cursor: sqlite3.Cursor,
        session_id: int,
        messages: Iterable[dict[str, str]],
        *,
        start_seq: int = 0,
    ) -> None:
        rows = []
        now = _utcnow()
        seq = start_seq
        for msg in messages:
            rows.append(
                (
                    session_id,
                    msg.get("role", "user"),
                    msg.get("content", ""),
                    seq,
                    now,
                )
            )
            seq += 1
        if rows:
            cursor.executemany(
                """
                INSERT INTO messages (session_id, role, content, seq, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def append_message(self, session_id: int, role: str, content: str) -> None:
        cursor = self._conn.cursor()
        seq_row = cursor.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 AS next_seq FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        next_seq = int(seq_row["next_seq"])
        now = _utcnow()
        cursor.execute(
            """
            INSERT INTO messages (session_id, role, content, seq, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, next_seq, now),
        )
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        self._conn.commit()

    def update_session_model(self, session_id: int, model: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET model = ?, updated_at = ? WHERE id = ?",
            (model, _utcnow(), session_id),
        )
        self._conn.commit()

    def mark_session_closed(self, session_id: int) -> None:
        self._conn.execute(
            "UPDATE sessions SET is_open = 0, updated_at = ? WHERE id = ?",
            (_utcnow(), session_id),
        )
        self._conn.commit()

    def load_messages(self, session_id: int) -> list[dict[str, str]]:
        rows = self._conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY seq ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def load_open_sessions(self) -> list[SessionRecord]:
        rows = self._conn.execute(
            """
            SELECT id, file_name, file_path, code, model, is_open, created_at, updated_at
            FROM sessions
            WHERE is_open = 1
            ORDER BY updated_at ASC, id ASC
            """
        ).fetchall()
        return [
            SessionRecord(
                session_id=int(row["id"]),
                file_name=row["file_name"],
                file_path=row["file_path"],
                code=row["code"],
                model=row["model"],
                is_open=bool(row["is_open"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

