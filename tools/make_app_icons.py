#!/usr/bin/env python3
"""Make the icons a phone uses when the listener page is added to its home
screen (app/static/img/app-icon-*.png), from the church's artwork.

    python3 tools/make_app_icons.py [path/to/lockup.png]

The mark is taken from the lockup (the mark and the name side by side), which
is 313px tall where mark.png is 208px, so the 512px icon is not an enlargement
of a small file. It is set on white, as phones expect an opaque icon (iOS
backs a transparent one with black), at a size that keeps it inside the safe
zone of an Android "maskable" icon, which the launcher may crop to a circle.
Needs Pillow (pip install pillow); run by a developer, never on a server.
"""
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCKUP = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    pathlib.Path.home() / 'mabc-ws/assets/brand/lockup.png'
OUT = ROOT / 'app/static/img'

lockup = Image.open(LOCKUP).convert('RGBA')
# The mark is the artwork left of the first wide transparent gap.
alpha = lockup.getchannel('A')
w, h = lockup.size
cols = [any(alpha.getpixel((x, y)) > 16 for y in range(0, h, 2)) for x in range(w)]
end, gap = 0, 0
for x, used in enumerate(cols):
    if used:
        end, gap = x, 0
    elif end:
        gap += 1
        if gap > h // 6:
            break
mark = lockup.crop((0, 0, end + 1, h))
mark = mark.crop(mark.getchannel('A').getbbox())


def icon(size, fill):
    """The mark at `fill` of the icon's side, centred on white."""
    canvas = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    side = int(size * fill)
    scale = side / max(mark.size)
    m = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    canvas.alpha_composite(m, ((size - m.width) // 2, (size - m.height) // 2))
    return canvas.convert('RGB')


# A maskable icon's safe zone is the centre circle of 80% of its side; a mark
# at 60% of the side fits inside it with room. The plain icons may fill more.
for name, size, fill in (('app-icon-192.png', 192, 0.72), ('app-icon-512.png', 512, 0.72),
                         ('app-icon-maskable-512.png', 512, 0.58),
                         ('apple-touch-icon.png', 180, 0.72)):
    icon(size, fill).save(OUT / name, optimize=True)
    print('wrote', (OUT / name).relative_to(ROOT))
