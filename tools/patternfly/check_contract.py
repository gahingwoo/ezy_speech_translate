#!/usr/bin/env python3
"""Prove a rewritten template still gives the JavaScript everything it reaches for.

A page can be rebuilt out of different components and still be correct, but not
if an id, an inline handler or a translation key went missing on the way: those
fail silently, at runtime, in front of whoever is running the event.

    python3 tools/patternfly/check_contract.py <original.html> <rewritten.html>

Exits non-zero and names what is missing.
"""
import re
import sys
import pathlib


def contract(text):
    return {
        "id": set(re.findall(r'\bid="([^"]+)"', text)),
        "handler": set(h for _, h in re.findall(r'\b(on\w+)="([^"]+)"', text)),
        "i18n": set(v for _, v in re.findall(r'(data-i18n[a-z-]*)="([^"]+)"', text)),
        "jinja": set(re.findall(r"\{%[^%]+%\}", text)),
    }


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    old = contract(pathlib.Path(argv[1]).read_text(encoding="utf-8"))
    new = contract(pathlib.Path(argv[2]).read_text(encoding="utf-8"))

    bad = 0
    for kind in ("id", "handler", "i18n", "jinja"):
        missing = sorted(old[kind] - new[kind])
        added = sorted(new[kind] - old[kind])
        print("%-8s kept %d/%d" % (kind, len(old[kind] & new[kind]), len(old[kind])))
        if missing:
            bad += len(missing)
            print("   MISSING (%d): %s" % (len(missing), ", ".join(missing)))
        if added:
            print("   added   (%d): %s" % (len(added), ", ".join(added[:10])))
    print("FAIL" if bad else "OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
