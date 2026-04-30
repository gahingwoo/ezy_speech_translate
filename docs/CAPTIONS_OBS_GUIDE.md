# OBS Captions Overlay — Usage Guide

A transparent caption renderer at `/captions` designed for OBS Browser Source,
streaming overlays, and external display walls. Subscribes to the same
Socket.IO channel as the user app, so every translation appears in real time.

---

## Quick Start

1. Start the user server (default port `1915`).
2. In OBS: **Sources → + → Browser**.
3. Settings:

| Field | Value |
|---|---|
| URL | `http://localhost:1915/captions?mode=both&size=64&pos=bottom` |
| Width | `1920` |
| Height | `1080` |
| Custom CSS | *(leave blank)* |
| Shutdown source when not visible | ☐ off (so it stays connected) |
| Refresh browser when scene becomes active | ☑ on (optional) |

The page background is **transparent** — OBS composites it over your scene.

---

## Why does the page look white in a normal browser?

This is **expected and correct**.

- The HTML uses `background: transparent` on `html`/`body`.
- A normal browser tab has a white window behind transparent content, so it
  shows white.
- OBS Browser Source draws on a transparent surface, so the white goes away
  and only the captions appear.

### Verifying transparency in a normal browser

Append `?bg=000000aa` to see a semi-transparent black backing instead:

```
http://localhost:1915/captions?bg=000000aa&size=48&pos=bottom
```

Or `?bg=ff00ff` for a chroma-key magenta you can key out in OBS:

```
http://localhost:1915/captions?bg=ff00ff
```

---

## Why are no captions showing?

Run through this checklist:

1. **Is anything being transcribed right now?**
   The overlay only displays *new* `new_translation` events plus the last
   `lines=N` items from history. Open the regular user app at `/` in another
   tab — captions there should mirror the overlay.

2. **Is the Socket.IO connection alive?**
   Add `?debug=1` to the URL. A small status badge appears in the top-right:
   `connected` / `disconnected` / `error`.

3. **Are you filtering by language?**
   `?lang=en` only shows entries whose `source_language` starts with `en`.
   Remove the param to show everything.

4. **Are you in `mode=translated` but no translation is set yet?**
   The overlay falls back to original text when translation is missing, so
   this should not happen — but double-check by switching to `?mode=original`.

5. **Browser console errors?**
   Open DevTools (in OBS: right-click source → *Interact*, then
   `Ctrl+Shift+I`) and look for socket errors or 4xx responses.

6. **Authentication / IP allow-list?**
   `/captions` is protected by `check_client_access` like all other user
   routes. If your client IP is not allowed, the page will load but the
   socket will be rejected. Check server logs.

---

## All URL Parameters

| Param | Default | Description |
|---|---|---|
| `mode` | `translated` | `translated` / `original` / `both` (original small + translated big) |
| `lang` | *(any)* | Filter to entries with this `source_language` (e.g. `en`, `zh`) |
| `lines` | `1` | Max number of recent lines kept on screen |
| `size` | `56` | Font size in px |
| `color` | `ffffff` | Text color (6-hex, no `#`) |
| `stroke` | `000000` | Outline color |
| `strokew` | `4` | Outline width in px (0 = no outline) |
| `weight` | `700` | Font weight 100–900 |
| `bg` | `transparent` | `transparent` / `RRGGBB` / `RRGGBBAA` (with alpha) |
| `align` | `center` | `left` / `center` / `right` |
| `pos` | `bottom` | `top` / `center` / `bottom` |
| `pad` | `40` | Edge padding in px |
| `fade` | `0` | Per-line fade-out delay in ms (`0` = never) |
| `maxchars` | *(none)* | Truncate single line at N chars (adds `…`) |
| `shadow` | `1` | Drop-shadow on text (`0` to disable) |
| `font` | *system sans* | CSS `font-family` (safe-character allowlist) |
| `debug` | `0` | Show connection status indicator top-right |

---

## Recommended Presets

### Bottom bilingual subtitles (training / lectures)
```
?mode=both&size=56&pos=bottom
```

### Top yellow translation only (gaming / live talks)
```
?mode=translated&color=ffff00&strokew=6&pos=top&size=64
```

### Semi-transparent backing (busy backgrounds)
```
?bg=000000aa&pad=24&size=48
```

### Bottom-left small with auto-fade (chat / talkshow)
```
?align=left&pos=bottom&size=36&lines=3&fade=8000
```

### Chroma-key (lime green for OBS color key filter)
```
?bg=00ff00
```

### Single-line large translated only
```
?mode=translated&size=80&lines=1&pos=center
```

---

## Implementation Notes

- File: [app/templates/captions.html](app/templates/captions.html)
- Route: [app/user/server.py](app/user/server.py) → `/captions`
- Reuses existing Socket.IO events: `new_translation`,
  `translation_corrected`, `history_cleared`.
- Initial backfill via `GET /api/history?limit=N` so OBS doesn't show a
  blank overlay if started mid-session.
- All caption text is HTML-escaped; the `font` param is restricted to a
  safe character allowlist to prevent CSS injection.
- Connection identifies itself with `type=caption` in the Socket.IO query
  string, distinct from `user` and `admin` clients.

---

## Known Limitations

- The overlay does **not** transmit audio/transcriptions back to the server
  — it is read-only. Use the regular `/` user app or admin app for that.
- `lang` filter only matches `source_language`. There is no current way to
  filter by *target* translation language (since each connection is
  broadcast-style and every client sees the same translations).
- The `?api/history?limit=N` backfill returns the most recent N items in
  insertion order; no per-language filtering is applied to the backfill
  (only to live updates).
- If you need a private overlay (different content per scene), run a second
  server instance on a separate port with its own translation state.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| White background in regular browser | Browser default behind transparent page | Normal — OBS will be transparent. Use `?bg=000000aa` to verify in browser. |
| No captions appearing | No live translations / wrong filter / socket blocked | Add `?debug=1`, check user app at `/` is producing output. |
| Captions appear but vanish too fast | `fade` set too low | Increase `?fade=15000` or omit it. |
| Text overflows / wraps weirdly | Width too small or `size` too big | Reduce `size`, increase OBS source width, or set `maxchars`. |
| Background is opaque white in OBS | OBS browser source has its own background | In OBS source properties, **uncheck** "Custom CSS" if it injected `body { background: white }`. |
| Socket reconnect loop | IP not in `check_client_access` allow-list | Check server logs and client config. |

