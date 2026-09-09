# Projection Screen — Usage Guide

The screen at the front of the room, at `/projection` on the user server. It
follows one room's feed and shows one language, read from the back of an
auditorium rather than from a phone.

It is not the listener page at a larger size. The listener page is a history
you can scroll, search and export; this shows the line being said now, the two
before it, and nothing else. It never scrolls — what does not fit is what has
already been said.

---

## Quick Start

1. Start the user server (default port `1915`).
2. On the machine driving the projector, open `http://<server>:1915/projection`.
3. It asks four things, once:

   | Step | What it asks |
   |---|---|
   | Room | Which room's speaker this screen follows. The list comes from the server, so you do not need to know a room's id |
   | Language | The language the room reads on this screen |
   | The room | Bright or dark. A lit hall reads better off a light screen, a dark one off a dark screen |
   | Ready | Shows the address people join at, and how to come back here |

4. Press **Done**. The screen starts.

The answers are remembered, so a projector that loses power comes back to the
same room and the same language rather than to a blank page or a setup box.

---

## Setting it up without the wizard

Every answer is also a query parameter, and the wizard writes them into the
address when it finishes. A screen can therefore be set up by pasting a URL,
and a second screen by copying the first one's:

```
http://<server>:1915/projection?room=main&lang=yue&theme=dark&join=ezyspeech.example.org
```

| Parameter | Default | Meaning |
|---|---|---|
| `room` | `main` | Which room's feed to follow |
| `lang` | *(none)* | The language to project. Left out, the screen shows the words as they were said |
| `theme` | `light` | `light` or `dark` |
| `join` | the server's own host | The address shown at the foot for the room to read along at |
| `setup=1` | — | Open the setup wizard on load, whatever is stored |

A parameter in the address wins over what the screen remembers, and what it
remembers is used for anything the address leaves out.

---

## Reopening the setup

- Press **`s`** on the keyboard attached to the machine.
- Or click the gear beside the clock. It sits at a quarter opacity until the
  pointer, the keyboard or a finger finds it: a room looks at this wall for an
  hour, and a control it is not going to use should not be part of what it
  looks at.
- `Esc` closes it again without changing anything.

Apart from that gear there is nothing on the screen to press. Whoever is
leading the service should never have to touch it once it is up.

---

## What is on the screen

**Top row** — the room's name on the left; on the right the language pair, the
clock, and the gear. The language pair is only shown when there is one: if the
language being read is the language being spoken, nothing is being translated
and the screen does not say "English → English".

**The stage** — three lines. The one being said now is the large one; the two
above it are quieter, and are there for anyone who looked away. Under the big
line, quieter still, are the speaker's own words, when they differ from what is
being shown.

The line being read is **typed as it arrives** rather than appearing whole. The
screen listens to the interim feed, so the words appear while they are being
said, and only the part that is new is typed — a sentence that grows a word at
a time grows on screen instead of being retyped from its first letter. The two
lines above it have already been read, so they move up in place.

**Scripture** — a verse that was read is looked up in a Bible in the projected
language and shown with its reference and which translation it came from. It
stays up after the line that carried it has moved on, because the room is still
looking at it; it goes when the next verse arrives, not when the next line does.

**The foot** — the address for the room to read along at in their own language.
If the feed drops, the foot changes colour. The screen says so once, quietly,
and does not throw a dialog in front of a congregation.

---

## Notes for whoever sets it up

- The page needs the same network access as a listener: Socket.IO to the user
  server, and the translation endpoint if it is projecting a language other
  than the one being spoken.
- The clock is the machine's own, in 24-hour time. A service runs to the clock
  on the wall, so it should be the same clock.
- Nothing on this page is authenticated. It shows what any listener can see. Do
  not put it on an address the public can reach if the room's feed is private.
- The wizard is shown in the language being projected, so whoever sets up a
  Cantonese service reads Cantonese.

---

## Troubleshooting

**The screen is blank and the clock is running.** It is connected but nothing
has been said yet, or it is following a room nobody is speaking in. Press `s`
and check the room.

**The foot has changed colour.** The feed has dropped. The screen keeps the
last three lines up and reconnects on its own; if it does not, the user server
is not reachable from that machine.

**The words are in the wrong language.** Press `s` and check the language step.
If the language shown matches the language being spoken, no translation is
happening — that is correct, and the pair at the top will be blank.

**It asks for setup every time it starts.** The machine is not keeping local
storage — a browser in private mode, or a kiosk that clears site data on exit.
Put the settings in the address instead: they are read from there first.
