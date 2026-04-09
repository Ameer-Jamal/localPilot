from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from config import HISTORY_DB_PATH


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class SessionRecord:
    session_id: int
    title: str
    file_name: str
    file_path: str
    code: str
    model: str
    is_open: bool
    created_at: str
    updated_at: str


@dataclass(slots=True)
class SessionSummary:
    session_id: int
    title: str
    file_name: str
    file_path: str
    model: str
    is_open: bool
    created_at: str
    updated_at: str
    message_count: int
    preview: str


class HistoryStore:
    """Small SQLite-backed store for persisted chat sessions."""

    _PERSISTED_SESSION_CLAUSE_TEMPLATE = """
        (
            TRIM(COALESCE({session_table}.code, '')) != ''
            OR EXISTS (
                SELECT 1
                FROM messages m_keep
                WHERE m_keep.session_id = {session_table}.id
                  AND m_keep.role != 'system'
                  AND TRIM(COALESCE(m_keep.content, '')) != ''
            )
        )
    """

    @classmethod
    def _persisted_session_clause(cls, session_table: str) -> str:
        return cls._PERSISTED_SESSION_CLAUSE_TEMPLATE.format(session_table=session_table)

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
                title TEXT NOT NULL DEFAULT '',
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
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "title" not in columns:
            self._conn.execute(
                "ALTER TABLE sessions ADD COLUMN title TEXT NOT NULL DEFAULT ''"
            )
        self._conn.execute(
            """
            UPDATE sessions
            SET title = file_name
            WHERE TRIM(title) = '' AND TRIM(file_name) != ''
            """
        )
        self._conn.commit()

    def create_session(
        self,
        *,
        title: str = "",
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
            INSERT INTO sessions (title, file_name, file_path, code, model, is_open, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title.strip() or file_name, file_name, file_path, code, model, int(is_open), now, now),
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

    def update_session_title(self, session_id: int, title: str) -> None:
        cleaned = title.strip()
        if not cleaned:
            return
        self._conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (cleaned, _utcnow(), session_id),
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
            f"""
            SELECT id, title, file_name, file_path, code, model, is_open, created_at, updated_at
            FROM sessions
            WHERE is_open = 1
              AND {self._persisted_session_clause("sessions")}
            ORDER BY updated_at ASC, id ASC
            """
        ).fetchall()
        return [
            SessionRecord(
                session_id=int(row["id"]),
                title=row["title"] or row["file_name"],
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

    def get_session(self, session_id: int) -> SessionRecord | None:
        row = self._conn.execute(
            """
            SELECT id, title, file_name, file_path, code, model, is_open, created_at, updated_at
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return SessionRecord(
            session_id=int(row["id"]),
            title=row["title"] or row["file_name"],
            file_name=row["file_name"],
            file_path=row["file_path"],
            code=row["code"],
            model=row["model"],
            is_open=bool(row["is_open"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def load_recent_sessions(self, *, limit: int = 100) -> list[SessionSummary]:
        rows = self._conn.execute(
            f"""
            SELECT
                s.id,
                s.title,
                s.file_name,
                s.file_path,
                s.model,
                s.is_open,
                s.created_at,
                s.updated_at,
                COUNT(m.id) AS message_count,
                COALESCE((
                    SELECT SUBSTR(TRIM(m2.content), 1, 160)
                    FROM messages m2
                    WHERE m2.session_id = s.id
                      AND m2.role != 'system'
                      AND TRIM(m2.content) != ''
                    ORDER BY m2.seq DESC, m2.id DESC
                    LIMIT 1
                ), '') AS preview
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE {self._persisted_session_clause("s")}
            GROUP BY s.id
            ORDER BY s.updated_at DESC, s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            SessionSummary(
                session_id=int(row["id"]),
                title=row["title"] or row["file_name"],
                file_name=row["file_name"],
                file_path=row["file_path"],
                model=row["model"],
                is_open=bool(row["is_open"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=int(row["message_count"]),
                preview=row["preview"] or "",
            )
            for row in rows
        ]

    def reopen_session(self, session_id: int) -> None:
        self._conn.execute(
            "UPDATE sessions SET is_open = 1, updated_at = ? WHERE id = ?",
            (_utcnow(), session_id),
        )
        self._conn.commit()

    def delete_session(self, session_id: int) -> None:
        self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()

    def clear_all_history(self) -> None:
        self._conn.execute("DELETE FROM sessions")
        self._conn.commit()
        self.vacuum()

    def delete_blank_sessions(self) -> int:
        cursor = self._conn.execute(
            """
            DELETE FROM sessions
            WHERE TRIM(COALESCE(code, '')) = ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM messages m_keep
                  WHERE m_keep.session_id = sessions.id
                    AND m_keep.role != 'system'
                    AND TRIM(COALESCE(m_keep.content, '')) != ''
              )
            """
        )
        self._conn.commit()
        return int(cursor.rowcount)

    def delete_closed_sessions_older_than(self, days: int) -> int:
        if days < 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        cursor = self._conn.execute(
            """
            DELETE FROM sessions
            WHERE is_open = 0 AND updated_at < ?
            """,
            (cutoff,),
        )
        self._conn.commit()
        return int(cursor.rowcount)

    def cap_total_sessions(self, max_sessions: int) -> int:
        if max_sessions <= 0:
            return 0
        total_row = self._conn.execute("SELECT COUNT(*) AS total FROM sessions").fetchone()
        total = int(total_row["total"])
        excess = total - max_sessions
        if excess <= 0:
            return 0
        rows = self._conn.execute(
            """
            SELECT id
            FROM sessions
            WHERE is_open = 0
            ORDER BY updated_at ASC, id ASC
            LIMIT ?
            """,
            (excess,),
        ).fetchall()
        ids = [int(row["id"]) for row in rows]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        cursor = self._conn.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            ids,
        )
        self._conn.commit()
        return int(cursor.rowcount)

    def vacuum(self) -> None:
        self._conn.execute("VACUUM")
        self._conn.commit()
