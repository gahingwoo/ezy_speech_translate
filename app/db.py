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
import re
from threading import Lock

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────
_db_path: str = ""
_lock = Lock()
_enabled = False

DEFAULT_ROOM_ID = "main"

# A language code as the pages send it: "zh", "zh-tw", "yue"
_LANG = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$")

# A line is known by its room and its number in that room. The number alone
# was the key until 4.1.19, and each room counts from 0, so a second room's
# lines replaced the first room's in this table, silently.
#
# `at` is when the line was said, date and time, which is what a service's
# transcript is gathered by. `cleared` marks lines taken off the live screen:
# they stay here, for the transcript, until a service is deleted.
_TRANSLATIONS = """
CREATE TABLE IF NOT EXISTS translations (
    room_id          TEXT    NOT NULL DEFAULT 'main',
    id               INTEGER NOT NULL,
    ts               TEXT    NOT NULL,
    at               TEXT,
    cleared          INTEGER NOT NULL DEFAULT 0,
    original         TEXT    NOT NULL,
    corrected        TEXT    NOT NULL,
    translated       TEXT,
    is_corrected     INTEGER DEFAULT 0,
    source_language  TEXT,
    confidence       REAL,
    bible_refs       TEXT,
    raw_json         TEXT    NOT NULL,
    PRIMARY KEY (room_id, id)
)
"""

_DDL = """
CREATE INDEX IF NOT EXISTS idx_room_at ON translations(room_id, at);

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
    """Bring an older translations table to the current shape: keyed by room
    and number, with `at` and `cleared`. The rows are copied as they are; an
    old row has no `at`, so it is not part of any service's transcript."""
    cols = {r[1]: r[5] for r in conn.execute("PRAGMA table_info(translations)").fetchall()}
    if not cols:
        return
    if cols.get("room_id") and cols.get("id") and "cleared" in cols:
        return                                  # already current
    room_expr = "room_id" if "room_id" in cols else "'main'"
    # All of it or none: a failure half way must not leave the lines in a
    # table the server no longer reads.
    level, conn.isolation_level = conn.isolation_level, None
    conn.execute("BEGIN IMMEDIATE")
    try:
        _rebuild_translations(conn, room_expr)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.isolation_level = level
    logger.info("Migrated translations table: keyed by room and number")


def _rebuild_translations(conn: sqlite3.Connection, room_expr: str) -> None:
    conn.execute("ALTER TABLE translations RENAME TO translations_old")
    conn.execute(_TRANSLATIONS)
    conn.execute(f"""
        INSERT OR IGNORE INTO translations
            (room_id, id, ts, at, cleared, original, corrected, translated,
             is_corrected, source_language, confidence, bible_refs, raw_json)
        SELECT {room_expr}, id, ts, NULL, 0, original, corrected, translated,
               is_corrected, source_language, confidence, bible_refs, raw_json
        FROM translations_old
    """)  # nosec B608 - room_expr is one of two literals above
    conn.execute("DROP TABLE translations_old")
    for old in ("idx_ts", "idx_id", "idx_room_id"):
        conn.execute(f"DROP INDEX IF EXISTS {old}")  # nosec B608 - fixed names


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
        _migrate_schema(conn)
        conn.execute(_TRANSLATIONS)
        conn.executescript(_DDL)
        # What has been done once to this database, so it is not done again
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
    logger.info("Database initialised: %s", db_path)


def load_all() -> list:
    """The lines still on the live screens, every room, oldest first."""
    if not _enabled or not _db_path:
        return []
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT raw_json, room_id FROM translations WHERE cleared = 0 "
                "ORDER BY room_id, id"
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
        logger.info("Loaded %d translations from DB", len(items))
        return items
    except Exception as exc:
        logger.warning("DB load_all error: %s", exc)
        return []


def next_id(room_id: str) -> int:
    """The number a room's next line takes: after every line the room has
    kept, cleared from the screen or not, so a new one never replaces one."""
    if not _enabled or not _db_path:
        return 0
    try:
        with _get_conn() as conn:
            row = conn.execute("SELECT MAX(id) FROM translations WHERE room_id = ?",
                               (room_id,)).fetchone()
        return (row[0] + 1) if row and row[0] is not None else 0
    except Exception as exc:
        logger.warning("DB next_id error: %s", exc)
        return 0


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
                        (room_id, id, ts, at, cleared, original, corrected,
                         translated, is_corrected, source_language, confidence,
                         bible_refs, raw_json)
                    VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.get("room_id") or DEFAULT_ROOM_ID,
                        item.get("id"),
                        item.get("timestamp", ""),
                        item.get("at"),
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


def update_correction(room_id: str, item_id: int, corrected: str, is_corrected: bool,
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
                    WHERE room_id = ? AND id = ?
                    """,
                    (
                        corrected,
                        1 if is_corrected else 0,
                        json.dumps(bible_refs, ensure_ascii=False)
                        if bible_refs else None,
                        json.dumps(full_item, ensure_ascii=False)
                        if full_item else None,
                        room_id,
                        item_id,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("DB update_correction error: %s", exc)


def update_translated(room_id: str, item_id: int, translated: str, lang: str) -> None:
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
                    WHERE room_id = ? AND id = ?
                    """,
                    (translated, translated, lang, room_id, item_id),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("DB update_translated error: %s", exc)


def save_line_translation(room_id: str, item_id: int, lang: str,
                          source: str, text: str) -> None:
    """Keep one language's translation on its line, with the wording it was
    made from, so the transcript does not translate it again (and knows to,
    if the line has been corrected since)."""
    if not _enabled or not _db_path or not _LANG.match(lang or ""):
        return
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute(
                    # The language is checked against _LANG above; the JSON
                    # path cannot be bound as a parameter.
                    f"""
                    UPDATE translations
                    SET raw_json = json_set(raw_json, '$.translations."{lang}"',
                                            json_object('source', ?, 'text', ?))
                    WHERE room_id = ? AND id = ?
                    """,  # nosec B608
                    (source, text, room_id, item_id),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("DB save_line_translation error: %s", exc)


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
                        # Only "?"s; the ids are bound (bandit B608)
                        f"DELETE FROM translations WHERE id IN ({placeholders})",  # nosec B608
                        safe_ids,
                    )
                else:
                    conn.execute(
                        # As above (bandit B608)
                        f"DELETE FROM translations WHERE room_id = ? AND id IN ({placeholders})",  # nosec B608
                        [room_id, *safe_ids],
                    )
                conn.commit()
        except Exception as exc:
            logger.warning("DB delete_ids error: %s", exc)


def clear_live(room_id: str) -> None:
    """Take a room's lines off the live screens. They are kept for the
    transcript of the service they were said in."""
    if not _enabled or not _db_path:
        return
    with _lock:
        try:
            with _get_conn() as conn:
                conn.execute("UPDATE translations SET cleared = 1 WHERE room_id = ?", (room_id,))
                conn.commit()
        except Exception as exc:
            logger.warning("DB clear_live error: %s", exc)


# ── Services: what was said in a room on a day ───────────────────────────────

def services(limit: int = 200) -> list:
    """Each room and day lines were said on, newest first, with how many and
    from when to when."""
    if not _enabled or not _db_path:
        return []
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT room_id, substr(at, 1, 10) AS day, COUNT(*), MIN(at), MAX(at)
                FROM translations
                WHERE at IS NOT NULL
                GROUP BY room_id, day
                ORDER BY day DESC, room_id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [{"room_id": r[0], "date": r[1], "lines": r[2], "first": r[3], "last": r[4]}
                for r in rows]
    except Exception as exc:
        logger.warning("DB services error: %s", exc)
        return []


def service_lines(room_id: str, day: str) -> list:
    """A service's lines, in the order they were said."""
    if not _enabled or not _db_path:
        return []
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                # `at` is ISO, "2026-10-18T09:31:05", so a day is a range of it
                "SELECT raw_json FROM translations WHERE room_id = ? AND at >= ? AND at < ? "
                "ORDER BY at, id",
                (room_id, day + "T", day + "U"),
            ).fetchall()
        out = []
        for (raw,) in rows:
            try:
                out.append(json.loads(raw))
            except ValueError:
                pass
        return out
    except Exception as exc:
        logger.warning("DB service_lines error: %s", exc)
        return []


def delete_service(room_id: str, day: str) -> int:
    """Delete a service's lines for good, live or cleared. Returns how many."""
    if not _enabled or not _db_path:
        return 0
    with _lock:
        try:
            with _get_conn() as conn:
                cur = conn.execute(
                    "DELETE FROM translations WHERE room_id = ? AND at >= ? AND at < ?",
                    (room_id, day + "T", day + "U"))
                conn.commit()
                return cur.rowcount
        except Exception as exc:
            logger.warning("DB delete_service error: %s", exc)
            return 0


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
                    # Columns from the allowed set; values bound (bandit B608)
                    f"UPDATE glossary SET {', '.join(sets)} WHERE id = ?", vals  # nosec B608
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


def seed_default_glossary(path: str) -> int:
    """The default glossary (app/data/default_glossary.json), added once to a
    database: a term the church already has for a language is left as it is,
    and once added, an entry deleted or changed in the console stays so.
    Returns how many entries were added."""
    if not _enabled or not _db_path or not os.path.exists(path):
        return 0
    import json
    from datetime import datetime as _dt
    with _lock:
        try:
            with _get_conn() as conn:
                if conn.execute("SELECT 1 FROM meta WHERE key = 'default_glossary'").fetchone():
                    return 0
                have = {(r[0].lower(), r[1]) for r in
                        conn.execute("SELECT source_term, target_lang FROM glossary").fetchall()}
                with open(path, encoding='utf-8') as f:
                    entries = json.load(f).get('entries', [])
                added = 0
                now = _dt.utcnow().isoformat()
                for e in entries:
                    term = e.get('source_term', '').strip()
                    for lang, translation in e.items():
                        if lang == 'source_term' or not term or not translation:
                            continue
                        if (term.lower(), lang) in have:
                            continue
                        conn.execute(
                            "INSERT INTO glossary (room_id, source_term, target_lang, translation,"
                            " case_sensitive, enabled, created_by, created_at)"
                            " VALUES (NULL, ?, ?, ?, 0, 1, 'ezyspeech', ?)",
                            (term, lang, translation, now))
                        added += 1
                conn.execute("INSERT INTO meta (key, value) VALUES ('default_glossary', ?)", (now,))
                conn.commit()
                return added
        except Exception as exc:
            logger.warning("DB seed_default_glossary error: %s", exc)
            return 0
