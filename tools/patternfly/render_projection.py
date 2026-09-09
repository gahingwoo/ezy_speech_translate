#!/usr/bin/env python3
"""Generate app/templates/projection.html: the screen at the front of the room.

    python3 tools/patternfly/render_projection.py

The one surface in the app that leaves the shell — no masthead, no sidebar,
no scrollbar. It is read from the back of an auditorium, so the sizes are set
for distance rather than for a phone, and the page never scrolls: what does
not fit is what has already been said.

The markup follows tools/patternfly/design/markup/Projection.html; the classes
are in app/static/css/ezyspeech.css, which the design ships.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from render_user import ROOT, LANGS, form_group, icon, select   # noqa: E402


# The four things a screen has to be told before it is pointed at a wall. The
# listener's wizard asks its questions the same way; the shape is PatternFly's
# and the machinery behind it is app/static/js/wizard.js, which both pages use.
SETUP_STEPS = (
    ("room", "Room", "proj_nav_room", "proj_step_room",
     "Which room's speaker is this screen following?"),
    ("language", "Language", "proj_nav_language", "proj_step_language",
     "The language the room reads here. The words the speaker actually said "
     "stay under it, quieter."),
    ("look", "The room", "proj_nav_look", "proj_step_look",
     "A bright room reads better off a light screen, a dark one off a dark "
     "screen. Nothing else about the page changes."),
    ("done", "Ready", "proj_nav_done", "proj_step_done",
     "The screen remembers this. Press s on the keyboard attached to it to "
     "come back here."),
)


def setup_wizard():
    """The same wizard the listener opens on a first visit, asking what a
    screen at the front of a room needs instead: which room, which language,
    and whether the room is dark. It writes its answers into the address, so
    the page is still configured by its query string and a screen can still be
    set up by pasting a URL."""
    nav = "".join(
        '''            <li class="pf-v6-c-wizard__nav-item">
              <button class="pf-v6-c-wizard__nav-link%s" type="button" id="projSetup-nav-%s"
                      onclick="projSetup.show('%s')"%s>
                <span class="pf-v6-c-wizard__nav-link-main">
                  <span class="pf-v6-c-wizard__nav-link-text" data-i18n="%s">%s</span>
                </span>
              </button>
            </li>
''' % (" pf-m-current" if i == 0 else "", key, key,
       ' aria-current="step"' if i == 0 else "", nav_key, title)
        for i, (key, title, nav_key, _body_key, _body) in enumerate(SETUP_STEPS))

    bodies = [
        '''            <div class="pf-v6-c-wizard__main-body setup-step" id="projSetup-room">
              <p class="pf-v6-c-content--p" data-i18n="proj_step_room">%s</p>
              <form class="pf-v6-c-form" onsubmit="return false;">
%s              </form>
            </div>
''' % (SETUP_STEPS[0][4],
       form_group("Room", "proj_nav_room",
                  select("projSetupRoom", "", "Room",
                         '<option value="main">Main</option>'),
                  "projSetupRoom")),

        '''            <div class="pf-v6-c-wizard__main-body setup-step" id="projSetup-language" hidden>
              <p class="pf-v6-c-content--p" data-i18n="proj_step_language">%s</p>
              <form class="pf-v6-c-form" onsubmit="return false;">
%s              </form>
            </div>
''' % (SETUP_STEPS[1][4],
       form_group("Language", "language",
                  select("projSetupLang", "", "Language", LANGS),
                  "projSetupLang")),

        '''            <div class="pf-v6-c-wizard__main-body setup-step" id="projSetup-look" hidden>
              <p class="pf-v6-c-content--p" data-i18n="proj_step_look">%s</p>
              <form class="pf-v6-c-form" onsubmit="return false;">
%s              </form>
            </div>
''' % (SETUP_STEPS[2][4],
       form_group("The room", "proj_nav_look",
                  select("projSetupTheme", "", "The room",
                         '<option value="light" data-i18n="proj_look_light">Bright room</option>'
                         '<option value="dark" data-i18n="proj_look_dark">Dark room</option>'),
                  "projSetupTheme")),

        '''            <div class="pf-v6-c-wizard__main-body setup-step" id="projSetup-done" hidden>
              <p class="pf-v6-c-content--p" data-i18n="proj_step_done">%s</p>
              <p class="pf-v6-c-content--p proj-setup-address">
                <span data-i18n="projJoin">Read along in your own language</span>
                &mdash; <strong id="projSetupJoin"></strong></p>
            </div>
''' % SETUP_STEPS[3][4],
    ]

    return '''  <div class="pf-v6-c-backdrop app-modal proj-setup" id="projSetupModal">
   <div class="pf-v6-c-modal-box pf-m-md setup-wizard" role="dialog" aria-modal="true"
        aria-labelledby="projSetupTitle">
    <div class="pf-v6-c-wizard pf-m-plain">
      <div class="pf-v6-c-wizard__header">
        <h1 class="pf-v6-c-wizard__title" id="projSetupTitle">
          <span class="pf-v6-c-wizard__title-text" data-i18n="proj_setup_title">Set up this screen</span>
        </h1>
        <div class="pf-v6-c-wizard__description" data-i18n="proj_setup_intro">
          This screen follows one room and shows one language.</div>
      </div>
      <div class="pf-v6-c-wizard__outer-wrap">
        <button class="pf-v6-c-wizard__toggle" type="button" id="projSetupToggle"
                aria-expanded="false" aria-controls="projSetupNav"
                onclick="projSetup.toggleNav()">
          <span class="pf-v6-c-wizard__toggle-list">
            <span class="pf-v6-c-wizard__toggle-list-item">
              <span class="pf-v6-c-wizard__toggle-num" id="projSetupToggleNum">1</span>
              <span id="projSetupToggleTitle" data-i18n="proj_nav_room">Room</span>
            </span>
          </span>
          <span class="pf-v6-c-wizard__toggle-icon">%s</span>
        </button>
        <div class="pf-v6-c-wizard__inner-wrap">
          <nav class="pf-v6-c-wizard__nav" id="projSetupNav" aria-label="Setup steps">
            <ol class="pf-v6-c-wizard__nav-list">
%s            </ol>
          </nav>
          <main class="pf-v6-c-wizard__main">
%s          </main>
        </div>
        <footer class="pf-v6-c-wizard__footer">
          <div class="pf-v6-c-action-list">
            <div class="pf-v6-c-action-list__group"></div>
            <div class="pf-v6-c-action-list__group">
              <div class="pf-v6-c-action-list__item">
                <button class="pf-v6-c-button pf-m-secondary" type="button" id="projSetupBack"
                        onclick="projSetup.back()" disabled>
                  <span class="pf-v6-c-button__text" data-i18n="tour_prev">Back</span>
                </button>
              </div>
              <div class="pf-v6-c-action-list__item">
                <button class="pf-v6-c-button pf-m-primary" type="button" id="projSetupNext"
                        onclick="projSetup.next()">
                  <span class="pf-v6-c-button__text" data-i18n="tour_next">Next</span>
                </button>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
   </div>
  </div>
''' % (icon("angle-down"), nav, "".join(bodies))


def build():
    return '''<!DOCTYPE html>
<!-- Generated by tools/patternfly/render_projection.py. Edit that, not this. -->
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta content="width=device-width, initial-scale=1.0" name="viewport">
  <title>EzySpeech - Projection</title>
  <!-- The room feed. Without this the page drew its clock and its footer and
       waited for a line that could never arrive: io was undefined, connect()
       threw, and the screen at the front of the room stayed empty for the
       whole service. -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
  <link href="{{ static_url('patternfly/patternfly.css') }}" rel="stylesheet">
  <link href="{{ static_url('css/shell.css') }}" rel="stylesheet">
  <link href="{{ static_url('css/ezyspeech.css') }}" rel="stylesheet">
  <link href="{{ static_url('css/projection.css') }}" rel="stylesheet">
</head>

<body data-theme="light" data-page="projection">
  <div class="proj">
    <div class="proj-top">
      <span class="brand">
        <img class="pf-v6-c-brand brand-mark" src="{{ static_url('img/mabc-mark.png') }}"
             width="208" height="208" alt="">
        <span class="brand-name" id="projRoom">EzySpeech</span>
      </span>
      <span class="proj-top-end">
        <span class="proj-lang" id="projLang"></span>
        <span class="proj-clock" id="projClock">--:--:--</span>
        <!-- The only thing on the screen anyone is meant to press, and only
             before the service. It is nearly invisible until the pointer or
             the keyboard finds it: a room should not spend an hour looking at
             a control it is not going to use. -->
        <button class="pf-v6-c-button pf-m-plain proj-setup-open" type="button"
                id="projSetupOpen" data-i18n-title="settings" title="Settings"
                aria-label="Set up this screen" onclick="openSetup()">%(cog)s</button>
      </span>
    </div>

    <!-- Two lines already said, then the line being said now. The room reads
         the big one; the two above it are there for anyone who looked away. -->
    <div class="proj-stage">
      <p class="proj-past proj-past-2" id="projPast2"></p>
      <p class="proj-past proj-past-1" id="projPast1"></p>
      <p class="proj-now" id="projNow"></p>
      <p class="proj-source" id="projSource"></p>
    </div>

    <!-- A verse, when one was read. Looked up in a Bible rather than
         translated, so it is exact and it says which Bible. -->
    <div class="proj-verse" id="projVerse" hidden>
      <p class="proj-verse-ref" id="projVerseRef"></p>
      <p class="proj-verse-text" id="projVerseText"></p>
    </div>

    <div class="proj-foot">
      <span class="proj-join" id="projJoin"></span>
      <span class="proj-langs" id="projLangs"></span>
    </div>
  </div>

%(setup)s

  <script src="{{ static_url('js/i18n.js') }}"></script>
  <script src="{{ static_url('js/wizard.js') }}"></script>
  <script src="{{ static_url('js/typewriter.js') }}"></script>
  <script src="{{ static_url('js/projection.js') }}"></script>
</body>

</html>
''' % {"setup": setup_wizard(), "cog": icon("cog")}


if __name__ == "__main__":
    out = ROOT / "app/templates/projection.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote %s (%d bytes)" % (out.relative_to(ROOT), out.stat().st_size))
