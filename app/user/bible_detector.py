"""
Bible reference detection and online lookup (PrayerPulse API).

Scans final transcriptions for Bible references like "John 3:16",
"1 Cor 13:4-8", "Romans 8" and fetches verse text from the
PrayerPulse Bible API (https://api.prayerpulse.io — free, no key
required, 27 languages, 150+ translations).

# ──────────────────────────────────────────────────────────────────
# Migration note (bolls.life → PrayerPulse)
# Previous API base: https://bolls.life/get-verses/
# New API base:      https://api.prayerpulse.io/bible/get-verses/
# The batch POST body format is identical.  PrayerPulse adds:
#   ?clean=true   — strips Strong's numbers & HTML annotations
#   GET /bible/get-languages/  — 150+ translations organised by lang
# ──────────────────────────────────────────────────────────────────

Supports two independent translations per lookup:
  source_translation — admin-configured; shown alongside the
                       original-language caption (e.g. "KJV", "NIV")
  target_translation — user-chosen per session; shown in the
                       translated column, auto-matched to the user's
                       display language (e.g. "CUV", "KRV", "RV1960")

Verse text is attached to translation events as `bible_refs` and is
intentionally NOT passed through the translation pipeline.

Thread-safe.  Safe to import when offline — lookups degrade gracefully.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
from collections import OrderedDict
from threading import Lock
from typing import Iterable

import requests as _requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# Book table — loaded from app/static/data/bible_books.json
# Each entry in the JSON: {id, name, aliases: [...]}
# ──────────────────────────────────────────
_BOOKS_JSON_PATH = pathlib.Path(__file__).parent.parent / "static" / "data" / "bible_books.json"

def _load_books() -> tuple[list[tuple[str, list[str]]], dict[str, int]]:
    with open(_BOOKS_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    books = [(entry["name"], entry["aliases"]) for entry in data]
    book_numbers = {entry["name"]: entry["id"] for entry in data}
    return books, book_numbers

_BOOKS, _BOOK_NUMBER = _load_books()

# Build lookup: lower-cased alias -> canonical name
_ALIAS_TO_BOOK: dict[str, str] = {}
for canonical, aliases in _BOOKS:
    _ALIAS_TO_BOOK[canonical.lower()] = canonical
    for a in aliases:
        _ALIAS_TO_BOOK[a.lower()] = canonical

# Build a regex alternation, longest aliases first so "1 Corinthians" wins
# over "1 Co". Escape each alias and allow flexible whitespace (a single
# space in the alias matches one-or-more whitespace in input).
_aliases_sorted = sorted(_ALIAS_TO_BOOK.keys(), key=len, reverse=True)
_book_pattern = "|".join(
    re.escape(a).replace(r"\ ", r"\s+") for a in _aliases_sorted
)

# Spoken-form normalisation: speech recognisers transcribe "John three
# sixteen" as words. This converts a small spoken-number prefix after a
# book name into digits *before* the main regex runs.
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100,
}


def _words_to_int(words: list[str]) -> int | None:
    """Best-effort small-number parse: 'twenty three' -> 23, 'one hundred and fifty' -> 150."""
    total = 0
    current = 0
    saw_any = False
    for w in words:
        wl = w.lower().strip(",.;:")
        if wl == "and":
            continue
        if wl not in _NUMBER_WORDS:
            return None
        saw_any = True
        n = _NUMBER_WORDS[wl]
        if n == 100:
            current = max(current, 1) * 100
        else:
            current += n
    if not saw_any:
        return None
    return total + current


# Match: <book> [<spoken-number-words> | <digits>] [: | chapter] [<verse> [- <verse>]]
# Strategy: find book occurrences, then for each occurrence parse what
# follows manually — much simpler and more accurate than one mega-regex.
_BOOK_FIND_RE = re.compile(rf"\b({_book_pattern})\b", re.IGNORECASE)

# After the book, allow: "3:16", "3:16-18", "chapter 3 verse 16", "3",
# and digits separated by various punctuation.
_NUMBER_RE = re.compile(r"\d+")


def _resolve_book(raw: str) -> str | None:
    """Map a matched book token (any case, any allowed inner whitespace) to canonical."""
    key = re.sub(r"\s+", " ", raw.strip()).lower()
    return _ALIAS_TO_BOOK.get(key)


def _normalize_spoken_numbers(text: str) -> str:
    """Convert spoken numbers immediately after a book name to digits.

    Token-by-token: each number-word becomes its own digit unless it's
    part of an obvious compound ("twenty three" -> 23, "one hundred and
    fifty" -> 150). Stops at the first non-number token. This way
    "John three sixteen" -> "John 3 16" (two numbers, chapter/verse),
    not "John 19" (sum).
    """
    # The smaller "units" set — words that *can* combine with a preceding
    # tens word to form 21-99. Anything outside this set never compounds.
    UNITS = {"one","two","three","four","five","six","seven","eight","nine"}
    TENS = {"twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"}
    # Connector words that can appear between book/chapter/verse without
    # ending the run (e.g. "Romans chapter eight verse twenty eight").
    CONNECTORS = {"chapter","chap","ch","verse","verses","v","vv"}

    def chunk_to_int(toks: list[str]) -> int | None:
        n = _words_to_int(toks)
        return n

    def repl(match: re.Match) -> str:
        book_part = match.group(1)
        tail_text = match.group(2)
        toks = tail_text.split()
        out_nums: list[int] = []
        # Track positions in `out_nums` that should be treated as a
        # range continuation (preceded by "to/through/thru"). When we
        # rebuild the digits string we'll insert "-" before those.
        range_marks: set[int] = set()
        consumed = 0
        i = 0
        while i < len(toks):
            wl = toks[i].lower().strip(",.;:")
            # Skip connector words ("chapter", "verse"...) — they don't
            # become numbers but also shouldn't terminate the run.
            if wl in CONNECTORS:
                i += 1
                consumed = i
                continue
            if wl in {"to", "through", "thru"}:
                # The next number we emit is a range end.
                range_marks.add(len(out_nums))
                i += 1
                consumed = i
                continue
            if wl not in _NUMBER_WORDS and wl != "and":
                break
            if wl == "and":
                # "and" only meaningful inside a multi-word compound
                # (e.g. "one hundred and fifty"). On its own break.
                break
            # Greedy compound: tens + units, or anything containing "hundred"
            j = i
            compound = [toks[j]]
            j += 1
            # Allow trailing units after a tens word
            if wl in TENS and j < len(toks):
                nxt = toks[j].lower().strip(",.;:")
                if nxt in UNITS:
                    compound.append(toks[j]); j += 1
            # Allow "X hundred [and] Y"
            if j < len(toks) and toks[j].lower().strip(",.;:") == "hundred":
                compound.append(toks[j]); j += 1
                if j < len(toks) and toks[j].lower().strip(",.;:") == "and":
                    compound.append(toks[j]); j += 1
                if j < len(toks):
                    nxt = toks[j].lower().strip(",.;:")
                    if nxt in TENS:
                        compound.append(toks[j]); j += 1
                        if j < len(toks):
                            nxt2 = toks[j].lower().strip(",.;:")
                            if nxt2 in UNITS:
                                compound.append(toks[j]); j += 1
                    elif nxt in UNITS:
                        compound.append(toks[j]); j += 1
            n = chunk_to_int(compound)
            if n is None:
                break
            out_nums.append(n)
            consumed = j
            i = j
            if len(out_nums) >= 4:  # cap: book + chapter + verse + verse_end
                break

        if not out_nums:
            return match.group(0)

        rest = " ".join(toks[consumed:])
        # Reassemble digits, marking range-ends with "-" so the main
        # parser recognises them as a verse range.
        parts: list[str] = []
        for idx, n in enumerate(out_nums):
            if idx in range_marks and parts:
                parts.append("-" + str(n))
            else:
                if parts:
                    parts.append(" " + str(n))
                else:
                    parts.append(str(n))
        digits = "".join(parts)
        return f"{book_part} {digits} {rest}".rstrip()

    pattern = re.compile(rf"\b({_book_pattern})\s+([a-zA-Z\s,]+)", re.IGNORECASE)
    return pattern.sub(repl, text)


def detect_refs(text: str) -> list[dict]:
    """Find Bible refs in `text`. Returns list of dicts.

    Each dict: {book, chapter, verse_start, verse_end, display}
    - verse_start/verse_end are None for a whole-chapter reference.
    """
    if not text:
        return []

    normalized = _normalize_spoken_numbers(text)
    refs: list[dict] = []
    seen_keys: set[str] = set()

    for m in _BOOK_FIND_RE.finditer(normalized):
        book = _resolve_book(m.group(1))
        if not book:
            continue
        # Look at the next ~30 chars for chapter/verse
        tail = normalized[m.end(): m.end() + 30]
        # Strip a leading "chapter" word
        tail = re.sub(r"^\s*(chapter|chap|ch)\.?\s*", " ", tail, flags=re.IGNORECASE)
        nums = _NUMBER_RE.findall(tail[:25])
        if not nums:
            # Bare book mention with no numbers — ignore (too noisy)
            continue
        try:
            chapter = int(nums[0])
        except ValueError:
            continue
        if chapter < 1 or chapter > 200:
            continue

        verse_start: int | None = None
        verse_end: int | None = None
        if len(nums) >= 2:
            # Determine if the second number is a verse. Prefer an
            # explicit separator (`:`, `.`, `,`, "verse", "v"), but also
            # accept pure whitespace because spoken-number normalisation
            # produces things like "John 3 16" with no punctuation.
            between = tail.split(nums[0], 1)[1].split(nums[1], 1)[0]
            looks_like_verse = (
                re.search(r"[:\.,]|\b(verse|verses|v|vv)\b", between, re.IGNORECASE)
                or re.fullmatch(r"\s+", between)
            )
            if looks_like_verse:
                try:
                    verse_start = int(nums[1])
                    if verse_start < 1 or verse_start > 200:
                        verse_start = None
                except ValueError:
                    pass
        if verse_start is not None and len(nums) >= 3:
            # Range end: must be preceded by hyphen / "to" / "through"
            after_v1 = tail.split(nums[1], 1)[1].split(nums[2], 1)[0]
            if re.search(r"[-–—]|\b(to|through|thru)\b", after_v1, re.IGNORECASE):
                try:
                    ve = int(nums[2])
                    if 0 < ve <= 200 and ve >= verse_start:
                        verse_end = ve
                except ValueError:
                    pass

        if verse_end is None:
            verse_end = verse_start

        # Display string
        if verse_start is None:
            display = f"{book} {chapter}"
        elif verse_end == verse_start:
            display = f"{book} {chapter}:{verse_start}"
        else:
            display = f"{book} {chapter}:{verse_start}-{verse_end}"

        key = display
        if key in seen_keys:
            continue
        seen_keys.add(key)

        refs.append({
            "book": book,
            "chapter": chapter,
            "verse_start": verse_start,
            "verse_end": verse_end,
            "display": display,
        })

    return refs


# ──────────────────────────────────────────
# Online API config & verse cache
# ──────────────────────────────────────────
# OLD API (bolls.life) — no longer used
# _API_VERSES_URL = "https://bolls.life/get-verses/"

# NEW API — PrayerPulse (free, no key, 27 languages, 150+ translations)
# ?clean=true strips Strong's concordance numbers and HTML footnotes
_API_VERSES_URL   = "https://api.prayerpulse.io/bible/get-verses/?clean=true"
_API_LANGUAGES_URL = "https://api.prayerpulse.io/bible/get-languages/"
_API_TIMEOUT = 8          # seconds per HTTP request
_SOURCE_TRANSLATION = "WEB"
_TARGET_TRANSLATION = ""   # empty → single-translation mode
_MAX_VERSES = 10

# LRU verse cache: (translation, book_num, chapter, verse_num) → text | ""
# Empty string means "verse was requested but does not exist", so we
# never re-request it.
_VERSE_CACHE: OrderedDict[tuple, str] = OrderedDict()
_CACHE_LOCK = Lock()
_MAX_CACHE_ENTRIES = 10_000

# Strong's number and HTML markup pattern (kept as fallback for any translation
# that does not honour ?clean=true, though PrayerPulse strips them server-side)
_MARKUP_RE = re.compile(r"<S>\d+</S>|<[^>]+>")


def _strip_markup(text: str) -> str:
    """Remove Strong's concordance tags and HTML markup from verse text."""
    return _MARKUP_RE.sub("", text).strip()


def init(
    source_translation: str = "WEB",
    target_translation: str = "",
    max_verses: int = 10,
    api_timeout: int = 8,
) -> None:
    """Configure translations and limits used for all subsequent lookups.

    Call once at startup (from server.py).  Thread-safe.

    Args:
        source_translation: bolls.life translation code for the original-
                            language column.  E.g. "WEB", "KJV", "NIV", "NLT".
        target_translation: bolls.life translation code for the translated
                            (e.g. Chinese) column.  Empty string disables.
        max_verses:         Maximum verses to show per reference.
        api_timeout:        HTTP timeout in seconds.
    """
    global _SOURCE_TRANSLATION, _TARGET_TRANSLATION, _MAX_VERSES, _API_TIMEOUT
    _SOURCE_TRANSLATION = (source_translation or "WEB").strip()
    _TARGET_TRANSLATION = (target_translation or "").strip()
    _MAX_VERSES = max(1, int(max_verses))
    _API_TIMEOUT = max(1, int(api_timeout))
    logger.info(
        "📖 Bible detector: source=%s target=%s max_verses=%d",
        _SOURCE_TRANSLATION,
        _TARGET_TRANSLATION or "(none)",
        _MAX_VERSES,
    )


def _cache_get(translation: str, book_num: int, chapter: int, verse: int) -> str | None:
    """Return cached text (possibly ""), or None if not cached."""
    return _VERSE_CACHE.get((translation, book_num, chapter, verse))


def _cache_set(translation: str, book_num: int, chapter: int, verse: int, text: str) -> None:
    """Insert into the LRU cache, evicting the oldest entry when full."""
    key = (translation, book_num, chapter, verse)
    with _CACHE_LOCK:
        if key in _VERSE_CACHE:
            _VERSE_CACHE.move_to_end(key)
        else:
            if len(_VERSE_CACHE) >= _MAX_CACHE_ENTRIES:
                _VERSE_CACHE.popitem(last=False)  # evict oldest
            _VERSE_CACHE[key] = text


def _fetch_batch(requests_list: list[dict]) -> list[list[dict]]:
    """POST /bible/get-verses/?clean=true for a list of {translation, book, chapter, verses}.

    PrayerPulse API: https://api.prayerpulse.io/bible/get-verses/?clean=true
    Request body: [{translation, book, chapter, verses: [...]}, ...]
    Response:     [[{pk, verse, text}, ...], ...]  (parallel list of verse-lists)

    Returns a parallel list of verse-lists.  On any error returns empty
    inner lists so callers always get a list of the same length.
    """
    try:
        resp = _requests.post(
            _API_VERSES_URL,
            json=requests_list,
            timeout=_API_TIMEOUT,
            headers={"User-Agent": "EzySpeechTranslate-BibleLookup/2.0"},
        )
        resp.raise_for_status()
        raw = resp.json()
        if isinstance(raw, list):
            return raw
        return [[] for _ in requests_list]
    except Exception as exc:
        logger.warning("📖 Bible API batch fetch failed: %s", exc)
        return [[] for _ in requests_list]


def _resolve_verses_for_ref(ref: dict) -> list[int]:
    """Return the list of verse numbers to request for a ref."""
    v_start = ref.get("verse_start")
    v_end = ref.get("verse_end") or v_start
    if v_start is None:
        # Whole-chapter reference — fetch first N verses.
        return list(range(1, _MAX_VERSES + 1))
    return list(range(v_start, min(v_end, v_start + _MAX_VERSES - 1) + 1))


def lookup(
    refs: Iterable[dict],
    source_translation: str | None = None,
    target_translation: str | None = None,
) -> list[dict]:
    """Fetch verse text for *refs* and return enriched dicts.

    Args:
        refs:               Iterable of ref dicts from detect_refs().
        source_translation: bolls.life code for the original-language
                            column.  Falls back to the value passed to
                            init() when None.
        target_translation: bolls.life code for the translated column.
                            Falls back to the value passed to init().
                            Pass "" explicitly to disable.

    Each output dict is a copy of the input ref augmented with:
      source: {translation: str, verses: [{n, text}, ...]}
      target: {translation: str, verses: [{n, text}, ...]}  # omitted if empty

    Both translations are fetched in a single HTTP round-trip and cached.
    """
    refs_list = list(refs)
    if not refs_list:
        return []

    src = source_translation if source_translation is not None else _SOURCE_TRANSLATION
    tgt = target_translation if target_translation is not None else _TARGET_TRANSLATION
    translations = [t for t in [src, tgt] if t]
    if not translations:
        return [dict(r) for r in refs_list]

    # ── Step 1: collect which (translation, book, chapter, verse) need fetching ──
    requests_to_make: list[dict] = []   # bolls.life request objects
    req_index_map: list[tuple] = []     # parallel metadata for cache population

    for trans in translations:
        for ref in refs_list:
            book_num = _BOOK_NUMBER.get(ref["book"])
            if not book_num:
                continue
            verse_nums = _resolve_verses_for_ref(ref)
            uncached = [
                v for v in verse_nums
                if _cache_get(trans, book_num, ref["chapter"], v) is None
            ]
            if uncached:
                requests_to_make.append({
                    "translation": trans,
                    "book": book_num,
                    "chapter": ref["chapter"],
                    "verses": uncached,
                })
                req_index_map.append((trans, book_num, ref["chapter"], uncached))

    # ── Step 2: fetch uncached verses in one HTTP call ──
    if requests_to_make:
        results = _fetch_batch(requests_to_make)
        for req_obj, verse_rows, (trans, book_num, chapter, requested) in zip(
            requests_to_make, results, req_index_map
        ):
            returned: dict[int, str] = {}
            for row in verse_rows:
                v_num = row.get("verse")
                if v_num is not None:
                    returned[int(v_num)] = _strip_markup(row.get("text", ""))
            # Cache all requested verses — mark missing ones as "" so they
            # are never re-requested.
            for v_num in requested:
                _cache_set(trans, book_num, chapter, v_num, returned.get(v_num, ""))

    # ── Step 3: build output from cache ──
    out: list[dict] = []
    for ref in refs_list:
        book_num = _BOOK_NUMBER.get(ref["book"])
        verse_nums = _resolve_verses_for_ref(ref)
        enriched = dict(ref)

        for attr, trans in [("source", src), ("target", tgt)]:
            if not trans:
                continue
            verses: list[dict] = []
            if book_num:
                for v_num in verse_nums:
                    text = _cache_get(trans, book_num, ref["chapter"], v_num)
                    if text:  # non-empty → verse exists
                        verses.append({"n": v_num, "text": text})
            enriched[attr] = {"translation": trans, "verses": verses}

        out.append(enriched)

    return out


def detect_and_lookup(text: str) -> list[dict]:
    """Detect Bible references in *text* and return ref metadata only.

    Verse text is intentionally NOT fetched here.  The server broadcasts
    the ref metadata (book/chapter/verse/display) and each client fetches
    verse text in their own preferred translations via /api/bible/lookup.
    """
    return detect_refs(text)


def fetch_languages() -> list[dict]:
    """Fetch the list of available Bible translations grouped by language.

    Returns the raw JSON from PrayerPulse GET /bible/get-languages/.
    Each item: { language: str, translations: [{short_name, full_name, updated}, ...] }
    Returns [] on failure (caller should handle gracefully).
    """
    try:
        resp = _requests.get(
            _API_LANGUAGES_URL,
            timeout=_API_TIMEOUT,
            headers={"User-Agent": "EzySpeechTranslate-BibleLookup/2.0"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("📖 Bible languages fetch failed: %s", exc)
        return []
