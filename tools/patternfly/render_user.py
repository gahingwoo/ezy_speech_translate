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


def btn_icon(name):
    return '<span class="pf-v6-c-button__icon">%s</span>' % icon(name)


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


def sidebar_button(el_id, onclick, aria, icon_name, text_id, text, i18n_key=None, extra=""):
    """A full-width action in the sidebar. PatternFly's link button, which is
    what a text action in a side panel is, rather than a nav item: these do
    things, they do not navigate."""
    label = ('<span id="%s"%s>%s</span>' % (text_id, ' data-i18n="%s"' % i18n_key if i18n_key else "", text)
             if text_id else
             '<span%s>%s</span>' % (' data-i18n="%s"' % i18n_key if i18n_key else "", text))
    return ('      <div class="pf-v6-c-form__group">\n'
            '        <button class="pf-v6-c-button pf-m-link pf-m-inline sidebar-action" type="button"'
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


def modal(el_id, title_id, title_i18n, title_text, body, footer="", close_fn=None, title_extra=""):
    close = close_fn or ("hide" + el_id.replace("Modal", "").capitalize() + "()")
    # The backdrop closes on a click; a click on the box itself must not reach
    # it, which is what the app's own handlers already expected.
    outer = close.replace("()", "(event)")
    return '''  <div class="pf-v6-c-backdrop app-modal" id="%s" onclick="%s" hidden>
    <div class="pf-v6-l-bullseye">
      <div class="pf-v6-c-modal-box pf-m-md" role="dialog" aria-modal="true" aria-labelledby="%s"
           onclick="event.stopPropagation()">
        <div class="pf-v6-c-modal-box__close">
          <button class="pf-v6-c-button pf-m-plain" type="button" aria-label="Close" onclick="%s">%s</button>
        </div>
        <header class="pf-v6-c-modal-box__header">
          <h1 class="pf-v6-c-modal-box__title" id="%s">
            <span class="pf-v6-c-modal-box__title-text" data-i18n="%s">%s</span>
          </h1>
        </header>
        <div class="pf-v6-c-modal-box__body">
%s
        </div>%s
      </div>
    </div>
  </div>
''' % (el_id, outer, title_id, close, btn_icon("times"), title_id, title_i18n,
       title_text + title_extra, body, footer)


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
    sidebar.append('''    <section class="pf-v6-c-form__section sidebar-section">
      <h2 class="pf-v6-c-form__section-title" data-i18n="textToSpeech">Text-to-Speech</h2>
      <div class="pf-v6-c-form__group">
        <button class="pf-v6-c-button pf-m-primary pf-m-block" type="button" id="toggleTTS"
                aria-pressed="false" aria-label="Toggle text to speech" onclick="toggleTTS()">
          %s
          <span class="pf-v6-c-button__text" data-i18n="enableTTS">Enable TTS</span>
        </button>
      </div>
%s%s%s%s    </section>
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
    ))

    # Export
    sidebar.append('''    <section class="pf-v6-c-form__section sidebar-section">
      <h2 class="pf-v6-c-form__section-title" data-i18n="export">Export</h2>
%s      <div class="pf-v6-c-form__group">
        <button class="pf-v6-c-button pf-m-primary pf-m-block" type="button"
                aria-label="Download translations" onclick="exportData()">
          %s
          <span class="pf-v6-c-button__text" data-i18n="download">Download</span>
        </button>
      </div>
%s%s    </section>
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
    ))

    # Settings
    sidebar.append('''    <section class="pf-v6-c-form__section sidebar-section">
      <h2 class="pf-v6-c-form__section-title" data-i18n="settings">Settings</h2>
%s%s%s%s%s%s%s%s    </section>
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
         '        <button class="pf-v6-c-button pf-m-link pf-m-inline sidebar-action" type="button"'
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
    ))

    # Bible verses, behind the same Jinja flag as before
    sidebar.append('''    {%% if bible_detection_enabled %%}
    <section class="pf-v6-c-form__section sidebar-section" id="bibleSidebarSection" aria-label="Bible Verses">
      <h2 class="pf-v6-c-form__section-title" data-i18n="bibleVerses">Bible Verses</h2>
%s      <div class="pf-v6-c-form__group" id="bibleVerseToggleWrap">
%s        <p class="pf-v6-c-form__helper-text" id="bibleTransLoadingHint" hidden>
          <span data-i18n="bibleAutoMatched">Auto-matched to your language. Choose any Bible below.</span>
        </p>
      </div>
    </section>
    {%% endif %%}
''' % (
        sidebar_button("bibleVerseToggle", "toggleBibleVerse()", "Toggle Bible verse display",
                       "book", "bibleVerseText", "Show Bible Verses", "bibleVerseShow",
                       extra=' aria-pressed="false"'),
        form_group("Your Bible", "yourBible",
                   select("bibleTargetTranslation", "onBibleTranslationChange()",
                          "Select Bible translation for your language",
                          '<option value="" data-i18n="bibleLoading">— Loading... —</option>'),
                   "bibleTargetTranslation"),
    ))

    about_body = '''          <div class="pf-v6-c-content">
            <p data-i18n="tagline">Let language no longer stand in the way of connection</p>
            <h3 data-i18n="madeBy">Made by</h3>
            <p data-i18n="author">Ga Hing Woo</p>
          </div>
          <div class="about-links">
            <span data-i18n="feedback">Feedback</span>
          </div>'''

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

    tour_body = '''          <div class="tour-body" id="tourStepBody"></div>
          <div class="tour-dots" id="tourDots" role="tablist" aria-label="Tour progress"></div>'''
    tour_footer = '''
        <footer class="pf-v6-c-modal-box__footer">
          <button class="pf-v6-c-button pf-m-secondary" type="button" id="tourPrev" onclick="tourPrev()">
            <span class="pf-v6-c-button__text" data-i18n="tour_prev">Back</span>
          </button>
          <span class="tour-progress" id="tourProgress">1 / 1</span>
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

  <!-- Toasts. PatternFly's alert group in its toast position. -->
  <ul class="pf-v6-c-alert-group pf-m-toast toast-container" id="toastContainer" role="list"
      aria-live="polite" aria-atomic="true"></ul>

  <div class="pf-v6-c-page">
    <header class="pf-v6-c-masthead" role="banner">
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
            <span aria-hidden="true"><img src="{{ static_url('img/mabc-mark.png') }}" alt=""></span>
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
    <div class="mobile-search-bar" id="mobileSearchBar" hidden>
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
         onclick="toggleMobileMenu()" hidden></div>

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

  <!-- Room picker, filled in by user.js -->
  <div class="pf-v6-c-backdrop room-picker-overlay" id="roomPickerOverlay" hidden>
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
       role="status" aria-live="polite" hidden>Translations updated</div>

%(about)s%(shortcuts)s%(welcome)s%(tour)s
  <button class="pf-v6-c-button pf-m-primary scroll-to-top" type="button" id="scrollToTopBtn"
          aria-label="Scroll to top" onclick="scrollToTop()" hidden>%(expand)s</button>

  <script src="{{ static_url('js/i18n.js') }}"></script>
  <script src="{{ static_url('js/user.js') }}"></script>
</body>

</html>
''' % {
        "bars": btn_icon("bars"),
        "search": icon("search"),
        "comments": icon("comments"),
        "info": icon("info-circle"),
        "times": btn_icon("times"),
        "expand": btn_icon("angle-down"),
        "sidebar": "".join(sidebar),
        "about": modal("aboutModal", "aboutTitle", "aboutTitle", "EzySpeech", about_body,
                       close_fn="hideAbout()"),
        "shortcuts": modal("shortcutsModal", "shortcutsTitle", "shortcuts_title", "Keyboard Shortcuts",
                           shortcuts_body, close_fn="hideShortcuts()"),
        "welcome": modal("welcomeModal", "welcomeTitle", "welcome_title", "Welcome to EzySpeech",
                         welcome_body, welcome_footer, close_fn="hideWelcome()"),
        "tour": modal("tourModal", "tourTitle", "userGuide", "User Guide",
                      tour_body, tour_footer, close_fn="hideTour()",
                      title_extra='<span id="tourStepIcon" aria-hidden="true"></span>'
                                  '<span id="tourStepTitle"></span>'),
    }


if __name__ == "__main__":
    out = ROOT / "app/templates/user.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote %s (%d bytes)" % (out.relative_to(ROOT), out.stat().st_size))
