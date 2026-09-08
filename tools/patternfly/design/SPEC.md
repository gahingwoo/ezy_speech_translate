# EzySpeech — design spec

The live sermon translation app at `ezyspeech.mabc.qzz.io`, redesigned to sit
inside the same shell as `new.mabc.org.nz`. This file is the load-bearing part:
the markup in `markup/` and the rules in `ezyspeech.css` follow from it.

## What this is built on

Not "PatternFly-inspired" — the real thing, from the church site's own build:

- `assets/patternfly/patternfly-site.css` (vendored by `tools/patternfly/build.sh`)
- `assets/site.css` (the house layer)

**Corrected.** The paragraph that stood here listed the church site's
components and said EzySpeech may use no others. That is the wrong list: it is
`mabc-ws/tools/patternfly/build.sh`, and EzySpeech has a vendor script of its
own with a far larger set — Label, Switch, Tabs, Toolbar, DataList, Form,
FormControl, HelperText, Divider, Badge, Alert, Tooltip, EmptyState,
NumberInput, Slider, Drawer and the rest are all in it.

`SPEC-CORRECTIONS.md` says EzySpeech ships the *full* distribution. It does
not, and the difference matters to whoever reads this next: it ships a trimmed
build too, just a much larger trim. ActionList was not in it until this design
asked for it. **Before using a component, check
`tools/patternfly/build.sh`; if it is not there, add it and rebuild** — that is
a one-line change and a rebuild, not a reason to hand-roll anything.

Availability is not a licence. Reach for a component when it is the right one,
not because it exists — and never hand-roll something PatternFly already has.
Anything drawn by hand that PatternFly ships is a bug.

The house layer on top is `shell.css` (ported from the church site:
`.doc-page`, `.with-rail`, `.page-rail`, `.page-head`, `.kv`, `.meta`,
`.section`), plus `ezyspeech.css` and the per-page stylesheets. Those are
existing vocabulary — use them, do not copy them.

## Rules that are not negotiable

1. **Density is PatternFly's.** `site.css` records that enlarging tap targets
   was tried and reverted: "The design system's density is the design, so it is
   left alone." Do not inflate rows, buttons or spacing.
2. **Headings are weight 400.** `page-title` 1.75rem, `card__title-text` and
   `section-title` 1.375rem. Red Hat Display is declared 300–900 for this.
3. **Tokens, never literals.** No hex, no px radii, no hard-coded spacing in
   new CSS. `ezyspeech.css` has no literal colour in it; keep it that way.
4. **One primary action per view.** Blue is the primary action, red is
   destructive, everything else is secondary or plain.
5. **Icons are inline SVG from `@patternfly/react-icons`** on `currentColor`.
   No emoji. The current app uses emoji as icons throughout; that goes.

## The viewer

The app shell as Cockpit runs it: masthead, left sidebar nav, `doc-page`,
jump-links rail. Sidebar has three groups only — This service / Reading /
Elsewhere.

The stream is a `.kv` description list, **stacked** rather than horizontal:

- `dt` — the timestamp, mono, subtle
- `dd` — the translation at 1.5rem, then the English source as `.meta`
- two plain buttons per row: **copy** takes the translation and the English
  together; **read aloud** speaks that one line and turns into a pause while it
  plays, with the line tinted `--pf-t--global--text--color--brand--default`

## The translation delay

There is no streaming translation API. A line arrives in stages, and the layout
carries the wait rather than hiding it:

1. Speaker still talking → interim recognition, greyed, in place.
2. Speaker pauses → English is final; **the translation's space is already
   reserved at the right height**.
3. One API round trip later → the translation fills that space. Nothing on the
   page moves. Measure the real round trip and put it in the docs — under about
   two seconds nobody calls this slow for a sermon.
4. Scripture skips the API entirely (below).

No spinners. A spinner draws attention to the wait; a reserved space does not.

## Scripture

**A verse is a citation, not a translation.** It is looked up in the reader's
own Bible, which is why it is instant and better worded than machine output.
That only holds if the match is right, so every row says how it was matched:

| Case | Treatment |
|---|---|
| Reference was spoken | Show the verse in place of a machine translation, with reference and version |
| Matched by wording only | Show it, labelled `matched by wording` |
| Below the confidence line | **Do not substitute.** Keep the ordinary translation and offer the verse on one quiet line |
| Cited but not read | Show the translated sentence and offer the passage; do not paste a chapter into the stream |

A wrong verse in a service is worse than no verse.

### Long passages

- Up to three verses: shown whole.
- Four or more: three shown, and **the window always contains the verse that
  was actually read** — not simply the first three — with a count of what sits
  above and below it. `Show all N verses` opens a dialog.
- If the whole passage was read, no verse is singled out and the window starts
  at the top.

The dialog follows `.sermon-backdrop` in `site.css` — `pf-v6-c-backdrop`,
`pf-v6-l-bullseye`, `pf-v6-c-modal-box pf-m-lg`, `data-dialog-close` — at a
reading measure rather than the player's 64rem. Its footer reads the whole
passage aloud; the stream never starts a passage on its own.

## Language

**Language is a dialog, not navigation.** Twenty-two languages are not a nav
list, and choosing one is not going somewhere. It works the way Cockpit's
*Display language* does: search field, native names in their own script, a
check on the current one, an explicit **Select** rather than instant-apply.

Two deliberate departures from Cockpit:

- The list is grouped, with the languages this congregation actually picks at
  the top. **That membership must come from real usage data, not a guess** —
  the three in the markup are placeholders.
- Each row carries the English name beside the native one, because someone is
  often setting the phone up for a newcomer and may not read the script. Keep
  it on **one line**; putting it on a second line is what made an earlier
  version stop looking like PatternFly.

**One choice, not two.** The current app has a *Display Language* and a *Target
Language* that look identical and do different things. Here the reading
language sets both, with a `Keep the page in English` escape hatch in Settings.

On a phone the masthead language button steps aside the way `.masthead-give`
already does, and the trigger sits in the sidebar under Reading.

## Two things to fix in the current app

1. **Script mismatch.** The stream renders Traditional (願耶和華使他的臉光照你)
   while the Bible default is `CUNPS` — 新标点和合本, Simplified. A Cantonese
   reader gets both scripts on one page. `CUV` or `CUNP` should be the default
   for 粵語.
2. **Two language selects** that look the same and are not (above).

## Still open

- The measured API round trip. The Latency artboard has `[FILL IN]`.
- Which languages belong in "Chosen most often here".
- Whether 思高聖經 belongs in the same Bible list — it is a Catholic translation
  whose book names and verse numbering do not line up with 和合本, so a reader
  can pick it by accident and get a reference that does not resolve.
- The Cantonese in the mockups is machine-assisted and needs a native speaker.
- The join address and QR on the projection screen are a proposal; the app does
  not do this today.


---

# Corrections applied

`SPEC-CORRECTIONS.md` is in this directory and has been merged into the text
above and into the app. Two notes on it, from checking its claims against the
code:

1. **The component constraint** was wrong here and is corrected above, but not
   for the reason given: this is a trimmed build, not the full distribution.
   ActionList was missing and had to be vendored.

2. **`Current: NLT`** is not in `app/templates/admin.html`. Nothing to remove.

3. **The data bug** — "353 translations in a 53-second session, about 6.7 rows
   a second, interim results being persisted" — is a misreading. The database
   holds 353 rows and 351 distinct originals, accumulated over every session
   the app has ever run; the 53 seconds is the *current* session, whose
   counter resets on restart. Nothing is being written 6.7 times a second.

   The design conclusion still holds, for a different reason: a lifetime row
   count sitting under a heading that says **This service** is not a data bug,
   it is a card telling two different stories in one column. That is what the
   four-row rewrite fixes.
