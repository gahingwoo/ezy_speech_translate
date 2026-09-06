#!/usr/bin/env python3
"""Pull the icons the templates use out of @patternfly/react-icons.

The icons are the one part of PatternFly the CSS bundle does not carry: the
React package holds them as path data, and the pages inline them as SVG. Hand
copying a 2,000 character path is how a glyph ends up subtly wrong, so this
reads them from the published package instead.

    python3 tools/patternfly/extract_icons.py

Needs node and npm. The output, tools/patternfly/icons.json, is committed, so a
normal checkout never runs this. Add a name to NAMES and re-run to grow it.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "tools/patternfly/icons.json"

# Kebab-case names as @patternfly/react-icons files them. A name that does not
# exist in the package stops the run rather than silently leaving a hole.
NAMES = """
angle-down angle-left angle-right bars bell book bullhorn bullseye chart-line
check check-circle cog comments copy database desktop download edit ellipsis-v
exclamation-circle exclamation-triangle expand external-link-alt eye eye-slash
file-export
globe grip-vertical
info-circle key keyboard language lightbulb list lock microphone minus
moon paper-plane pause play plus qrcode redo save search share-alt sign-out-alt
stop sun sync-alt table times trash upload user users volume-up wheelchair
""".split()


def main():
    work = pathlib.Path(tempfile.mkdtemp())
    try:
        subprocess.run(["npm", "pack", "@patternfly/react-icons@6"],
                       cwd=work, check=True, capture_output=True)
        tgz = next(work.glob("patternfly-react-icons-*.tgz"))
        with tarfile.open(tgz) as tf:
            tf.extractall(work, filter="data")
        icons_dir = work / "package/dist/js/icons"
        if not icons_dir.is_dir():
            sys.exit("the package layout changed: %s is not there" % icons_dir)

        out = {}
        for name in sorted(set(NAMES)):
            src = icons_dir / ("%s-icon.js" % name)
            if not src.is_file():
                sys.exit("no icon named %r in @patternfly/react-icons" % name)
            text = src.read_text(encoding="utf-8")
            # The file assigns `icon: {...}` before `rhUiIcon: {...}`; the first
            # is the classic set the rest of the app already uses.
            match = re.search(r"\n\s*icon:\s*(\{.*?\}),\n", text, re.S)
            if not match:
                sys.exit("could not find the icon data in %s" % src.name)
            data = json.loads(match.group(1))
            out[name] = {"w": data["width"], "h": data["height"],
                         "d": data["svgPathData"]}

        OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")
        print("wrote %s (%d icons)" % (OUT.relative_to(ROOT), len(out)))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
