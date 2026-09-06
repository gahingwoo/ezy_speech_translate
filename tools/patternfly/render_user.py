#!/usr/bin/env python3
"""Generate app/templates/user.html as PatternFly 6.

The page was hand-written CSS wearing PatternFly's class names. This builds it
out of the real components instead, and it is a generator rather than an edited
file because the icons are 32 real SVG paths from @patternfly/react-icons and
inlining them by hand is how mistakes get made.

    python3 tools/patternfly/render_user.py

Everything the JavaScript reaches for is preserved: every id, every inline
handler, every data-i18n key and the Jinja block around the Bible section.
tools/patternfly/check_contract.py proves it afterwards.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ICONS = json.loads((ROOT / "tools/patternfly/icons.json").read_text())


def icon(name, cls="pf-v6-svg"):
    """One PatternFly icon, inline, from the official path data."""
    i = ICONS[name]
    return ('<svg class="%s" viewBox="0 0 %d %d" fill="currentColor" '
            'aria-hidden="true" role="img" width="1em" height="1em">'
            '<path d="%s"/></svg>' % (cls, i["w"], i["h"], i["d"]))


def i18n_attr(key):
    return ' data-i18n="%s"' % key if key else ""


def btn_icon(name):
    return '<span class="pf-v6-c-button__icon">%s</span>' % icon(name)


# user.js builds cards, tour steps and the announcement banner as HTML strings
# and used emoji for their icons. It cannot inline a 2,000-character path, so
# the icons it needs go in the page once as a sprite and it references them by
# id through svgIcon() — see the helper of that name in user.js.
SPRITE_ICONS = ("book", "bullhorn", "check", "check-circle", "copy", "edit",
                "exclamation-circle", "exclamation-triangle", "globe",
                "info-circle", "keyboard", "microphone", "search", "times",
                "volume-up", "wheelchair")


def sprite():
    parts = []
    for name in SPRITE_ICONS:
        i = ICONS[name]
        parts.append('    <symbol id="i-%s" viewBox="0 0 %d %d"><path d="%s"/></symbol>'
                     % (name, i["w"], i["h"], i["d"]))
    return ('  <svg class="pf-sprite" aria-hidden="true" focusable="false" width="0" height="0">\n'
            '%s\n  </svg>\n' % "\n".join(parts))


def form_group(label_text, i18n_key, control, for_id=None, group_id=None):
    """PatternFly form group: label above, control below."""
    label = ""
    if label_text is not None:
        label = ('        <div class="pf-v6-c-form__group-label">\n'
                 '          <label class="pf-v6-c-form__label"%s>\n'
                 '            <span class="pf-v6-c-form__label-text" data-i18n="%s">%s</span>\n'
                 '          </label>\n'
                 '        </div>\n' % (' for="%s"' % for_id if for_id else "", i18n_key, label_text))
    return ('      <div class="pf-v6-c-form__group"%s>\n%s'
            '        <div class="pf-v6-c-form__group-control">\n%s\n'
            '        </div>\n'
            '      </div>\n' % (' id="%s"' % group_id if group_id else "", label, control))


def select(el_id, onchange, aria, options, extra=""):
    return ('          <span class="pf-v6-c-form-control">\n'
            '            <select id="%s" aria-label="%s" onchange="%s"%s>%s</select>\n'
            '            <span class="pf-v6-c-form-control__utilities">\n'
            '              <span class="pf-v6-c-form-control__toggle-icon">%s</span>\n'
            '            </span>\n'
            '          </span>' % (el_id, aria, onchange, extra, options, icon("angle-down")))


def field_group(title, i18n, body, el_id=None, extra=""):
    """PatternFly's expandable field group, which is what the design system
    offers for a long form: the panel holds six groups of controls and only the
    display settings are touched every time, so the rest start folded. The
    component animates its own body open and shut."""
    return '''    <div class="pf-v6-c-form__field-group pf-m-expandable sidebar-section"%s%s>
      <div class="pf-v6-c-form__field-group-toggle">
        <div class="pf-v6-c-form__field-group-toggle-button">
          <button class="pf-v6-c-button pf-m-plain" type="button" aria-expanded="false"
                  aria-label="Toggle %s" onclick="toggleFieldGroup(this)">
            <span class="pf-v6-c-form__field-group-toggle-icon">%s</span>
          </button>
        </div>
      </div>
      <div class="pf-v6-c-form__field-group-header">
        <div class="pf-v6-c-form__field-group-header-main">
          <div class="pf-v6-c-form__field-group-header-title">
            <div class="pf-v6-c-form__field-group-header-title-text"%s>%s</div>
          </div>
        </div>
      </div>
      <div class="pf-v6-c-form__field-group-body">
%s      </div>
    </div>
''' % (' id="%s"' % el_id if el_id else "", extra, title, icon("angle-right"),
       ' data-i18n="%s"' % i18n if i18n else "", title, body)


def sidebar_button(el_id, onclick, aria, icon_name, text_id, text, i18n_key=None, extra=""):
    """A full-width action in the sidebar. PatternFly's secondary button, not
    a nav item: these do things, they do not navigate. Not the link button
    either — a column of underlined links reads as unfinished."""
    label = ('<span id="%s"%s>%s</span>' % (text_id, ' data-i18n="%s"' % i18n_key if i18n_key else "", text)
             if text_id else
             '<span%s>%s</span>' % (' data-i18n="%s"' % i18n_key if i18n_key else "", text))
    return ('      <div class="pf-v6-c-form__group">\n'
            '        <button class="pf-v6-c-button pf-m-secondary pf-m-block sidebar-action" type="button"'
            '%s aria-label="%s" onclick="%s"%s>\n'
            '          %s\n'
            '          <span class="pf-v6-c-button__text">%s</span>\n'
            '        </button>\n'
            '      </div>\n'
            % (' id="%s"' % el_id if el_id else "", aria, onclick, extra,
               btn_icon(icon_name), label))


LANGS = ('<option value="en">English</option><option value="zh">简体中文</option>'
         '<option value="zh-tw">繁體中文</option><option value="yue">粵語</option>'
         '<option value="ja">日本語</option><option value="ko">한국어</option>'
         '<option value="es">Español</option><option value="fr">Français</option>'
         '<option value="de">Deutsch</option><option value="pt">Português</option>'
         '<option value="ru">Русский</option><option value="ar">العربية</option>'
         '<option value="hi">हिन्दी</option><option value="th">ไทย</option>'
         '<option value="vi">Tiếng Việt</option><option value="id">Bahasa Indonesia</option>'
         '<option value="ms">Bahasa Melayu</option><option value="tl">Tagalog</option>'
         '<option value="sm">Gagana Samoa</option><option value="to">Lea faka-Tonga</option>'
         '<option value="mi">Te Reo Māori</option>')


def modal(el_id, title_id, title_i18n, title_text, body, footer="", close_fn=None,
          title_icon_id=None, title_text_id=None, size="md"):
    close = close_fn or ("hide" + el_id.replace("Modal", "").capitalize() + "()")
    # The backdrop closes on a click; a click on the box itself must not reach
    # it, which is what the app's own handlers already expected.
    outer = close.replace("()", "(event)")
    return '''  <div class="pf-v6-c-backdrop app-modal" id="%s" onclick="%s">
    <div class="pf-v6-c-modal-box pf-m-%s" role="dialog" aria-modal="true" aria-labelledby="%s">
        <div class="pf-v6-c-modal-box__close">
          <button class="pf-v6-c-button pf-m-plain" type="button" aria-label="Close" onclick="%s">%s</button>
        </div>
        <header class="pf-v6-c-modal-box__header">
          <h1 class="pf-v6-c-modal-box__title%s" id="%s">%s
            <span class="pf-v6-c-modal-box__title-text"%s%s>%s</span>
          </h1>
        </header>
        <div class="pf-v6-c-modal-box__body">
%s
        </div>%s
    </div>
  </div>
''' % (el_id, outer, size, title_id, close, btn_icon("times"),
       " pf-m-icon" if title_icon_id else "", title_id,
       # An element carrying data-i18n has its textContent replaced wholesale,
       # so anything the JavaScript writes into has to be a sibling of it, never
       # a child: nesting the tour's icon inside the title deleted it on the
       # first language pass.
       ('\n            <span class="pf-v6-c-modal-box__title-icon" id="%s"'
        ' aria-hidden="true"></span>' % title_icon_id) if title_icon_id else "",
       ' id="%s"' % title_text_id if title_text_id else "",
       ' data-i18n="%s"' % title_i18n if title_i18n else "",
       title_text, body, footer)


# term, its translation key, value, the value's translation key.
ABOUT_ROWS = (
    ("Version", None, "v4.0.0 - Open Source - MIT License", "version"),
    ("Source", None, '<a href="https://github.com/gahingwoo/ezy_speech_translate"'
     ' rel="noopener noreferrer" target="_blank">gahingwoo/ezy_speech_translate</a>',
     None),
    ("Feedback", "feedback", '<a href="https://github.com/gahingwoo/ezy_speech_translate/issues/new/choose"'
     ' rel="noopener noreferrer" target="_blank">Open an issue</a>', None),
)


def about_modal():
    """PatternFly's about modal, which is the component this box has always
    been imitating. The backdrop centres it directly, with no wrapper, because
    hideAbout() closes on `event.target === this`."""
    rows = "".join(
        '''          <div class="pf-v6-c-description-list__group">
            <dt class="pf-v6-c-description-list__term">
              <span class="pf-v6-c-description-list__text"%s>%s</span>
            </dt>
            <dd class="pf-v6-c-description-list__description">
              <div class="pf-v6-c-description-list__text"%s>%s</div>
            </dd>
          </div>
''' % (i18n_attr(term_key), term, i18n_attr(value_key), value)
        for term, term_key, value, value_key in ABOUT_ROWS)

    return '''  <div class="pf-v6-c-backdrop app-modal about-backdrop" id="aboutModal"
       onclick="hideAbout(event)">
    <div class="pf-v6-c-about-modal-box" role="dialog" aria-modal="true"
         aria-labelledby="aboutTitle">
      <div class="pf-v6-c-about-modal-box__brand">
        <img class="pf-v6-c-about-modal-box__brand-image"
             src="{{ static_url('img/mabc-mark.png') }}" width="208" height="208" alt="">
      </div>
      <div class="pf-v6-c-about-modal-box__close">
        <button class="pf-v6-c-button pf-m-plain about-close" type="button"
                aria-label="Close" onclick="hideAbout()">%s</button>
      </div>
      <div class="pf-v6-c-about-modal-box__header">
        <h1 class="pf-v6-c-title pf-m-4xl" id="aboutTitle" data-i18n="aboutTitle">EzySpeech</h1>
      </div>
      <div class="pf-v6-c-about-modal-box__content">
        <dl class="pf-v6-c-description-list pf-m-horizontal">
%s        </dl>
        <p class="credit-badge">
          <a href="https://github.com/gahingwoo" rel="noopener noreferrer" target="_blank">
            <img class="credit-badge__light" src="{{ static_url('img/credit-badge-light.svg') }}"
                 width="360" height="110" alt="Engineered by gahingwoo">
            <img class="credit-badge__dark" src="{{ static_url('img/credit-badge-dark.svg') }}"
                 width="360" height="110" alt="">
          </a>
        </p>
        <p class="pf-v6-c-about-modal-box__strapline" data-i18n="tagline">
          Let language no longer stand in the way of connection</p>
      </div>
    </div>
  </div>
''' % (btn_icon("times"), rows)


def build():
    sidebar = []

    # Room switcher, hidden until there is more than one room
    sidebar.append('''    <section class="pf-v6-c-form__section sidebar-section user-room-switcher-section"
             id="userRoomSwitcherSection" hidden>
      <h2 class="pf-v6-c-form__section-title" data-i18n="room">Room</h2>
%s    </section>
''' % form_group("Current room", "currentRoom",
                 select("userRoomSelect", "window.userSwitchRoom && window.userSwitchRoom(this.value)",
                        "Switch room", ""), "userRoomSelect"))

    # Display
    sidebar.append('''    <section class="pf-v6-c-form__section sidebar-section">
      <h2 class="pf-v6-c-form__section-title" data-i18n="displaySettings">Display Settings</h2>
%s%s%s    </section>
''' % (
        form_group("Display Language", "displayLanguage",
                   select("displayLanguage", "changeDisplayLanguageLocal()", "Select display language", LANGS),
                   "displayLanguage"),
        form_group("Display Mode", "displayMode",
                   select("displayMode", "changeDisplayMode()", "Select display mode",
                          '<option value="translation" data-i18n="translation">Translation</option>'
                          '<option value="transcription" data-i18n="transcriptionOnly">Transcription</option>'),
                   "displayMode"),
        form_group("Target Language", "targetLanguage",
                   select("targetLang", "changeLanguage()", "Select target language", LANGS),
                   "targetLang", group_id="languageSelectGroup"),
    ))

    # Text to speech
    sidebar.append(field_group("Text-to-Speech", "textToSpeech", '''
      <div class="pf-v6-c-form__group">
        <button class="pf-v6-c-button pf-m-primary pf-m-block" type="button" id="toggleTTS"
                aria-pressed="false" aria-label="Toggle text to speech" onclick="toggleTTS()">
          %s
          <span class="pf-v6-c-button__text" data-i18n="enableTTS">Enable TTS</span>
        </button>
      </div>
%s%s%s%s
''' % (
        btn_icon("volume-up"),
        form_group("TTS Engine", "ttsEngine",
                   select("ttsEngine", "changeTTSEngine()", "Select TTS engine",
                          '<option value="system" data-i18n="tts_system">System (Local)</option>'
                          '<option value="edge" data-i18n="tts_edge">Edge (Server)</option>'),
                   "ttsEngine"),
        form_group("Voice", "voice",
                   select("voiceSelect", "changeVoice()", "Select voice",
                          '<option value="" data-i18n="tts_autoVoice">Auto (System Default)</option>'),
                   "voiceSelect"),
        form_group("Speed", "speed",
                   '''          <div class="pf-v6-c-slider">
            <div class="pf-v6-c-slider__main">
              <input class="pf-v6-c-slider__rail slider" id="rateSlider" type="range"
                     min="0.5" max="2" step="0.1" value="1" aria-label="Speech rate"
                     oninput="updateRate()">
            </div>
            <div class="pf-v6-c-slider__value"><span class="slider-value" id="rateValue">1.0x</span></div>
          </div>''', "rateSlider"),
        form_group("Volume", "volume",
                   '''          <div class="pf-v6-c-slider">
            <div class="pf-v6-c-slider__main">
              <input class="pf-v6-c-slider__rail slider" id="volumeSlider" type="range"
                     min="0" max="1" step="0.05" value="1" aria-label="Speech volume"
                     oninput="updateVolume()">
            </div>
            <div class="pf-v6-c-slider__value"><span class="slider-value" id="volumeValue">100%</span></div>
          </div>''', "volumeSlider"),
    )))

    # Export
    sidebar.append(field_group("Export", "export", '''
%s      <div class="pf-v6-c-form__group">
        <button class="pf-v6-c-button pf-m-primary pf-m-block" type="button"
                aria-label="Download translations" onclick="exportData()">
          %s
          <span class="pf-v6-c-button__text" data-i18n="download">Download</span>
        </button>
      </div>
%s%s
''' % (
        form_group("Format", "format",
                   select("exportFormat", "", "Select export format",
                          '<option value="txt" data-i18n="format_txt">Text (TXT)</option>'
                          '<option value="json" data-i18n="format_json">JSON</option>'
                          '<option value="csv" data-i18n="format_csv">CSV</option>'
                          '<option value="srt" data-i18n="format_srt">Subtitle (SRT)</option>'),
                   "exportFormat"),
        btn_icon("download"),
        sidebar_button("ai-summary-btn", "shareForAI('chatgpt')", "Share for AI", "share-alt",
                       None, "AI sermon summary", "aiSermonSummary") +
        '      <p class="pf-v6-c-form__helper-text" data-i18n="aiSermonHint">'
        'Opens your AI assistant with the transcript.</p>\n',
        sidebar_button(None, "clearLocal()", "Clear display", "trash", None, "Clear display", "clearDisplay"),
    )))

    # Settings
    sidebar.append(field_group("Settings", "settings", '''
%s%s%s%s%s%s%s%s
''' % (
        form_group("View Mode", "uiMode",
                   select("uiMode", "updateUIMode()", "View mode",
                          '<option value="standard" data-i18n="uiMode_standard">Standard</option>'
                          '<option value="accessibility" data-i18n="uiMode_accessibility">Accessibility</option>'
                          '<option value="elderly" data-i18n="uiMode_elderly">Elderly</option>'),
                   "uiMode"),
        form_group("Font Size", "fontSize",
                   '''          <div class="pf-v6-c-slider">
            <div class="pf-v6-c-slider__main">
              <input class="pf-v6-c-slider__rail slider" id="fontSizeSlider" type="range"
                     min="12" max="24" step="1" value="18" aria-label="Translation font size"
                     oninput="updateFontSize()">
            </div>
            <div class="pf-v6-c-slider__value"><span id="fontSizeValue">18px</span></div>
          </div>''', "fontSizeSlider"),
        sidebar_button("sourceTextToggle", "toggleSourceText()", "Toggle source text display",
                       "book", "sourceTextText", "Show Source"),
        ('      <div class="pf-v6-c-form__group">\n'
         '        <button class="pf-v6-c-button pf-m-secondary pf-m-block sidebar-action" type="button"'
         ' aria-label="Toggle theme" onclick="toggleTheme()">\n'
         '          <span class="pf-v6-c-button__icon" id="themeIcon">%s%s</span>\n'
         '          <span class="pf-v6-c-button__text"><span id="themeText" data-i18n="darkMode">Dark Mode</span></span>\n'
         '        </button>\n'
         '      </div>\n' % (icon("moon", "pf-v6-svg icon-moon"), icon("sun", "pf-v6-svg icon-sun"))),
        sidebar_button(None, "resetSettings()", "Reset settings", "sync-alt", None, "Reset Settings", "resetSettings"),
        sidebar_button(None, "showTour()", "User guide", "lightbulb", None, "User Guide", "userGuide"),
        sidebar_button(None, "showShortcuts()", "Keyboard shortcuts", "keyboard", None,
                       "Keyboard Shortcuts", "shortcuts_title"),
        sidebar_button(None, "showAbout()", "About", "info-circle", None, "About", "about"),
    )))

    # Bible verses, behind the same Jinja flag as before
    sidebar.append('''    {% if bible_detection_enabled %}
''' + field_group("Bible Verses", "bibleVerses", '''%s      <div class="pf-v6-c-form__group" id="bibleVerseToggleWrap">
%s        <p class="pf-v6-c-form__helper-text" id="bibleTransLoadingHint" hidden>
          <span data-i18n="bibleAutoMatched">Auto-matched to your language. Choose any Bible below.</span>
        </p>
      </div>
''' % (
        sidebar_button("bibleVerseToggle", "toggleBibleVerse()", "Toggle Bible verse display",
                       "book", "bibleVerseText", "Show Bible Verses", "bibleVerseShow",
                       extra=' aria-pressed="false"'),
        form_group("Your Bible", "yourBible",
                   select("bibleTargetTranslation", "onBibleTranslationChange()",
                          "Select Bible translation for your language",
                          '<option value="" data-i18n="bibleLoading">— Loading... —</option>'),
                   "bibleTargetTranslation"),
    ), el_id="bibleSidebarSection", extra=' aria-label="Bible Verses"')
                   + '''    {% endif %}
''')


    shortcuts_body = '''          <dl class="pf-v6-c-description-list pf-m-horizontal">
            <div class="pf-v6-c-description-list__group">
              <dt class="pf-v6-c-description-list__term"><span class="pf-v6-c-description-list__text"
                  data-i18n="shortcuts_help">Show this help</span></dt>
              <dd class="pf-v6-c-description-list__description"><div class="pf-v6-c-description-list__text"><kbd>?</kbd></div></dd>
            </div>
            <div class="pf-v6-c-description-list__group">
              <dt class="pf-v6-c-description-list__term"><span class="pf-v6-c-description-list__text"
                  data-i18n="shortcuts_search">Focus search</span></dt>
              <dd class="pf-v6-c-description-list__description"><div class="pf-v6-c-description-list__text"><kbd>/</kbd></div></dd>
            </div>
            <div class="pf-v6-c-description-list__group">
              <dt class="pf-v6-c-description-list__term"><span class="pf-v6-c-description-list__text"
                  data-i18n="shortcuts_top">Scroll to top</span></dt>
              <dd class="pf-v6-c-description-list__description"><div class="pf-v6-c-description-list__text"><kbd>g</kbd></div></dd>
            </div>
            <div class="pf-v6-c-description-list__group">
              <dt class="pf-v6-c-description-list__term"><span class="pf-v6-c-description-list__text"
                  data-i18n="shortcuts_close">Close dialog / menu</span></dt>
              <dd class="pf-v6-c-description-list__description"><div class="pf-v6-c-description-list__text"><kbd>Esc</kbd></div></dd>
            </div>
          </dl>'''

    welcome_body = '''          <p class="pf-v6-c-content--p" data-i18n="welcome_intro">
            Real-time speech translations will appear here as the host speaks.</p>
          <ul class="pf-v6-c-list" role="list">
            <li data-i18n="welcome_tip_lang">Pick your display language in the sidebar.</li>
            <li data-i18n="welcome_tip_tts">Enable Text-to-Speech to hear translations aloud.</li>
            <li data-i18n="welcome_tip_copy">Tap a card to copy or replay it.</li>
            <li><span data-i18n="welcome_tip_keys">Press</span> <kbd>?</kbd>
                <span data-i18n="welcome_tip_keys_after">any time for shortcuts.</span></li>
          </ul>'''

    welcome_footer = '''
        <footer class="pf-v6-c-modal-box__footer">
          <button class="pf-v6-c-button pf-m-secondary" type="button" onclick="hideWelcome()">
            <span class="pf-v6-c-button__text" data-i18n="welcome_gotIt">Got it</span>
          </button>
          <button class="pf-v6-c-button pf-m-primary" type="button" onclick="hideWelcome(); showTour();">
            <span class="pf-v6-c-button__text" data-i18n="welcome_takeTour">Take a quick tour</span>
          </button>
        </footer>'''

    tour_body = '''          <div class="tour-layout">
            <ol class="pf-v6-c-progress-stepper pf-m-vertical" id="tourDots"
                aria-label="Guide steps"></ol>
            <div class="tour-body pf-v6-c-content" id="tourStepBody"></div>
          </div>'''
    tour_footer = '''
        <footer class="pf-v6-c-modal-box__footer">
          <span class="tour-progress" id="tourProgress">1 / 1</span>
          <button class="pf-v6-c-button pf-m-secondary" type="button" id="tourPrev" onclick="tourPrev()">
            <span class="pf-v6-c-button__text" data-i18n="tour_prev">Back</span>
          </button>
          <button class="pf-v6-c-button pf-m-primary" type="button" id="tourNext" onclick="tourNext()">
            <span class="pf-v6-c-button__text" data-i18n="tour_next">Next</span>
          </button>
        </footer>'''

    return '''<!DOCTYPE html>
<!-- Generated by tools/patternfly/render_user.py. Edit that, not this. -->
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta content="width=device-width, initial-scale=1.0" name="viewport">
  <title>EzySpeech - User Client</title>
  <meta data-i18n-meta="metaDescription" name="description"
        content="Real-time speech translation with TTS support for 20+ languages">
  <!-- Favicon will be set by OEM loader -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
  <!-- PatternFly carries Red Hat Text, Display and Mono itself, so the fonts
       no longer come from Google. -->
  <link href="{{ static_url('patternfly/patternfly.css') }}" rel="stylesheet">
  <link href="{{ static_url('css/user.css') }}" rel="stylesheet">
  <script src="{{ static_url('js/oem-loader.js') }}"></script>
</head>

<body data-theme="light">
  <a class="pf-v6-c-skip-to-content pf-v6-c-button pf-m-primary" href="#main-content"
     data-i18n="skipToMain">Skip to content</a>
  <div id="google_translate_element" hidden></div>

%(sprite)s

  <!-- Toasts. PatternFly's alert group in its toast position. -->
  <ul class="pf-v6-c-alert-group pf-m-toast toast-container" id="toastContainer" role="list"
      aria-live="polite" aria-atomic="true"></ul>

  <div class="pf-v6-c-page">
    <!-- PatternFly stacks the masthead by default: the brand takes its own
         row, the toggle and the actions the next. That is right on a phone;
         from md there is room for one row. -->
    <header class="pf-v6-c-masthead pf-m-display-inline-on-md" role="banner">
      <div class="pf-v6-c-masthead__main">
        <span class="pf-v6-c-masthead__toggle">
          <button class="pf-v6-c-button pf-m-plain" type="button" id="mobileMenuToggle"
                  aria-controls="sidebar" aria-expanded="false" aria-label="Toggle mobile menu"
                  onclick="toggleMobileMenu()">%(bars)s</button>
        </span>
        <div class="pf-v6-c-masthead__brand">
          <!-- .brand and the order of its two spans are what oem-loader.js
               writes a customer's icon and name into. -->
          <div class="pf-v6-c-masthead__logo brand">
            <span aria-hidden="true"><img class="pf-v6-c-brand brand-mark" src="{{ static_url('img/mabc-mark.png') }}" width="208" height="208" alt=""></span>
            <span>EzySpeech User</span>
          </div>
        </div>
      </div>

      <!-- The masthead's content row is already a flex container, so the
           items sit in it directly; PatternFly's toolbar is for a page's own
           filter/action bar, not for this. -->
      <div class="pf-v6-c-masthead__content">
        <!-- setConnectionStatus() in user.js owns this class list and sets the
             label modifier that carries the state colour. -->
        <span class="pf-v6-c-label pf-m-orange connection-badge waiting" id="statusBadge"
              role="status" aria-live="polite">
          <span class="pf-v6-c-label__content">
            <span class="pf-v6-c-label__text" data-i18n="waiting">Waiting</span>
          </span>
        </span>

        <div class="header-search-desktop" id="headerSearchDesktop">
          <div class="pf-v6-c-text-input-group">
            <div class="pf-v6-c-text-input-group__main pf-m-icon">
              <span class="pf-v6-c-text-input-group__text">
                <span class="pf-v6-c-text-input-group__icon">%(search)s</span>
                <input class="pf-v6-c-text-input-group__text-input" type="search" id="searchInput"
                       aria-label="Search translations" data-i18n-placeholder="search"
                       placeholder="Search..." oninput="handleSearch()">
              </span>
            </div>
          </div>
        </div>

        <button class="pf-v6-c-button pf-m-plain mobile-search-toggle" type="button"
                id="mobileSearchToggle" aria-label="Toggle search"
                onclick="toggleMobileSearch()">%(search)s</button>
      </div>
    </header>

    <!-- Mobile search, revealed by the button above -->
    <div class="mobile-search-bar" id="mobileSearchBar">
      <div class="pf-v6-c-text-input-group">
        <div class="pf-v6-c-text-input-group__main pf-m-icon">
          <span class="pf-v6-c-text-input-group__text">
            <span class="pf-v6-c-text-input-group__icon">%(search)s</span>
            <input class="pf-v6-c-text-input-group__text-input" type="search" id="searchInputMobile"
                   aria-label="Search translations" data-i18n-placeholder="searchTranslations"
                   placeholder="Search translations..." oninput="handleSearch()">
          </span>
        </div>
      </div>
      <div class="search-results-info" id="searchResultsInfo" role="status" aria-live="polite" hidden></div>
    </div>

    <!-- Backdrop behind the sidebar on a phone -->
    <div class="pf-v6-c-backdrop sidebar-overlay" id="sidebarOverlay" aria-hidden="true"
         onclick="toggleMobileMenu()"></div>

    <!-- The sidebar holds settings, not navigation, so its contents are a
         form rather than a nav list. -->
    <div class="pf-v6-c-page__sidebar" id="sidebar" aria-label="Settings and controls">
      <div class="pf-v6-c-page__sidebar-body">
        <form class="pf-v6-c-form" onsubmit="return false;">
%(sidebar)s        </form>
      </div>
    </div>

    <div class="pf-v6-c-page__main-container">
      <main class="pf-v6-c-page__main" id="main-content" tabindex="-1">
        <section class="pf-v6-c-page__main-section pf-m-fill" aria-label="Translation list">
          <div class="pf-v6-c-page__main-body">
            <div class="content-header">
              <h1 class="pf-v6-c-title pf-m-xl" id="mainTitle">
                <span id="mainTitleText" data-i18n="liveTranslations">Live Translations</span>
                <span class="pf-v6-c-badge pf-m-read count-badge" id="itemCount"
                      aria-label="Translation count">0</span>
              </h1>
            </div>

            <div class="translation-list" id="translationsList" role="list">
              <div class="pf-v6-c-empty-state empty-state">
                <div class="pf-v6-c-empty-state__content">
                  <div class="pf-v6-c-empty-state__icon">%(comments)s</div>
                  <div class="pf-v6-c-empty-state__title">
                    <h2 class="pf-v6-c-empty-state__title-text" data-i18n="waitingTranslations">
                      Waiting for translations...</h2>
                  </div>
                  <div class="pf-v6-c-empty-state__body" data-i18n="waitingDesc">
                    Translations will appear here in real-time</div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  </div>

  <!-- Announcement banner, shown by user.js -->
  <div class="pf-v6-c-alert pf-m-info announcement-banner" id="announcementBanner" hidden>
    <div class="pf-v6-c-alert__icon" id="announcementIcon">%(info)s</div>
    <p class="pf-v6-c-alert__title" id="announcementMessage"></p>
    <div class="pf-v6-c-alert__action">
      <button class="pf-v6-c-button pf-m-plain" type="button" aria-label="Dismiss"
              onclick="dismissAnnouncement()">%(times)s</button>
    </div>
  </div>

  <!-- Room picker, filled in by the script at the end of this page -->
  <div class="pf-v6-c-backdrop app-modal room-picker-overlay" id="roomPickerOverlay" hidden>
    <div class="pf-v6-l-bullseye">
      <div class="pf-v6-c-modal-box pf-m-sm" role="dialog" aria-modal="true" aria-label="Choose a room">
        <header class="pf-v6-c-modal-box__header">
          <h1 class="pf-v6-c-modal-box__title">
            <span class="pf-v6-c-modal-box__title-text" data-i18n="chooseSession">Choose a session</span>
          </h1>
        </header>
        <div class="pf-v6-c-modal-box__body">
          <p class="pf-v6-c-modal-box__description room-picker-overlay__hint"
             data-i18n="chooseSessionHint">Pick the room you are in.</p>
          <ul class="pf-v6-c-list" id="roomPickerList" role="list"></ul>
        </div>
      </div>
    </div>
  </div>

  <div class="sync-indicator" id="syncIndicator" data-i18n="translationsUpdated"
       role="status" aria-live="polite">Translations updated</div>

%(about)s%(shortcuts)s%(welcome)s%(tour)s
  <button class="pf-v6-c-button pf-m-primary scroll-to-top" type="button" id="scrollToTopBtn"
          aria-label="Scroll to top" onclick="scrollToTop()">%(expand)s</button>

  <script>
    // PatternFly's expandable field group: the class on the group and the
    // button's aria-expanded are the two halves of its state.
    function toggleFieldGroup(button) {
      const group = button.closest('.pf-v6-c-form__field-group');
      if (!group) return;
      const open = group.classList.toggle('pf-m-expanded');
      button.setAttribute('aria-expanded', String(open));
    }
    window.toggleFieldGroup = toggleFieldGroup;

    // Persistent room switcher: navigates by reloading with ?room=
    window.userSwitchRoom = function (roomId) {
      if (!roomId || !/^[A-Za-z0-9][A-Za-z0-9_\\-]{0,63}$/.test(roomId)) return;
      if (roomId === (window.CURRENT_ROOM_ID || 'main')) return;
      const url = new URL(window.location.href);
      url.searchParams.set('room', roomId);
      window.location.href = url.toString();
    };

    (async function () {
      try {
        const catalog = window.sharedI18n || {};
        const lang = window.resolveDisplayLang
          ? window.resolveDisplayLang(localStorage.getItem('displayLanguage'))
          : 'en';
        const t = (k, fb) => (catalog[lang] && catalog[lang][k]) || (catalog.en && catalog.en[k]) || fb;

        const explicitRoom = new URLSearchParams(window.location.search).get('room');
        const resp = await fetch('/api/rooms');
        if (!resp.ok) return;
        const rooms = ((await resp.json()) || {}).rooms || [];
        if (rooms.length <= 1) return;

        // The sidebar switcher, whenever there is more than one room.
        const section = document.getElementById('userRoomSwitcherSection');
        const select = document.getElementById('userRoomSelect');
        if (section && select) {
          const current = explicitRoom || window.CURRENT_ROOM_ID || 'main';
          select.replaceChildren();
          rooms.forEach(function (r) {
            const opt = document.createElement('option');
            opt.value = r.room_id;
            opt.textContent = (r.display_name || r.room_id) + ' (' + (r.listeners || 0) + ')';
            if (r.room_id === current) opt.selected = true;
            select.appendChild(opt);
          });
          section.hidden = false;
        }

        // The picker, only on a first load that names no room.
        if (explicitRoom) return;
        const overlay = document.getElementById('roomPickerOverlay');
        const list = document.getElementById('roomPickerList');
        if (!overlay || !list) return;
        rooms.forEach(function (r) {
          const li = document.createElement('li');
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'pf-v6-c-button pf-m-tertiary pf-m-block room-picker-overlay__item';
          const name = document.createElement('span');
          name.className = 'pf-v6-c-button__text';
          name.textContent = (r.display_name || r.room_id) + ' \u00b7 '
            + t('listenersCount', '{n} listening').replace('{n}', r.listeners || 0);
          btn.appendChild(name);
          btn.onclick = function () {
            const url = new URL(window.location.href);
            url.searchParams.set('room', r.room_id);
            window.location.href = url.toString();
          };
          li.appendChild(btn);
          list.appendChild(li);
        });
        overlay.hidden = false;
      } catch (e) {
        console.warn('Room picker init failed:', e);
      }
    })();
  </script>

  <script src="{{ static_url('js/i18n.js') }}"></script>
  <script src="{{ static_url('js/user.js') }}"></script>
</body>

</html>
''' % {
        "sprite": sprite(),
        "bars": btn_icon("bars"),
        "search": icon("search"),
        "comments": icon("comments"),
        "info": icon("info-circle"),
        "times": btn_icon("times"),
        "expand": btn_icon("angle-down"),
        "sidebar": "".join(sidebar),
        "about": about_modal(),
        "shortcuts": modal("shortcutsModal", "shortcutsTitle", "shortcuts_title", "Keyboard Shortcuts",
                           shortcuts_body, close_fn="hideShortcuts()"),
        "welcome": modal("welcomeModal", "welcomeTitle", "welcome_title", "Welcome to EzySpeech",
                         welcome_body, welcome_footer, close_fn="hideWelcome()"),
        # user.js fills the tour's icon and title per step, so neither carries
        # a data-i18n key of its own.
        "tour": modal("tourModal", "tourTitle", None, "User Guide",
                      tour_body, tour_footer, close_fn="hideTour()", size="lg",
                      title_icon_id="tourStepIcon", title_text_id="tourStepTitle"),
    }


if __name__ == "__main__":
    out = ROOT / "app/templates/user.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote %s (%d bytes)" % (out.relative_to(ROOT), out.stat().st_size))
