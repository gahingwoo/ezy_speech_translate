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

DEFAULT_ROOM_ID = "main"

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
    raw_json         TEXT    NOT NULL,
    room_id          TEXT    NOT NULL DEFAULT 'main'
);
CREATE INDEX IF NOT EXISTS idx_ts        ON translations(ts);
CREATE INDEX IF NOT EXISTS idx_id        ON translations(id);
CREATE INDEX IF NOT EXISTS idx_room_id   ON translations(room_id);

-- Multi-room registry (admin-created rooms)
CREATE TABLE IF NOT EXISTS rooms (
    room_id      TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_by   TEXT,
    created_at   TEXT NOT NULL,
    is_active    INTEGER DEFAULT 1
);

-- Glossary: global (room_id IS NULL) or per-room overrides
-- target_lang='*' means applies to all target languages (replace source-side only)
CREATE TABLE IF NOT EXISTS glossary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id         TEXT,
    source_term     TEXT NOT NULL,
    target_lang     TEXT NOT NULL,
    translation     TEXT NOT NULL,
    case_sensitive  INTEGER DEFAULT 0,
    enabled         INTEGER DEFAULT 1,
    created_by      TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_glossary_lookup ON glossary(room_id, target_lang, enabled);
"""


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Add missing columns to existing tables (for upgrades from older versions)."""
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(translations)").fetchall()]
        if "room_id" not in cols:
            conn.execute(
                "ALTER TABLE translations ADD COLUMN room_id TEXT NOT NULL DEFAULT 'main'"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_room_id ON translations(room_id)")
            logger.info("✅ Migrated translations table: added room_id column")
    except Exception as exc:
        logger.warning("Schema migration error: %s", exc)


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
        # 1) Ensure base tables exist (won't add new columns to existing tables)
        conn.execute("""
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
                raw_json         TEXT    NOT NULL,
                room_id          TEXT    NOT NULL DEFAULT 'main'
            )
        """)
        # 2) Migrate existing tables to add any missing columns
        _migrate_schema(conn)
        # 3) Now safe to create indexes and the rest of the schema
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
                "SELECT raw_json, room_id FROM translations ORDER BY id ASC"
            ).fetchall()
        items: list = []
        for raw, room_id in rows:
            try:
                obj = json.loads(raw)
                # Ensure room_id is present on the dict (may be missing in old rows)
                if not obj.get("room_id"):
                    obj["room_id"] = room_id or DEFAULT_ROOM_ID
                items.append(obj)
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
                         bible_refs, raw_json, room_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        item.get("room_id") or DEFAULT_ROOM_ID,
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


def update_translated(item_id: int, translated: str, lang: str) -> None:
    """Cache the translated text and the language it was translated into."""
    if not _enabled or not _db_path:
        return
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    UPDATE translations
                    SET translated = ?,
                        raw_json = json_set(COALESCE(raw_json, '{}'),
                                           '$.translated', ?,
                                           '$.translated_lang', ?)
                    WHERE id = ?
                    """,
                    (translated, translated, lang, item_id),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("DB update_translated error: %s", exc)


def delete_ids(ids: list, room_id: str | None = None) -> None:
    """Delete records by id list, optionally scoped to a specific room."""
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
                if room_id is None:
                    conn.execute(
                        f"DELETE FROM translations WHERE id IN ({placeholders})",
                        safe_ids,
                    )
                else:
                    conn.execute(
                        f"DELETE FROM translations WHERE room_id = ? AND id IN ({placeholders})",
                        [room_id, *safe_ids],
                    )
                conn.commit()
        except Exception as exc:
            logger.warning("DB delete_ids error: %s", exc)


def clear_all(room_id: str | None = None) -> None:
    """Delete every record, optionally scoped to a specific room."""
    if not _enabled or not _db_path:
        return
    with _lock:
        try:
            with _get_conn() as conn:
                if room_id is None:
                    conn.execute("DELETE FROM translations")
                else:
                    conn.execute("DELETE FROM translations WHERE room_id = ?", (room_id,))
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


# ── Rooms ─────────────────────────────────────────────────────────────────────

def list_rooms() -> list:
    """Return all rooms (active and inactive). Always includes the default room."""
    if not _enabled or not _db_path:
        return [{"room_id": DEFAULT_ROOM_ID, "display_name": "Main", "is_active": 1}]
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT room_id, display_name, created_by, created_at, is_active "
                "FROM rooms ORDER BY created_at ASC"
            ).fetchall()
        result = [
            {
                "room_id": r[0], "display_name": r[1], "created_by": r[2],
                "created_at": r[3], "is_active": r[4],
            }
            for r in rows
        ]
        # Ensure default room is always present
        if not any(r["room_id"] == DEFAULT_ROOM_ID for r in result):
            result.insert(0, {
                "room_id": DEFAULT_ROOM_ID, "display_name": "Main",
                "created_by": None, "created_at": "", "is_active": 1,
            })
        return result
    except Exception as exc:
        logger.warning("DB list_rooms error: %s", exc)
        return [{"room_id": DEFAULT_ROOM_ID, "display_name": "Main", "is_active": 1}]


def upsert_room(room_id: str, display_name: str, created_by: str | None = None,
                is_active: bool = True) -> bool:
    """Create or update a room."""
    if not _enabled or not _db_path:
        return False
    from datetime import datetime as _dt
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO rooms (room_id, display_name, created_by, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(room_id) DO UPDATE SET
                        display_name = excluded.display_name,
                        is_active    = excluded.is_active
                    """,
                    (room_id, display_name, created_by,
                     _dt.utcnow().isoformat(), 1 if is_active else 0),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("DB upsert_room error: %s", exc)
            return False


def delete_room(room_id: str) -> bool:
    """Mark a room inactive (kept for history). Default room cannot be deleted.
    Also soft-disables associated glossary entries to avoid orphans."""
    if not _enabled or not _db_path or room_id == DEFAULT_ROOM_ID:
        return False
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute(
                    "UPDATE rooms SET is_active = 0 WHERE room_id = ?", (room_id,)
                )
                conn.execute(
                    "UPDATE glossary SET enabled = 0 WHERE room_id = ?", (room_id,)
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("DB delete_room error: %s", exc)
            return False


# ── Glossary ──────────────────────────────────────────────────────────────────

def glossary_list(room_id: str | None = None, include_global: bool = True) -> list:
    """List glossary entries. If room_id given and include_global, returns global + room.
    If room_id is None, returns only global."""
    if not _enabled or not _db_path:
        return []
    try:
        with _get_conn() as conn:
            if room_id and include_global:
                rows = conn.execute(
                    "SELECT id, room_id, source_term, target_lang, translation, "
                    "case_sensitive, enabled, created_by, created_at "
                    "FROM glossary WHERE room_id IS NULL OR room_id = ? "
                    "ORDER BY room_id IS NULL DESC, source_term ASC",
                    (room_id,),
                ).fetchall()
            elif room_id:
                rows = conn.execute(
                    "SELECT id, room_id, source_term, target_lang, translation, "
                    "case_sensitive, enabled, created_by, created_at "
                    "FROM glossary WHERE room_id = ? ORDER BY source_term ASC",
                    (room_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, room_id, source_term, target_lang, translation, "
                    "case_sensitive, enabled, created_by, created_at "
                    "FROM glossary WHERE room_id IS NULL ORDER BY source_term ASC"
                ).fetchall()
        return [
            {
                "id": r[0], "room_id": r[1], "source_term": r[2],
                "target_lang": r[3], "translation": r[4],
                "case_sensitive": bool(r[5]), "enabled": bool(r[6]),
                "created_by": r[7], "created_at": r[8],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("DB glossary_list error: %s", exc)
        return []


def glossary_add(source_term: str, target_lang: str, translation: str,
                 room_id: str | None = None, case_sensitive: bool = False,
                 enabled: bool = True, created_by: str | None = None) -> int | None:
    """Add a glossary entry. Returns inserted row ID."""
    if not _enabled or not _db_path:
        return None
    from datetime import datetime as _dt
    with _lock:
        try:
            with _get_conn() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO glossary
                        (room_id, source_term, target_lang, translation,
                         case_sensitive, enabled, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (room_id, source_term, target_lang, translation,
                     1 if case_sensitive else 0, 1 if enabled else 0,
                     created_by, _dt.utcnow().isoformat()),
                )
                conn.commit()
                return cur.lastrowid
        except Exception as exc:
            logger.warning("DB glossary_add error: %s", exc)
            return None


def glossary_update(entry_id: int, **fields) -> bool:
    """Update mutable fields of a glossary entry."""
    if not _enabled or not _db_path:
        return False
    allowed = {"source_term", "target_lang", "translation",
               "case_sensitive", "enabled", "room_id"}
    sets = []
    vals = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("case_sensitive", "enabled"):
            v = 1 if v else 0
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return False
    vals.append(int(entry_id))
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute(
                    f"UPDATE glossary SET {', '.join(sets)} WHERE id = ?", vals
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("DB glossary_update error: %s", exc)
            return False


def glossary_delete(entry_id: int) -> bool:
    """Delete a glossary entry by ID."""
    if not _enabled or not _db_path:
        return False
    try:
        eid = int(entry_id)
    except (TypeError, ValueError):
        return False
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute("DELETE FROM glossary WHERE id = ?", (eid,))
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("DB glossary_delete error: %s", exc)
            return False
