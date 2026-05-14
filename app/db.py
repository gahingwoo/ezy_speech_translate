"""EzySpeechTranslate — SQLite persistence layer.

Opt-in via config:
  database:
    enabled: true
    path: "data/translations.db"

Thread-safe.  All writes are serialised through a single Lock.
Safe to import when disabled — all operations are no-ops.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from threading import Lock

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────
_db_path: str = ""
_lock = Lock()
_enabled = False

_DDL = """
CREATE TABLE IF NOT EXISTS translations (
    id               INTEGER PRIMARY KEY,
    ts               TEXT    NOT NULL,
    original         TEXT    NOT NULL,
    corrected        TEXT    NOT NULL,
    translated       TEXT,
    is_corrected     INTEGER DEFAULT 0,
    source_language  TEXT,
    confidence       REAL,
    bible_refs       TEXT,
    raw_json         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ts  ON translations(ts);
CREATE INDEX IF NOT EXISTS idx_id  ON translations(id);
"""


# ── Public API ────────────────────────────────────────────────────────────────

def init_db(db_path: str, enabled: bool = True) -> None:
    """Initialise the database.  Call once on server startup."""
    global _db_path, _enabled
    _db_path = db_path
    _enabled = enabled
    if not _enabled:
        logger.info("Database persistence disabled via config")
        return
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with _get_conn() as conn:
        conn.executescript(_DDL)
        conn.commit()
    logger.info("✅ Database initialised: %s", db_path)


def load_all() -> list:
    """Return all persisted translations ordered by id asc."""
    if not _enabled or not _db_path:
        return []
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT raw_json FROM translations ORDER BY id ASC"
            ).fetchall()
        items: list = []
        for (raw,) in rows:
            try:
                items.append(json.loads(raw))
            except Exception:
                pass
        logger.info("✅ Loaded %d translations from DB", len(items))
        return items
    except Exception as exc:
        logger.warning("DB load_all error: %s", exc)
        return []


def persist(item: dict) -> None:
    """Insert or replace a translation record."""
    if not _enabled or not _db_path:
        return
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO translations
                        (id, ts, original, corrected, translated,
                         is_corrected, source_language, confidence,
                         bible_refs, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.get("id"),
                        item.get("timestamp", ""),
                        item.get("original", ""),
                        item.get("corrected", ""),
                        item.get("translated"),
                        1 if item.get("is_corrected") else 0,
                        item.get("source_language", ""),
                        item.get("confidence"),
                        json.dumps(item.get("bible_refs"), ensure_ascii=False)
                        if item.get("bible_refs") else None,
                        json.dumps(item, ensure_ascii=False),
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("DB persist error: %s", exc)


def update_correction(item_id: int, corrected: str, is_corrected: bool,
                       bible_refs=None, full_item: dict | None = None) -> None:
    """Update the corrected text and optionally the full JSON blob."""
    if not _enabled or not _db_path:
        return
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    UPDATE translations
                    SET corrected = ?, is_corrected = ?, bible_refs = ?,
                        raw_json = COALESCE(?, raw_json)
                    WHERE id = ?
                    """,
                    (
                        corrected,
                        1 if is_corrected else 0,
                        json.dumps(bible_refs, ensure_ascii=False)
                        if bible_refs else None,
                        json.dumps(full_item, ensure_ascii=False)
                        if full_item else None,
                        item_id,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("DB update_correction error: %s", exc)


def delete_ids(ids: list) -> None:
    """Delete records by id list."""
    if not _enabled or not _db_path or not ids:
        return
    # Enforce integer type for each ID to prevent type-confusion injection
    try:
        safe_ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        logger.warning("delete_ids: non-integer ID rejected, skipping")
        return
    with _lock:
        try:
            with _get_conn() as conn:
                placeholders = ",".join("?" * len(safe_ids))
                conn.execute(
                    f"DELETE FROM translations WHERE id IN ({placeholders})",
                    safe_ids,
                )
                conn.commit()
        except Exception as exc:
            logger.warning("DB delete_ids error: %s", exc)


def clear_all() -> None:
    """Delete every record."""
    if not _enabled or not _db_path:
        return
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute("DELETE FROM translations")
                conn.commit()
        except Exception as exc:
            logger.warning("DB clear_all error: %s", exc)


def get_stats() -> dict:
    """Return lightweight stats for the analytics endpoint."""
    if not _enabled or not _db_path:
        return {"enabled": False, "count": 0}
    try:
        with _get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM translations"
            ).fetchone()[0]
        return {"enabled": True, "count": count, "path": _db_path}
    except Exception as exc:
        return {"enabled": True, "count": 0, "error": str(exc)}


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(_db_path, check_same_thread=False)
