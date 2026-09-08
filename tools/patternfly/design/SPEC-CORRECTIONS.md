# Corrections and additions to `tools/patternfly/design/SPEC.md`

Apply these to the SPEC already in the repo. Two of them contradict what is
written there now.

---

## 1. CORRECTION — the component constraint is wrong for this app

The SPEC currently says:

> **Use only the components that vendor script ships.** The list is in
> `tools/patternfly/build.sh` … There is **no** Toolbar, DataList, Label,
> Switch, Badge, MenuToggle, ToggleGroup, Slider, Drawer or FormControl in
> that bundle.

That is true of **mabc-ws**, which vendors a trimmed build. It is **not** true
of EzySpeech: `app/templates/admin.html` loads
`app/static/patternfly/patternfly.css`, the **full** distribution. Verified by
fetching the served stylesheets and grepping for class names — Label, Switch,
Tabs, Toolbar, DataList, Form, FormControl, HelperText, Divider, Badge, Alert,
Tooltip, EmptyState and NumberInput are all present.

Replace that paragraph with:

> EzySpeech ships the full PatternFly distribution, so the whole component set
> is available. The house layer on top of it is `shell.css` (ported from the
> church site: `.doc-page`, `.with-rail`, `.page-rail`, `.page-head`, `.kv`,
> `.meta`, `.section`), plus `ezyspeech.css` and `admin.css`.
>
> Availability is not a licence. Reach for a component when it is the right
> one, not because it exists — and never hand-roll something PatternFly already
> has. Anything drawn by hand that PatternFly ships is a bug.

## 2. CORRECTION — `Current: NLT` is redundant

The Bible panel prints `Current: NLT` under a select whose visible value is
already `NLT — New Living Translation, 2015`. Delete the line.

---

## 3. ADDITION — the operator's control panel

Six buttons of equal weight above a stats card is where this went wrong.

- **Row actions live on rows.** Add and Edit act on one line; they belong in
  the row's kebab and in the correction cell, not in a global bar.
- **A destructive button with no target should not exist yet.** Export and
  Delete appear in the card header only once rows are selected, and the header
  says how many. `Delete` is `pf-m-danger pf-m-secondary` — outlined, not
  filled. Nothing on this card should be the only filled button.
- **Setting up is not operating.** Import and Clear all move to Setup. Clear
  all wipes a service; it does not belong beside Export.
- **One number, one row.** Translations / DB Entries / Transcripts were the
  same count three times, and two of them named the storage. It is `Lines`,
  with the word count as the `.meta` line. Peak Viewers and Clients were one
  concept: `Viewers — 1 now, 3 at peak`.
- **No Refresh button.** A live console that has to be asked is not live. If it
  genuinely cannot push, print when it last updated.
- **Pills are for status only.** A row count is not a status and a locale is
  not a status. `Recording` is.

See `markup/Admin.html`.

### A data bug, not a design one

A 53-second session reporting 6 words, 353 translations and 353 DB rows is
about 6.7 rows a second. That looks like interim recognition results being
persisted rather than finished lines. Check what the writer commits before
redrawing this card — no layout survives a counter that disagrees with itself.

---

## 4. ADDITION — the Settings dialog comes apart

`#settingsModal` holds three unrelated kinds of thing behind one label.

| What is in it now | What it actually is | Where it goes |
|---|---|---|
| Announcement, *Send to All Viewers* | A live operation that interrupts every viewer | The masthead's one primary action, `Announce` |
| Audience QR code | A live operation | The `Room and joining` card on the setup page |
| Room, Bible, TTS cache | Configuration set once | A **page** under Setup, like `Rooms` and `Server configuration` already are |
| Display language, Dark Mode, Keyboard Shortcuts, About | This operator's own browser preferences | The masthead overflow, beside the theme toggle |

After the split there is no Settings dialog left, and no second `Config` entry
point in the masthead either — `Server configuration` is already a nav item.

**A nav item that opens a modal is not navigation.** `Setup → Settings`,
`Rooms` and `Server configuration` are `<button onclick=…>` inside
`pf-v6-c-nav__link`. At least Service setup should become a real page.

See `markup/AdminSetup.html` and `markup/AdminUtils.html`.

### Spacing

The complaint that the buttons are badly spaced is real, and the cause is that
the spacing is hand-written.

- The setup page is a `pf-v6-c-form`; PatternFly owns the gaps between label,
  control and helper text. Do not add margins between form groups.
- Buttons sit in a `pf-v6-c-action-list`, which uses
  `--pf-t--global--spacer--gap--action-to-action--default`. Do not write
  margins between buttons.
- **Nothing is full-width.** A button is as wide as its label.
  `pf-m-block` on `Dark Mode` / `Keyboard Shortcuts` / `About` is a phone
  pattern used in a desktop dialog.
- The masthead splits into two groups — what belongs to the service, and what
  belongs to this operator — with `justify-content: space-between`. A lone
  vertical divider floating mid-bar is the symptom of not having grouped them.
