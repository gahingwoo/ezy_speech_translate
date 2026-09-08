"""Recognise scripture that was quoted rather than cited.

The reference detector next door reads "John 3:16". This reads the words —
"for God so loved the world" — which is how a preacher usually reaches for a
verse. A sermon quotes far more often than it cites.

The rule the design works to is that a wrong verse in a service is worse than
no verse, so this never answers with a bare yes. Every match comes back with
how sure it is, and the caller decides:

    reference  the reference was spoken, so the detector already has it
    wording    the words match closely enough to show in place of a translation
    offer      close, but not close enough to substitute — offer it instead
    (none)     below that, say nothing

Nothing here touches the network. The index is built by
tools/bible/build_index.py and committed.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading

_log = logging.getLogger(__name__)

_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bible",
                           "web_index.json")
_BOOKS_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "data",
                           "bible_books.json")

_WORD = re.compile(r"[a-z']+")

# ── the confidence lines ─────────────────────────────────────────────────
# A run is the longest stretch of words said in the same order as the verse.
# It is the honest signal: a paraphrase shares plenty of words with a verse but
# almost never eight of them in a row, and a bag of words alone will happily
# match "the Lord is my shepherd" to half the Psalms.
_SUBSTITUTE_RUN = 8          # words in a row, to show the verse in its place
_SUBSTITUTE_COVERAGE = 0.55  # and this much of the verse actually said
_OFFER_RUN = 5               # words in a row, to offer it quietly
_OFFER_COVERAGE = 0.30

# Below this a sentence is too short to be a quotation of anything.
_MIN_WORDS = 6

# How many verses get the expensive word-order test. Everything a lookup turns
# up is measured cheaply first, so this only ever caps the shortlist.
_MAX_CANDIDATES = 40

_lock = threading.Lock()
_index = None
_books = None


def _load():
    """Read the index once, on the first match rather than at import.

    It is six megabytes; a deployment that never quotes scripture should not
    pay for it, and a server that fails to start because a data file moved is
    worse than one that quietly does not match."""
    global _index, _books
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        try:
            with open(_INDEX_PATH, encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, ValueError) as err:
            _log.warning("Scripture matcher disabled: %s", err)
            _index = {"verses": [], "postings": {}}
            return _index

        verses = []
        for entry in raw.get("verses", []):
            book, chapter, verse, words = entry.split(" ", 3)
            verses.append((int(book), int(chapter), int(verse), words.split(" ")))
        _index = {"verses": verses, "postings": raw.get("postings", {})}

        try:
            with open(_BOOKS_PATH, encoding="utf-8") as handle:
                _books = {b["id"]: b["name"] for b in json.load(handle)}
        except (OSError, ValueError, KeyError):
            _books = {}
        _log.info("Scripture matcher ready: %d verses", len(verses))
    return _index


def _words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _longest_run(said: list[str], verse: list[str]) -> int:
    """The longest stretch of words the two have in common, in order.

    The usual dynamic program, kept to two rows because the full table for a
    long reading is a megabyte of integers to answer one question."""
    if not said or not verse:
        return 0
    previous = [0] * (len(verse) + 1)
    best = 0
    for i in range(1, len(said) + 1):
        current = [0] * (len(verse) + 1)
        word = said[i - 1]
        for j in range(1, len(verse) + 1):
            if word == verse[j - 1]:
                current[j] = previous[j - 1] + 1
                if current[j] > best:
                    best = current[j]
        previous = current
    return best


def match(text: str, limit: int = 3) -> list[dict]:
    """Verses the given sentence appears to be quoting, best first.

    Returns records shaped like the reference detector's, with two fields
    added: `match` says how it was found and `score` how sure that is."""
    index = _load()
    if not index["verses"]:
        return []

    said = _words(text)
    if len(said) < _MIN_WORDS:
        return []
    said_set = set(said)

    # Which verses share a rare word with what was said.
    hits: dict[int, int] = {}
    postings = index["postings"]
    for word in said_set:
        for idx in postings.get(word, ()):
            hits[idx] = hits.get(idx, 0) + 1
    if not hits:
        return []

    # Ranking by how many rare words a verse shares would drop the verse whose
    # only distinctive word is a fairly ordinary one — "bless" is the whole of
    # what marks Numbers 6:24 — behind hundreds of verses that share the same
    # single word. Every candidate is measured cheaply first, and only the
    # shortlist pays for the word-order test.
    shortlist = []
    for idx in hits:
        words = index["verses"][idx][3]
        verse_set = set(words)
        coverage = len(said_set & verse_set) / len(verse_set)
        if coverage >= _OFFER_COVERAGE:
            shortlist.append((coverage, idx))
    shortlist.sort(key=lambda pair: -pair[0])

    scored = []
    for coverage, idx in shortlist[:_MAX_CANDIDATES]:
        book, chapter, verse, words = index["verses"][idx]
        run = _longest_run(said, words)

        # A short verse can never reach eight words in a row because it does
        # not have eight — "Yahweh bless you, and keep you" is the whole of
        # Numbers 6:24. The bar is the verse's own length where that is
        # shorter, with a floor: below five words nothing is identifiable
        # from wording alone, so nothing short of that is ever substituted.
        needed = min(_SUBSTITUTE_RUN, max(_OFFER_RUN, len(words)))
        if run >= needed and coverage >= _SUBSTITUTE_COVERAGE:
            kind = "wording"
        elif run >= _OFFER_RUN and coverage >= _OFFER_COVERAGE:
            kind = "offer"
        else:
            continue

        # A score to rank by and to show a person if they ask. The run is what
        # decides, so it leads; coverage breaks ties between equal runs.
        score = min(1.0, run / 12.0) * 0.7 + coverage * 0.3
        scored.append({
            "book_id": book,
            "book": (_books or {}).get(book, str(book)),
            "chapter": chapter,
            "verse_start": verse,
            "verse_end": verse,
            "display": "%s %d:%d" % ((_books or {}).get(book, str(book)), chapter, verse),
            "match": kind,
            "score": round(score, 3),
            "run": run,
        })

    scored.sort(key=lambda r: -r["score"])
    return _merge_adjacent(scored)[:limit]


def _merge_adjacent(rows: list[dict]) -> list[dict]:
    """A reading of three verses matches as three verses; it is one passage.

    Only neighbours in the same chapter merge, and only when they were found
    the same way. A verse that merely borrows a clause from its neighbour —
    John 3:15 and 3:16 share most of one — would otherwise be pulled into the
    quotation and inherit a confidence it never earned."""
    if not rows:
        return []
    ordered = sorted(rows, key=lambda r: (r["book_id"], r["chapter"], r["verse_start"]))
    merged = [dict(ordered[0])]
    for row in ordered[1:]:
        last = merged[-1]
        if (row["book_id"] == last["book_id"]
                and row["chapter"] == last["chapter"]
                and row["match"] == last["match"]
                and row["verse_start"] <= last["verse_end"] + 1):
            last["verse_end"] = max(last["verse_end"], row["verse_end"])
            last["score"] = max(last["score"], row["score"])
            last["run"] = max(last["run"], row["run"])
            last["display"] = ("%s %d:%d" % (last["book"], last["chapter"],
                                             last["verse_start"])
                               if last["verse_start"] == last["verse_end"]
                               else "%s %d:%d-%d" % (last["book"], last["chapter"],
                                                     last["verse_start"],
                                                     last["verse_end"]))
        else:
            merged.append(dict(row))
    merged.sort(key=lambda r: -r["score"])
    return merged
