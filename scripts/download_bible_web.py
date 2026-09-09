#!/usr/bin/env python3
"""
Download the full World English Bible (public domain) and convert it
to the JSON shape expected by app/user/bible_detector.py:

    { "Book Name": { "1": { "1": "verse text", ... }, ... }, ... }

Source: https://github.com/wldeh/bible-api (per-chapter JSON files,
public-domain WEB text). We fetch each chapter and stitch into one
file. Requires network access; on failure the existing bootstrap
web.json is left untouched.

Usage:
    python scripts/download_bible_web.py

Output:
    app/data/bible/web.json   (overwritten on success)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "https://raw.githubusercontent.com/wldeh/bible-api/main/bibles/en-web/books"

# (display name used by bible_detector, slug used by wldeh, chapter count)
BOOKS: list[tuple[str, str, int]] = [
    ("Genesis", "genesis", 50),
    ("Exodus", "exodus", 40),
    ("Leviticus", "leviticus", 27),
    ("Numbers", "numbers", 36),
    ("Deuteronomy", "deuteronomy", 34),
    ("Joshua", "joshua", 24),
    ("Judges", "judges", 21),
    ("Ruth", "ruth", 4),
    ("1 Samuel", "1samuel", 31),
    ("2 Samuel", "2samuel", 24),
    ("1 Kings", "1kings", 22),
    ("2 Kings", "2kings", 25),
    ("1 Chronicles", "1chronicles", 29),
    ("2 Chronicles", "2chronicles", 36),
    ("Ezra", "ezra", 10),
    ("Nehemiah", "nehemiah", 13),
    ("Esther", "esther", 10),
    ("Job", "job", 42),
    ("Psalms", "psalms", 150),
    ("Proverbs", "proverbs", 31),
    ("Ecclesiastes", "ecclesiastes", 12),
    ("Song of Solomon", "songofsolomon", 8),
    ("Isaiah", "isaiah", 66),
    ("Jeremiah", "jeremiah", 52),
    ("Lamentations", "lamentations", 5),
    ("Ezekiel", "ezekiel", 48),
    ("Daniel", "daniel", 12),
    ("Hosea", "hosea", 14),
    ("Joel", "joel", 3),
    ("Amos", "amos", 9),
    ("Obadiah", "obadiah", 1),
    ("Jonah", "jonah", 4),
    ("Micah", "micah", 7),
    ("Nahum", "nahum", 3),
    ("Habakkuk", "habakkuk", 3),
    ("Zephaniah", "zephaniah", 3),
    ("Haggai", "haggai", 2),
    ("Zechariah", "zechariah", 14),
    ("Malachi", "malachi", 4),
    ("Matthew", "matthew", 28),
    ("Mark", "mark", 16),
    ("Luke", "luke", 24),
    ("John", "john", 21),
    ("Acts", "acts", 28),
    ("Romans", "romans", 16),
    ("1 Corinthians", "1corinthians", 16),
    ("2 Corinthians", "2corinthians", 13),
    ("Galatians", "galatians", 6),
    ("Ephesians", "ephesians", 6),
    ("Philippians", "philippians", 4),
    ("Colossians", "colossians", 4),
    ("1 Thessalonians", "1thessalonians", 5),
    ("2 Thessalonians", "2thessalonians", 3),
    ("1 Timothy", "1timothy", 6),
    ("2 Timothy", "2timothy", 4),
    ("Titus", "titus", 3),
    ("Philemon", "philemon", 1),
    ("Hebrews", "hebrews", 13),
    ("James", "james", 5),
    ("1 Peter", "1peter", 5),
    ("2 Peter", "2peter", 3),
    ("1 John", "1john", 5),
    ("2 John", "2john", 1),
    ("3 John", "3john", 1),
    ("Jude", "jude", 1),
    ("Revelation", "revelation", 22),
]

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "data", "bible", "web.json",
)


def fetch_chapter(slug: str, chap: int, retries: int = 3) -> list[dict]:
    url = f"{BASE}/{slug}/chapters/{chap}.json"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("data", [])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_err = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def main() -> int:
    out: dict[str, dict[str, dict[str, str]]] = {}
    total_chapters = sum(c for _, _, c in BOOKS)
    done = 0
    print(f"Downloading WEB Bible: {len(BOOKS)} books, {total_chapters} chapters")
    for display, slug, n_chap in BOOKS:
        book_obj: dict[str, dict[str, str]] = {}
        for c in range(1, n_chap + 1):
            done += 1
            verses = fetch_chapter(slug, c)
            ch_obj: dict[str, str] = {}
            for v in verses:
                vn = str(v.get("verse", "")).strip()
                txt = (v.get("text") or "").strip()
                if vn and txt:
                    ch_obj[vn] = txt
            if ch_obj:
                book_obj[str(c)] = ch_obj
            if done % 25 == 0 or done == total_chapters:
                pct = (done * 100) // total_chapters
                print(f"  [{pct:3d}%] {done}/{total_chapters} chapters")
        out[display] = book_obj

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    total_verses = sum(
        len(verses) for book in out.values() for verses in book.values()
    )
    print(f"Wrote {OUT_PATH}: {len(out)} books, {total_verses} verses")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
