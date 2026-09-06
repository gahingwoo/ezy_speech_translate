#!/usr/bin/env python3
"""Generate app/templates/admin.html as PatternFly 6.

Written from a blank file against the real components, not edited out of the
old template. The old one is kept at tools/patternfly/backup/admin.html.orig
and is the source of the contract: every id, inline handler and data-i18n key
in it has to come out the other side, because admin.js is 78KB and finds its
controls by id.

    python3 tools/patternfly/render_admin.py
    python3 tools/patternfly/check_contract.py \\
        tools/patternfly/backup/admin.html.orig app/templates/admin.html

Layout, top to bottom:

    masthead   brand, connection state, room switcher, config, logout
    sidebar    the controls, as a PatternFly form
    main       the transcription list beside the edit panel, on a grid so the
               panel drops below the list on a narrow screen

Icons are inlined from tools/patternfly/icons.json, which
tools/patternfly/extract_icons.py pulls out of @patternfly/react-icons.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ICONS = json.loads((ROOT / "tools/patternfly/icons.json").read_text())


# ── helpers ───────────────────────────────────────────────────────────────

def icon(name, cls="pf-v6-svg"):
    i = ICONS[name]
    return ('<svg class="%s" viewBox="0 0 %d %d" fill="currentColor" '
            'aria-hidden="true" role="img" width="1em" height="1em">'
            '<path d="%s"/></svg>' % (cls, i["w"], i["h"], i["d"]))


def btn_icon(name, where="start"):
    return ('<span class="pf-v6-c-button__icon pf-m-%s">%s</span>'
            % (where, icon(name)))


# admin.js builds the toast alerts as HTML strings and cannot inline a
# 2,000-character path, so the icons it needs go in the page once as a sprite
# and it references them by id through svgIcon() — the helper of that name in
# admin.js.
SPRITE_ICONS = ("check-circle", "exclamation-circle", "exclamation-triangle",
                "info-circle", "times")


def sprite():
    parts = []
    for name in SPRITE_ICONS:
        i = ICONS[name]
        parts.append('    <symbol id="i-%s" viewBox="0 0 %d %d"><path d="%s"/></symbol>'
                     % (name, i["w"], i["h"], i["d"]))
    return ('  <svg class="pf-sprite" aria-hidden="true" focusable="false" width="0" height="0">\n'
            '%s\n  </svg>\n' % "\n".join(parts))


def i18n_attr(key):
    return ' data-i18n="%s"' % key if key else ""


def button(text, onclick, icon_name=None, variant="secondary", el_id=None,
           i18n=None, extra="", text_id=None, indent=10):
    """A PatternFly button. Icon before the label, both in their own spans,
    which is what the component's grid expects."""
    pad = " " * indent
    return ('%s<button class="pf-v6-c-button pf-m-%s" type="button"%s onclick="%s"%s>\n'
            '%s  %s<span class="pf-v6-c-button__text"%s%s>%s</span>\n'
            '%s</button>' % (
                pad, variant, ' id="%s"' % el_id if el_id else "", onclick, extra,
                pad, btn_icon(icon_name) if icon_name else "",
                ' id="%s"' % text_id if text_id else "", i18n_attr(i18n), text,
                pad))


def group(control, label=None, i18n=None, for_id=None, group_id=None,
          helper=None, indent=6):
    """PatternFly form group: label above, control below."""
    pad = " " * indent
    head = ""
    if label is not None:
        head = ('%s  <div class="pf-v6-c-form__group-label">\n'
                '%s    <label class="pf-v6-c-form__label"%s>\n'
                '%s      <span class="pf-v6-c-form__label-text"%s>%s</span>\n'
                '%s    </label>\n'
                '%s  </div>\n' % (pad, pad, ' for="%s"' % for_id if for_id else "",
                                  pad, i18n_attr(i18n), label, pad, pad))
    tail = ""
    if helper:
        tail = '%s  %s\n' % (pad, helper)
    return ('%s<div class="pf-v6-c-form__group"%s>\n%s'
            '%s  <div class="pf-v6-c-form__group-control">\n%s\n%s  </div>\n%s'
            '%s</div>\n' % (pad, ' id="%s"' % group_id if group_id else "", head,
                            pad, control, pad, tail, pad))


def select(el_id, options, aria, onchange=None, extra="", indent=10):
    pad = " " * indent
    return ('%s<span class="pf-v6-c-form-control">\n'
            '%s  <select id="%s" aria-label="%s"%s%s>%s</select>\n'
            '%s  <span class="pf-v6-c-form-control__utilities">\n'
            '%s    <span class="pf-v6-c-form-control__toggle-icon">%s</span>\n'
            '%s  </span>\n'
            '%s</span>' % (pad, pad, el_id, aria,
                           ' onchange="%s"' % onchange if onchange else "", extra,
                           options, pad, pad, icon("angle-down"), pad, pad))


def textarea(el_id, rows=3, placeholder=None, i18n_placeholder=None,
             disabled=False, extra="", indent=10):
    pad = " " * indent
    return ('%s<span class="pf-v6-c-form-control pf-m-textarea pf-m-resize-vertical%s">\n'
            '%s  <textarea id="%s" rows="%d"%s%s%s></textarea>\n'
            '%s</span>' % (
                pad, " pf-m-disabled" if disabled else "", pad, el_id, rows,
                ' placeholder="%s"' % placeholder if placeholder else "",
                ' data-i18n-placeholder="%s"' % i18n_placeholder if i18n_placeholder else "",
                (" disabled" if disabled else "") + extra, pad))


def text_input(el_id, kind="text", placeholder=None, extra="", indent=10):
    pad = " " * indent
    return ('%s<span class="pf-v6-c-form-control">\n'
            '%s  <input type="%s" id="%s"%s%s>\n'
            '%s</span>' % (pad, pad, kind, el_id,
                           ' placeholder="%s"' % placeholder if placeholder else "",
                           extra, pad))


def section(title, body, i18n=None, el_id=None):
    return ('    <section class="pf-v6-c-form__section sidebar-section"%s>\n'
            '      <h2 class="pf-v6-c-form__section-title"%s>%s</h2>\n'
            '%s'
            '    </section>\n' % (' id="%s"' % el_id if el_id else "",
                                  i18n_attr(i18n), title, body))


def dl_group(term, value, i18n=None, indent=12):
    pad = " " * indent
    return ('%s<div class="pf-v6-c-description-list__group">\n'
            '%s  <dt class="pf-v6-c-description-list__term">\n'
            '%s    <span class="pf-v6-c-description-list__text"%s>%s</span>\n'
            '%s  </dt>\n'
            '%s  <dd class="pf-v6-c-description-list__description">\n'
            '%s    <div class="pf-v6-c-description-list__text">%s</div>\n'
            '%s  </dd>\n'
            '%s</div>\n' % (pad, pad, pad, i18n_attr(i18n), term, pad, pad, pad,
                            value, pad, pad))


def label(el_id, text, colour=None, i18n=None, icon_text=None):
    """PatternFly label. admin.js replaces the class list and inner HTML of
    these outright, so what it writes has to match this shape."""
    return ('<span id="%s" class="pf-v6-c-label%s">'
            '<span class="pf-v6-c-label__content">%s'
            '<span class="pf-v6-c-label__text"%s>%s</span>'
            '</span></span>' % (
                el_id, " pf-m-%s" % colour if colour else "",
                '<span class="pf-v6-c-label__icon">%s</span>' % icon_text if icon_text else "",
                i18n_attr(i18n), text))


def modal(el_id, title, body, close_fn, footer="", size="md", i18n=None,
          icon_name=None, description=None, backdrop_onclick=None):
    """A dialog. The backdrop centres the box itself rather than wrapping it in
    a bullseye, because admin.js closes on `event.target === this` and a
    wrapper would become the target instead of the backdrop."""
    title_id = el_id + "Title"
    desc = ""
    if description:
        desc = ('        <p class="pf-v6-c-modal-box__description">%s</p>\n'
                % description)
    return '''  <div class="pf-v6-c-backdrop app-modal" id="%s" onclick="%s">
    <div class="pf-v6-c-modal-box pf-m-%s" role="dialog" aria-modal="true"
         aria-labelledby="%s">
      <div class="pf-v6-c-modal-box__close">
        <button class="pf-v6-c-button pf-m-plain about-close" type="button"
                aria-label="Close" onclick="%s">%s</button>
      </div>
      <header class="pf-v6-c-modal-box__header">
        <h1 class="pf-v6-c-modal-box__title%s" id="%s">%s
          <span class="pf-v6-c-modal-box__title-text"%s>%s</span>
        </h1>
      </header>
      <div class="pf-v6-c-modal-box__body">
%s%s
      </div>%s
    </div>
  </div>
''' % (el_id, backdrop_onclick or close_fn, size, title_id, close_fn,
       btn_icon("times"),
       " pf-m-icon" if icon_name else "", title_id,
       '\n          <span class="pf-v6-c-modal-box__title-icon">%s</span>' % icon(icon_name)
       if icon_name else "",
       i18n_attr(i18n), title, desc, body, footer)


def footer(*buttons):
    return ('\n      <footer class="pf-v6-c-modal-box__footer">\n%s\n      </footer>'
            % "\n".join(buttons))


# ── option lists, carried over unchanged ──────────────────────────────────

SOURCE_LANGS = (
    '<option value="en-US" data-i18n="englishUS">English (US)</option>'
    '<option value="en-GB" data-i18n="englishUK">English (UK)</option>'
    '<option value="zh-CN" data-i18n="chineseMandarin">中文 (普通话)</option>'
    '<option value="yue-Hant-HK">粵語</option>'
    '<option value="ja-JP">日本語</option>'
    '<option value="ko-KR">한국어</option>'
    '<option value="es-ES">Español</option>'
    '<option value="fr-FR">Français</option>'
    '<option value="de-DE">Deutsch</option>')

DISPLAY_LANGS = (
    '<option value="">Auto</option>'
    '<option value="en">English</option><option value="zh">简体中文</option>'
    '<option value="yue">粵語</option><option value="zh-tw">繁體中文</option>'
    '<option value="ja">日本語</option><option value="ko">한국어</option>'
    '<option value="es">Español</option><option value="fr">Français</option>'
    '<option value="de">Deutsch</option><option value="ru">Русский</option>'
    '<option value="ar">العربية</option><option value="pt">Português</option>'
    '<option value="it">Italiano</option><option value="nl">Nederlands</option>'
    '<option value="pl">Polski</option><option value="tr">Türkçe</option>'
    '<option value="vi">Tiếng Việt</option><option value="th">ไทย</option>'
    '<option value="id">Bahasa Indonesia</option>'
    '<option value="ms">Bahasa Melayu</option>'
    '<option value="hi">हिन्दी</option><option value="ta">தமிழ்</option>')

# The glossary picker shows the code because an entry is stored against it.
GLOSSARY_LANGS = (
    '<option value="*">(all langs)</option>'
    '<option value="zh">zh — 简体中文</option>'
    '<option value="zh-tw">zh-tw — 繁體中文</option>'
    '<option value="yue">yue — 粵語</option>'
    '<option value="en">en — English</option>'
    '<option value="id">id — Bahasa Indonesia</option>'
    '<option value="ms">ms — Bahasa Melayu</option>'
    '<option value="ja">ja — 日本語</option>'
    '<option value="ko">ko — 한국어</option>'
    '<option value="th">th — ภาษาไทย</option>'
    '<option value="vi">vi — Tiếng Việt</option>'
    '<option value="hi">hi — हिन्दी</option>'
    '<option value="ar">ar — العربية</option>'
    '<option value="ta">ta — தமிழ்</option>'
    '<option value="es">es — Español</option>'
    '<option value="pt">pt — Português</option>'
    '<option value="fr">fr — Français</option>'
    '<option value="de">de — Deutsch</option>'
    '<option value="it">it — Italiano</option>'
    '<option value="nl">nl — Nederlands</option>'
    '<option value="ru">ru — Русский</option>'
    '<option value="pl">pl — Polski</option>'
    '<option value="tr">tr — Türkçe</option>')

QR_LANGS = (
    '<option value="">— No preset (default) —</option>'
    '<option value="zh">简体中文 (Simplified Chinese)</option>'
    '<option value="zh-tw">繁體中文 (Traditional Chinese)</option>'
    '<option value="yue">粵語 (Cantonese)</option>'
    '<option value="en">English</option>'
    '<option value="id">Bahasa Indonesia (Indonesian)</option>'
    '<option value="ms">Bahasa Melayu (Malay)</option>'
    '<option value="ja">日本語 (Japanese)</option>'
    '<option value="ko">한국어 (Korean)</option>'
    '<option value="th">ภาษาไทย (Thai)</option>'
    '<option value="vi">Tiếng Việt (Vietnamese)</option>'
    '<option value="hi">हिन्दी (Hindi)</option>'
    '<option value="ar">العربية (Arabic)</option>'
    '<option value="ta">தமிழ் (Tamil)</option>'
    '<option value="es">Español (Spanish)</option>'
    '<option value="pt">Português (Portuguese)</option>'
    '<option value="fr">Français (French)</option>'
    '<option value="de">Deutsch (German)</option>'
    '<option value="it">Italiano (Italian)</option>'
    '<option value="nl">Nederlands (Dutch)</option>'
    '<option value="ru">Русский (Russian)</option>'
    '<option value="pl">Polski (Polish)</option>'
    '<option value="tr">Türkçe (Turkish)</option>')

# The interface-language select carries its whole behaviour in the attribute,
# as it did before; moving it into admin.js would be a change of a different
# kind from this one.
DISPLAY_LANG_ONCHANGE = (
    "(function(el){ const v = el.value; if(!v){ localStorage.removeItem('displayLanguage'); "
    "if(window.applyDisplayLanguage) window.applyDisplayLanguage(); } else { "
    "if(window.changeDisplayLanguage) window.changeDisplayLanguage(v); else { "
    "localStorage.setItem('displayLanguage', v); "
    "if(window.applyDisplayLanguage) window.applyDisplayLanguage(); } } })(this)")


# ── the sidebar ───────────────────────────────────────────────────────────

def audio_section():
    body = (
        group(select("sourceLangSelect", SOURCE_LANGS, "Source language",
                     "changeSourceLanguage()"),
              "Source Language", "sourceLanguage", "sourceLangSelect")
        + group(select("deviceSelect", '<option data-i18n="loading">Loading...</option>',
                       "Audio device"),
                "Audio Device", "audioDevice", "deviceSelect")
        + '''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control">
%s
          <span class="pf-v6-c-label pf-m-blue auto-restart-badge" id="autoRestartBadge"
                style="display: none;">
            <span class="pf-v6-c-label__content">
              <span class="pf-v6-c-label__icon">%s</span>
              <span class="pf-v6-c-label__text" data-i18n="autoRestartEnabled">Auto-restart enabled</span>
            </span>
          </span>
        </div>
      </div>
''' % (button("Start Recording", "toggleRecording()", "microphone", "primary",
              el_id="recordBtn", i18n="startRecording",
              extra=' aria-pressed="false"'),
       icon("sync-alt"))
        + group('''          <div class="interim-display inactive" id="interimDisplay"
               role="status" aria-live="polite">
            <span id="interimText" data-i18n="waitingForSpeech">Waiting for speech...</span>
          </div>''',
                "Recognizing...", "recognizing", "interimDisplay"))
    return section("Audio Controls", body, "audioControls")


def actions_section():
    body = '''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control sidebar-actions">
%s
%s
%s
%s
%s
%s
          <input type="file" id="importFileInput" accept=".json" hidden
                 onchange="handleImportFile(event)">
        </div>
      </div>
''' % (
        button("Add", "addNewItem()", "plus", "primary", i18n="add"),
        button("Edit", "editSelected()", "edit", "secondary", i18n="edit"),
        button("Delete", "deleteSelected()", "trash", "danger", i18n="delete"),
        button("Clear All", "clearHistory()", "times", "secondary", i18n="clearAll"),
        button("Export", "exportData()", "download", "secondary", i18n="export"),
        button("Import", "document.getElementById('importFileInput').click()",
               "upload", "secondary", i18n="import"),
    )
    return section("Actions", body, "actions")


def settings_section():
    body = (
        group(select("displayLanguage", DISPLAY_LANGS, "Interface language",
                     DISPLAY_LANG_ONCHANGE),
              "Interface Language", "displayLanguage", "displayLanguage")
        + '''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control sidebar-links">
%s
%s
%s
        </div>
      </div>
''' % (
            # themeIcon and themeText are written by updateThemeUI(), so the
            # icon is a text node here rather than an inline SVG.
            ('          <button class="pf-v6-c-button pf-m-secondary pf-m-block sidebar-action" type="button"\n'
             '                  aria-label="Toggle theme" onclick="toggleTheme(); closeMobileMenu();">\n'
             '            <span class="pf-v6-c-button__icon pf-m-start" aria-hidden="true"\n'
             '                  id="themeIcon">%s%s</span>\n'
             '            <span class="pf-v6-c-button__text" id="themeText" data-i18n="darkMode">Dark Mode</span>\n'
             '          </button>' % (icon("moon", "pf-v6-svg icon-moon"),
                                     icon("sun", "pf-v6-svg icon-sun"))),
            button("Keyboard Shortcuts", "showShortcuts(); closeMobileMenu();",
                   "keyboard", "secondary pf-m-block sidebar-action", i18n="shortcuts_title",
                   extra=' aria-label="Keyboard shortcuts"'),
            button("About", "showAbout(); closeMobileMenu();", "info-circle",
                   "secondary pf-m-block sidebar-action", i18n="about", extra=' aria-label="About"'),
        ))
    return section("Settings", body, "settings")


def tts_cache_section():
    stats = ('''          <dl class="pf-v6-c-description-list pf-m-horizontal pf-m-compact"
              id="ttsCacheStats">
%s%s          </dl>'''
             % (dl_group("Items", '<strong id="cache-items">0/1000</strong>'),
                dl_group("Memory", '<strong id="cache-memory">0.00MB/1000MB</strong>')))
    body = ('''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control">
          <div class="pf-v6-c-card pf-m-compact" id="ttsCacheContainer" aria-label="TTS Cache">
            <div class="pf-v6-c-card__body">
%s
            </div>
          </div>
        </div>
      </div>
      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control sidebar-actions">
%s
%s
        </div>
      </div>
''' % (stats,
       button("Refresh", "refreshTTSCacheStats()", "sync-alt", "secondary"),
       button("Clear", "clearTTSCache()", "trash", "danger")))
    return section("TTS Cache", body)


def bible_section():
    body = group(
        select("adminBibleSourceSelect", '<option value="">— Loading... —</option>',
               "Bible source translation", "saveBibleSourceTranslation()",
               extra=' title="Bible translation shown alongside the original-language'
                     ' caption. Choose based on the language being spoken."'),
        "Source Translation", None, "adminBibleSourceSelect",
        helper='<p class="pf-v6-c-form__helper-text" id="adminBibleSaveStatus"'
               ' role="status" aria-live="polite"></p>')
    return section("Bible", body, el_id="bibleAdminSection")


def announcement_section():
    body = (
        group(textarea("announcementText", 3,
                       "Type announcement to all viewers..."),
              "Message", None, "announcementText")
        + group(select("announcementDuration",
                       '<option value="5000">5 seconds</option>'
                       '<option value="10000" selected>10 seconds</option>'
                       '<option value="30000">30 seconds</option>'
                       '<option value="60000">1 minute</option>'
                       '<option value="0">Until dismissed</option>',
                       "Announcement duration"),
                "Duration", None, "announcementDuration")
        + group(select("announcementType",
                       '<option value="info" selected>Info</option>'
                       '<option value="success">Success</option>'
                       '<option value="warning">Warning</option>'
                       '<option value="danger">Urgent</option>',
                       "Announcement type"),
                "Type", None, "announcementType")
        + '''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control">
%s
        </div>
      </div>
''' % button("Send to All Viewers", "sendAnnouncement()", "paper-plane",
             "primary pf-m-block"))
    return section("Announcement", body, el_id="announcementSection")


def qr_section():
    body = (
        group(select("qrRoomSelect", '<option value="">— Auto (current room) —</option>',
                     "QR room"),
              "Room", None, "qrRoomSelect")
        + group(select("qrLangSelect", QR_LANGS, "QR language preset"),
                "Language preset", None, "qrLangSelect")
        + '''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control">
%s
          <div class="qr-output" id="qrOutput" style="display:none;">
            <div class="qr-canvas" id="qrCanvas"></div>
            <p class="qr-url" id="qrUrlLabel"></p>
%s
          </div>
        </div>
      </div>
''' % (button("Generate QR Code", "generateQR()", "qrcode", "primary pf-m-block"),
       button("Download PNG", "downloadQR()", "download", "secondary pf-m-block",
              indent=12)))
    return section("Audience QR Code", body, el_id="qrSection")


# ── the edit panel ────────────────────────────────────────────────────────

def edit_card():
    return '''        <div class="pf-v6-c-card">
          <div class="pf-v6-c-card__header">
            <div class="pf-v6-c-card__header-main">
              <h2 class="pf-v6-c-card__title-text" data-i18n="editAndCorrect">Edit &amp; Correct</h2>
            </div>
          </div>
          <div class="pf-v6-c-card__body">
            <form class="pf-v6-c-form" onsubmit="return false;">
%s%s            </form>
          </div>
          <div class="pf-v6-c-card__footer">
%s
%s
          </div>
        </div>
''' % (
        group(textarea("originalText", 3, disabled=True, indent=16),
              "Original", "original", "originalText", indent=14),
        group(textarea("correctedText", 4, "Select an item to edit...",
                       "selectItemToEdit", indent=16),
              "Corrected (Edit Here)", "correctedLabel", "correctedText", indent=14),
        button("Save", "saveCorrection()", "save", "primary", i18n="save", indent=12),
        button("Cancel", "cancelCorrection()", "times", "link", i18n="cancel", indent=12),
    )


def system_info_card():
    rows = (
        dl_group("Clients", '<strong id="sys-clients">0</strong>', "clients")
        + dl_group("Transcripts", '<strong id="sys-transcriptions">0</strong>',
                   "transcriptions")
        + dl_group("Recording", label("sys-recording", "Stopped", None, "stopped"), "recording")
        + dl_group("Language",
                   '<span id="sys-language" class="pf-v6-c-label pf-m-blue">'
                   '<span class="pf-v6-c-label__content">'
                   '<span class="pf-v6-c-label__text mono">en-US</span>'
                   '</span></span>', "language")
    )
    return '''        <div class="pf-v6-c-card" id="systemInfo" aria-label="System Info">
          <div class="pf-v6-c-card__header">
            <div class="pf-v6-c-card__header-main">
              <h2 class="pf-v6-c-card__title-text" data-i18n="systemInfo">System Info</h2>
            </div>
          </div>
          <div class="pf-v6-c-card__body">
            <dl class="pf-v6-c-description-list pf-m-horizontal pf-m-compact">
%s            </dl>
          </div>
        </div>
''' % rows


def analytics_card():
    rows = (
        dl_group("Duration", '<strong id="stat-duration">—</strong>')
        + dl_group("Peak Viewers", '<strong id="stat-peak">0</strong>')
        + dl_group("Total Words", '<strong id="stat-words">0</strong>')
        + dl_group("Translations", '<strong id="stat-translations">0</strong>')
        + dl_group("Bible Refs", '<strong id="stat-bible-refs">0</strong>')
        + dl_group("DB Entries", label("stat-db", "—"))
    )
    return '''        <div class="pf-v6-c-card" id="analyticsSection">
          <div class="pf-v6-c-card__header">
            <div class="pf-v6-c-card__header-main">
              <h2 class="pf-v6-c-card__title-text">Session Stats</h2>
            </div>
          </div>
          <div class="pf-v6-c-card__body" id="analyticsCard" aria-label="Session Analytics">
            <dl class="pf-v6-c-description-list pf-m-horizontal pf-m-compact">
%s            </dl>
          </div>
          <div class="pf-v6-c-card__footer">
%s
          </div>
        </div>
''' % (rows, button("Refresh Stats", "refreshAnalytics()", "sync-alt",
                    "secondary pf-m-block", indent=12))


def empty_state(indent=16):
    """The list is empty on load and again whenever admin.js clears it, so the
    same markup is rendered inline and into a <template> it can clone."""
    pad = " " * indent
    return ('%s<div class="pf-v6-c-empty-state">\n'
            '%s  <div class="pf-v6-c-empty-state__content">\n'
            '%s    <div class="pf-v6-c-empty-state__icon">%s</div>\n'
            '%s    <div class="pf-v6-c-empty-state__title">\n'
            '%s      <h2 class="pf-v6-c-empty-state__title-text"\n'
            '%s          data-i18n="noTranscriptionsYet">No transcriptions yet</h2>\n'
            '%s    </div>\n'
            '%s    <div class="pf-v6-c-empty-state__body" data-i18n="startRecordingHelp">\n'
            '%s      Start recording to see transcriptions</div>\n'
            '%s  </div>\n'
            '%s</div>\n' % (pad, pad, pad, icon("comments"), pad, pad, pad, pad,
                            pad, pad, pad, pad))


# ── dialogs ───────────────────────────────────────────────────────────────

def room_manager():
    glossary_form = '''          <div class="glossary-form">
%s
%s
%s
%s
%s
          </div>
          <div class="pf-v6-c-check glossary-flag">
            <input class="pf-v6-c-check__input" type="checkbox" id="glossaryCaseSensitive">
            <label class="pf-v6-c-check__label" for="glossaryCaseSensitive">Case sensitive</label>
          </div>
          <div class="glossary-table-wrap">
            <table class="pf-v6-c-table pf-m-compact pf-m-grid-md" role="grid"
                   aria-label="Glossary entries">
              <thead class="pf-v6-c-table__thead">
                <tr class="pf-v6-c-table__tr">
                  <th class="pf-v6-c-table__th" scope="col">Scope</th>
                  <th class="pf-v6-c-table__th" scope="col">Source</th>
                  <th class="pf-v6-c-table__th" scope="col">Lang</th>
                  <th class="pf-v6-c-table__th" scope="col">Translation</th>
                  <th class="pf-v6-c-table__th" scope="col">Flags</th>
                  <th class="pf-v6-c-table__th" scope="col"><span class="pf-v6-screen-reader">Remove</span></th>
                </tr>
              </thead>
              <tbody class="pf-v6-c-table__tbody" id="glossaryTableBody"></tbody>
            </table>
          </div>''' % (
        text_input("glossarySource", placeholder="Source term (e.g. Yahweh)",
                   extra=' maxlength="200" aria-label="Source term"', indent=12),
        select("glossaryLang", GLOSSARY_LANGS, "Target language", indent=12),
        text_input("glossaryTranslation", placeholder="Translation (e.g. 耶和华)",
                   extra=' maxlength="500" aria-label="Translation"', indent=12),
        select("glossaryScope",
               '<option value="">(global)</option>'
               '<option id="glossaryScopeCurrent" value=""></option>',
               "Glossary scope", indent=12),
        button("Add", "addGlossaryEntry()", "plus", "primary", indent=12),
    )

    body = '''          <div class="room-toolbar">
%s
%s
%s
%s
          </div>
          <hr class="pf-v6-c-divider" />
          <h2 class="pf-v6-c-title pf-m-md glossary-heading">Glossary (forced translations)</h2>
          <p class="pf-v6-c-form__helper-text">Entries scoped to a room override globals.
            The source term is preserved exactly during translation.</p>
%s
''' % (
        select("roomSelect", "", "Select room", indent=12),
        button("Switch", "switchRoom(document.getElementById('roomSelect').value)",
               None, "primary", indent=12),
        button("New", "createRoom()", "plus", "secondary", indent=12),
        ('            <button class="pf-v6-c-button pf-m-plain" type="button"\n'
         '                    title="Delete selected room" aria-label="Delete selected room"\n'
         "                    onclick=\"deleteRoom(document.getElementById('roomSelect').value)\">%s</button>"
         % btn_icon("trash")),
        glossary_form,
    )
    return modal("roomManagerModal", "Rooms", body, "closeRoomManager()", size="lg",
                 icon_name="users",
                 backdrop_onclick="if(event.target===this)closeRoomManager()",
                 footer=footer(button("Close", "closeRoomManager()", None,
                                      "secondary", indent=8)))


def config_password_modal():
    body = text_input("configPasswordInput", "password", "Admin password",
                      extra=' aria-label="Admin password"'
                            " onkeydown=\"if(event.key==='Enter')confirmConfigPassword()\"")
    return modal("configPasswordModal", "Confirm identity", body,
                 "closeConfigPasswordGate()", size="sm", icon_name="lock",
                 description="Enter your admin password to access the config editor.",
                 backdrop_onclick="if(event.target===this)closeConfigPasswordGate()",
                 footer=footer(
                     button("Cancel", "closeConfigPasswordGate()", None, "link", indent=8),
                     button("Confirm", "confirmConfigPassword()", None, "primary", indent=8)))


def config_editor_modal():
    body = '''          <span class="pf-v6-c-form-control pf-m-textarea config-editor">
            <textarea id="configEditorTextarea" spellcheck="false"
                      aria-label="config.yaml" placeholder="Loading…"></textarea>
          </span>
          <div class="pf-v6-c-alert pf-m-warning pf-m-inline config-warning">
            <div class="pf-v6-c-alert__icon">%s</div>
            <p class="pf-v6-c-alert__title">Some changes (ports, secrets) only take effect
              after restarting the server.</p>
          </div>''' % icon("exclamation-triangle")
    return modal("configEditorModal", "Edit config.yaml", body,
                 "closeConfigEditor()", size="lg", icon_name="cog",
                 description="Sensitive values (passwords, secrets) appear as *** and "
                             "remain untouched on save.",
                 backdrop_onclick="if(event.target===this)closeConfigEditor()",
                 footer=footer(
                     button("Cancel", "closeConfigEditor()", None, "link", indent=8),
                     button("Save", "saveConfigEditor()", None, "primary", indent=8)))


def recording_lock_modal():
    body = '''          <div class="pf-v6-c-alert pf-m-warning pf-m-inline">
            <div class="pf-v6-c-alert__icon">%s</div>
            <p class="pf-v6-c-alert__title">
              <strong id="recordingLockOwner">Another admin</strong> is currently recording
              in this room.</p>
          </div>
%s''' % (icon("exclamation-triangle"),
         text_input("recordingLockPassword", "password", "Admin password",
                    extra=' aria-label="Admin password"'))
    return modal("recordingLockModal", "Room already recording", body,
                 "closeRecordingLock()", size="sm", icon_name="lock",
                 description="Enter your admin password to force-stop the current "
                             "recording and take over.",
                 backdrop_onclick="if(event.target===this)closeRecordingLock()",
                 footer=footer(
                     button("Cancel", "closeRecordingLock()", None, "link", indent=8),
                     button("Force takeover", "confirmForceRecording()", None,
                            "danger", indent=8)))


def about_modal():
    body = '''          <div class="pf-v6-c-content">
            <p><strong>Real-time Speech Transcription</strong></p>
            <p>Let language no longer stand in the way of connection</p>
            <h3>Made by</h3>
            <p>Ga Hing Woo</p>
          </div>
          <div class="about-links">
            <a class="pf-v6-c-button pf-m-link" href="https://github.com/gahingwoo/ezy_speech_translate"
               rel="noopener noreferrer" target="_blank">
              %s<span class="pf-v6-c-button__text">GitHub</span>
            </a>
            <a class="pf-v6-c-button pf-m-link" href="https://github.com/gahingwoo/ezy_speech_translate/issues/new/choose"
               rel="noopener noreferrer" target="_blank">
              %s<span class="pf-v6-c-button__text">Feedback</span>
            </a>
          </div>
          <p class="pf-v6-c-form__helper-text about-version">v3.3.0 · Open Source · MIT License</p>''' % (
        btn_icon("share-alt"), btn_icon("comments"))
    return modal("aboutModal", "EzySpeech", body, "hideAbout()", size="sm",
                 backdrop_onclick="hideAbout(event)")


def shortcuts_modal():
    rows = "".join(
        dl_group(term, "<kbd>%s</kbd>" % keys, key)
        for term, keys, key in (
            ("Show this help", "?", "shortcuts_help"),
            ("Close dialog / menu", "Esc", "shortcuts_close"),
            ("Toggle recording", "Ctrl/⌘ + R", "adminShortcut_record"),
            ("Save correction", "Ctrl/⌘ + S", "adminShortcut_save"),
        ))
    body = ('          <dl class="pf-v6-c-description-list pf-m-horizontal">\n'
            '%s          </dl>' % rows)
    return modal("shortcutsModal", "Keyboard Shortcuts", body, "hideShortcuts()",
                 size="sm", i18n="shortcuts_title", icon_name="keyboard",
                 backdrop_onclick="hideShortcuts(event)")


def input_modal():
    body = '''          <p id="inputModalLabel" data-i18n="addManualLabel">Enter transcription text:</p>
%s''' % textarea("inputModalField", 3)
    return modal("inputModal", "Add Transcription", body, "hideInputModal()",
                 size="sm", i18n="addManualTitle", icon_name="edit",
                 backdrop_onclick="hideInputModal(event)",
                 footer=footer(
                     button("Cancel", "hideInputModal()", None, "link", i18n="cancel", indent=8),
                     button("OK", "__inputModalConfirm()", None, "primary", i18n="ok", indent=8)))


def export_modal():
    def choice(fmt, desc, key):
        return ('          <button class="pf-v6-c-button pf-m-secondary pf-m-block export-choice"\n'
                '                  type="button" onclick="__doExport(\'%s\')">\n'
                '            <span class="pf-v6-c-button__text"><strong>%s</strong>\n'
                '              <span data-i18n="%s">%s</span></span>\n'
                '          </button>' % (fmt, fmt.upper(), key, desc))

    body = ('          <p data-i18n="exportChoose">Choose a format:</p>\n'
            '          <div class="export-choices">\n%s\n%s\n%s\n          </div>' % (
                choice("txt", "Plain text", "exportTxtDesc"),
                choice("json", "Structured data", "exportJsonDesc"),
                choice("srt", "Subtitle file", "exportSrtDesc")))
    return modal("exportModal", "Export Transcriptions", body, "hideExportModal()",
                 size="sm", i18n="exportTitle", icon_name="file-export",
                 backdrop_onclick="hideExportModal(event)")


# The dialog glue that lived in the template before, unchanged in behaviour.
# It belongs to the page rather than to admin.js, which never calls into it.
PAGE_SCRIPT = '''  <script>
    function openRoomManager() {
      document.getElementById('roomManagerModal').classList.add('modal-overlay--open');
      const optCur = document.getElementById('glossaryScopeCurrent');
      optCur.value = window.CURRENT_ROOM_ID || 'main';
      optCur.textContent = '(this room: ' + (window.CURRENT_ROOM_ID || 'main') + ')';
      if (typeof refreshRoomDropdown === 'function') refreshRoomDropdown();
      if (typeof renderGlossaryTable === 'function') renderGlossaryTable();
    }
    function closeRoomManager() {
      document.getElementById('roomManagerModal').classList.remove('modal-overlay--open');
    }
    function openConfigPasswordGate() {
      document.getElementById('configPasswordModal').classList.add('modal-overlay--open');
      const inp = document.getElementById('configPasswordInput');
      if (inp) { inp.value = ''; setTimeout(() => inp.focus(), 50); }
    }
    function closeConfigPasswordGate() {
      document.getElementById('configPasswordModal').classList.remove('modal-overlay--open');
      const inp = document.getElementById('configPasswordInput');
      if (inp) inp.value = '';
    }
    function openConfigEditor() {
      const ta = document.getElementById('configEditorTextarea');
      ta.value = 'Loading…';
      document.getElementById('configEditorModal').classList.add('modal-overlay--open');
      if (typeof loadConfigEditor === 'function') loadConfigEditor();
    }
    function closeConfigEditor() {
      document.getElementById('configEditorModal').classList.remove('modal-overlay--open');
    }
    function closeRecordingLock() {
      document.getElementById('recordingLockModal').classList.remove('modal-overlay--open');
      const pw = document.getElementById('recordingLockPassword');
      if (pw) pw.value = '';
    }
    window.openRoomManager = openRoomManager;
    window.closeRoomManager = closeRoomManager;
    window.openConfigPasswordGate = openConfigPasswordGate;
    window.closeConfigPasswordGate = closeConfigPasswordGate;
    window.openConfigEditor = openConfigEditor;
    window.closeConfigEditor = closeConfigEditor;
    window.closeRecordingLock = closeRecordingLock;
  </script>
'''


def build():
    sidebar = (audio_section() + actions_section() + settings_section()
               + tts_cache_section() + bible_section() + announcement_section()
               + qr_section())

    dialogs = (room_manager() + config_password_modal() + config_editor_modal()
               + recording_lock_modal() + about_modal() + shortcuts_modal()
               + input_modal() + export_modal())

    return '''<!DOCTYPE html>
<!-- Generated by tools/patternfly/render_admin.py. Edit that, not this. -->
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta content="width=device-width, initial-scale=1.0" name="viewport">
  <title>EzySpeech - Admin Panel</title>
  <meta data-i18n-meta="metaDescription" name="description"
        content="Admin panel for managing EzySpeech server and live translations">
  <!-- The CSP is set by the server from config.server.external_url. -->
  <!-- Favicon will be set by OEM loader -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
  <!-- PatternFly carries Red Hat Text, Display and Mono itself, so the fonts
       no longer come from Google. -->
  <link href="{{ static_url('patternfly/patternfly.css') }}" rel="stylesheet">
  <link href="{{ static_url('css/admin.css') }}" rel="stylesheet">
  <script src="{{ static_url('js/oem-loader.js') }}"></script>
</head>

<body data-theme="light" data-page="admin">
  <a class="pf-v6-c-skip-to-content pf-v6-c-button pf-m-primary" href="#main-content">Skip to content</a>

%(sprite)s
  <!-- Toasts. PatternFly's alert group in its toast position; admin.js fills it. -->
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
            <span>EzySpeech Admin</span>
          </div>
        </div>
      </div>

      <div class="pf-v6-c-masthead__content">
        <!-- updateStatus() in admin.js replaces this class list outright, so
             what it writes and what is written here have to agree. -->
        <span class="pf-v6-c-label pf-m-red connection-badge offline" id="statusBadge"
              role="status" aria-live="polite">
          <span class="pf-v6-c-label__content">
            <span class="pf-v6-c-label__icon">%(bullseye)s</span>
            <span class="pf-v6-c-label__text" data-i18n="offline">Disconnected</span>
          </span>
        </span>

        <div class="room-switcher">
          <span class="pf-v6-c-label pf-m-outline" title="Current room">
            <span class="pf-v6-c-label__content">
              <span class="pf-v6-c-label__icon">%(users)s</span>
              <span class="pf-v6-c-label__text" id="currentRoomLabel">main</span>
            </span>
          </span>
%(manage)s
        </div>

%(config)s
%(logout)s
      </div>
    </header>

    <!-- Backdrop behind the sidebar on a phone -->
    <div class="pf-v6-c-backdrop sidebar-overlay" id="sidebarOverlay" aria-hidden="true"
         onclick="toggleMobileMenu()"></div>

    <!-- The sidebar holds controls, not navigation, so its contents are a
         form rather than a nav list. -->
    <div class="pf-v6-c-page__sidebar" id="sidebar" aria-label="Controls and settings">
      <div class="pf-v6-c-page__sidebar-body">
        <form class="pf-v6-c-form" onsubmit="return false;">
%(sidebar)s        </form>
      </div>
    </div>

    <div class="pf-v6-c-page__main-container">
      <main class="pf-v6-c-page__main" id="main-content" tabindex="-1">
        <section class="pf-v6-c-page__main-section pf-m-fill">
          <div class="pf-v6-l-grid pf-m-gutter">

            <div class="pf-v6-l-grid__item pf-m-12-col pf-m-8-col-on-lg">
              <div class="content-header">
                <h1 class="pf-v6-c-title pf-m-xl">
                  <span data-i18n="liveTranscriptions">Transcriptions</span>
                  <span class="pf-v6-c-badge pf-m-read" id="itemCount"
                        aria-label="Transcription count">0</span>
                </h1>
                <p class="pf-v6-c-form__helper-text drag-hint">
                  %(grip)s <span data-i18n="dragToReorder">Drag to reorder</span>
                </p>
              </div>

              <div class="transcription-list" id="transcriptionsList" role="list">
%(empty)s              </div>
            </div>

            <div class="pf-v6-l-grid__item pf-m-12-col pf-m-4-col-on-lg edit-panel">
%(edit)s%(sysinfo)s%(analytics)s            </div>

          </div>
        </section>
      </main>
    </div>
  </div>

  <!-- admin.js clones this when it clears the list. -->
  <template id="emptyStateTemplate">
%(empty_template)s  </template>

%(dialogs)s%(script)s
  <script src="{{ static_url('js/i18n.js') }}"></script>
  <script src="{{ static_url('js/admin.js') }}"></script>
</body>

</html>
''' % {
        "sprite": sprite(),
        "bars": btn_icon("bars"),
        "bullseye": icon("bullseye"),
        "users": icon("users"),
        "grip": icon("grip-vertical"),
        "empty": empty_state(),
        "empty_template": empty_state(6),
        "manage": button("Manage", "openRoomManager()", None, "secondary pf-m-block sidebar-action",
                         i18n="manage_rooms", indent=10),
        "config": button("Config", "openConfigPasswordGate()", "cog",
                         "plain masthead-action",
                         extra=' title="Edit config.yaml" aria-label="Config"', indent=8),
        "logout": button("Logout", "logout()", "sign-out-alt",
                         "plain masthead-action", i18n="logout",
                         extra=' aria-label="Logout"', indent=8),
        "sidebar": sidebar,
        "edit": edit_card(),
        "sysinfo": system_info_card(),
        "analytics": analytics_card(),
        "dialogs": dialogs,
        "script": PAGE_SCRIPT,
    }


if __name__ == "__main__":
    out = ROOT / "app/templates/admin.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote %s (%d bytes)" % (out.relative_to(ROOT), out.stat().st_size))
