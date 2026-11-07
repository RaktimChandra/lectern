"""SQLite persistence.

Each lesson is stored as one JSON document (the full `Lesson` model). Every
step writes the lesson back as soon as it finishes, so a crash, a failed API
call or a closed browser never loses finished work: a retry resumes from the
first unfinished step with everything before it intact.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path

from .models import Lesson, utcnow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    document    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lessons_updated ON lessons(updated_at DESC);
"""


class LessonStore:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._lesson_locks: dict[str, asyncio.Lock] = {}
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def lock_for(self, lesson_id: str) -> asyncio.Lock:
        """One async lock per lesson so edits and pipeline writes never interleave."""
        if lesson_id not in self._lesson_locks:
            self._lesson_locks[lesson_id] = asyncio.Lock()
        return self._lesson_locks[lesson_id]

    def save(self, lesson: Lesson) -> Lesson:
        lesson.updated_at = utcnow()
        payload = lesson.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO lessons (id, title, created_at, updated_at, document)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     title=excluded.title, updated_at=excluded.updated_at, document=excluded.document""",
                (
                    lesson.id,
                    lesson.request.title,
                    lesson.created_at.isoformat(),
                    lesson.updated_at.isoformat(),
                    payload,
                ),
            )
        return lesson

    def get(self, lesson_id: str) -> Lesson | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT document FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        return Lesson.model_validate_json(row[0]) if row else None

    def list(self) -> list[Lesson]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT document FROM lessons ORDER BY updated_at DESC").fetchall()
        return [Lesson.model_validate_json(r[0]) for r in rows]

    def delete(self, lesson_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        self._lesson_locks.pop(lesson_id, None)
        return cur.rowcount > 0
