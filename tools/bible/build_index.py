#!/usr/bin/env python3
"""Build the index the wording matcher searches.

A speaker quotes scripture far more often than they cite it: "for God so loved
the world" arrives with no reference attached, and the reference detector —
which only reads "John 3:16" — sees nothing. This builds the index that lets
the app recognise the words themselves.

    python3 tools/bible/build_index.py

Source: the World English Bible, public domain, as one file from bolls.life —
the same service the app already looks verses up in. Output is committed, so a
normal checkout needs no build step and the app never reaches the network to
match.

    app/data/bible/web_index.json

The index is deliberately small. Indexing every word of 37,000 verses would be
a hundred megabytes to hold a lookup that is wrong most of the time: common
words match everything. Only each verse's rarest words are indexed, which is
what actually identifies it — "lovingkindness" finds a psalm, "the" does not.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "app/data/bible/web_index.json"
SOURCE = "https://bolls.life/static/translations/WEB.json"

# How many of a verse's rarest words identify it. Three is enough to find any
# verse that was quoted at length and few enough that the index stays small;
# a verse with fewer distinct words than this contributes all of them.
SIGNATURE_WORDS = 4

# A word this common carries no information about which verse was said, so it
# never earns a place in a signature however rare it is inside its own verse.
MAX_DOC_FREQUENCY = 400

_WORD = re.compile(r"[a-z']+")
_TAG = re.compile(r"<[^>]+>")


def normalise(text: str) -> list[str]:
    """The words of a verse, as the matcher will see them.

    Speech recognition gives no punctuation, no capitals and no verse markup,
    so none of those can be part of the comparison."""
    text = _TAG.sub(" ", text or "").lower()
    return _WORD.findall(text)


def load_source() -> list[dict]:
    local = pathlib.Path("/tmp/WEB.json")
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    print("fetching %s" % SOURCE)
    with urllib.request.urlopen(SOURCE, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    rows = load_source()
    print("%d verses" % len(rows))

    verses = []
    for row in rows:
        words = normalise(row.get("text", ""))
        if not words:
            continue
        verses.append({
            "b": row["book"], "c": row["chapter"], "v": row["verse"],
            "w": words,
        })

    # How many verses each word appears in. A word in a thousand verses tells
    # us nothing; a word in three tells us almost everything.
    frequency = collections.Counter()
    for verse in verses:
        frequency.update(set(verse["w"]))

    postings: dict[str, list[int]] = collections.defaultdict(list)
    for index, verse in enumerate(verses):
        distinct = set(verse["w"])
        rare = sorted(distinct, key=lambda w: (frequency[w], w))
        picked = [w for w in rare if frequency[w] <= MAX_DOC_FREQUENCY][:SIGNATURE_WORDS]
        # A short verse of ordinary words — "Yahweh bless you, and keep you"
        # is the whole of Numbers 6:24 — has nothing under the cap, and an
        # unindexed verse can never be found however plainly it is quoted. It
        # takes its own rarest words instead.
        if not picked:
            picked = rare[:SIGNATURE_WORDS]
        for word in picked:
            postings[word].append(index)

    payload = {
        "translation": "WEB",
        "source": SOURCE,
        # The words are joined back into a string: a list of 37,000 lists costs
        # several times what the text does, both on disk and in memory.
        "verses": ["%d %d %d %s" % (v["b"], v["c"], v["v"], " ".join(v["w"]))
                   for v in verses],
        "postings": {w: idx for w, idx in sorted(postings.items())},
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    size = OUT.stat().st_size
    print("wrote %s (%.1f MB, %d words indexed)"
          % (OUT.relative_to(ROOT), size / 1e6, len(postings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
