# Handing this to another agent

## What is in here

```
SPEC.md          the design decisions — read this first
ezyspeech.css    the classes this design adds, token-only, ~180 lines
markup/          PatternFly 6 markup per screen, no CSS inlined
```

`markup/` files are body fragments. They assume the two church-site
stylesheets are already loaded and expect `/assets/brand/mark.png`.

| File | Screen |
|---|---|
| `Main.html` | Viewer — the live stream. The same markup serves desktop, phone and light theme. |
| `Scripture.html` | Viewer — passages read in this service |
| `Settings.html` | Viewer — text, audio and language |
| `LanguageDialog.html` | The language dialog, over the viewer |
| `PassageModal.html` | The passage dialog, over the viewer |
| `Admin.html` | Operator console |
| `Projection.html` | The projected screen — leaves the app shell |

## The prompt to give the other agent

> I have a design for EzySpeech, our live sermon translation app. It is
> PatternFly 6 markup built on the same stylesheets as our church site
> (`assets/patternfly/patternfly-site.css` and `assets/site.css` in the
> mabc-ws repo).
>
> Read `SPEC.md` first — it has the rules the markup follows and the reasons
> behind them. `markup/` holds the body fragment for each screen; `ezyspeech.css`
> holds the classes the design adds, and appends to `site.css`.
>
> Port these into the EzySpeech app. Constraints:
>
> - Use only the PatternFly components vendored by `tools/patternfly/build.sh`.
>   If something seems to need a component that is not in that list, the design
>   is wrong — tell me rather than reaching for another library.
> - Do not change PatternFly's density, and do not introduce literal colours,
>   radii or spacing. Everything is a token.
> - The reserved-space behaviour while a translation is in flight is the point
>   of the stream layout, not a detail. Keep it.
> - Scripture is a Bible lookup, not machine output. Keep the labels that say
>   how each verse was matched, and keep the rule that a doubtful match is
>   offered rather than substituted.
>
> The open questions at the end of `SPEC.md` are mine to answer — ask me, do
> not invent values.

## If you want the design to keep evolving

The canvas is at the artifact link and can be edited there. These files are a
snapshot of it. If the other agent changes the design rather than only building
it, the canvas and this package will drift — decide which one is the source of
truth before that happens.
