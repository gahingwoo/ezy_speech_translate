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
                "grip-vertical", "info-circle", "times")


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
             readonly=False, extra="", indent=10):
    pad = " " * indent
    return ('%s<span class="pf-v6-c-form-control pf-m-textarea pf-m-resize-vertical%s">\n'
            '%s  <textarea id="%s" rows="%d"%s%s%s></textarea>\n'
            '%s</span>' % (
                pad, " pf-m-readonly pf-m-plain" if readonly else "", pad, el_id, rows,
                ' placeholder="%s"' % placeholder if placeholder else "",
                ' data-i18n-placeholder="%s"' % i18n_placeholder if i18n_placeholder else "",
                (" readonly" if readonly else "") + extra, pad))


def text_input(el_id, kind="text", placeholder=None, extra="", indent=10):
    pad = " " * indent
    return ('%s<span class="pf-v6-c-form-control">\n'
            '%s  <input type="%s" id="%s"%s%s>\n'
            '%s</span>' % (pad, pad, kind, el_id,
                           ' placeholder="%s"' % placeholder if placeholder else "",
                           extra, pad))


def details_toggle():
    """Below lg the details panel is a drawer, so it needs something to open
    it. From lg the panel is static and this button has nothing to say."""
    return button("Details", "toggleDetails()", "list", "secondary details-toggle",
                  el_id="detailsToggle", i18n="details",
                  extra=' aria-controls="detailsPanel" aria-expanded="false"',
                  indent=18) + "\n"


def password_input(el_id, placeholder=None, extra="", indent=10):
    """A password field with the eye that reveals it. Somebody typing a
    password they cannot see has no way to find the typo, so every password
    field in the app has this; login.html had it first."""
    pad = " " * indent
    return ('%s<div class="pf-v6-c-input-group">\n'
            '%s  <div class="pf-v6-c-input-group__item pf-m-fill">\n'
            '%s' 
            '%s  </div>\n'
            '%s  <div class="pf-v6-c-input-group__item">\n'
            '%s    <button class="pf-v6-c-button pf-m-control" type="button"\n'
            '%s            aria-controls="%s" aria-pressed="false"\n'
            '%s            aria-label="Show password" data-i18n-title="showPassword"\n'
            '%s            onclick="togglePasswordField(this)">\n'
            '%s      <span class="pf-v6-c-button__icon">%s%s</span>\n'
            '%s    </button>\n'
            '%s  </div>\n'
            '%s</div>' % (
                pad, pad,
                text_input(el_id, "password", placeholder, extra, indent + 4),
                pad, pad, pad, pad, el_id, pad, pad, pad,
                icon("eye", "pf-v6-svg icon-eye"),
                icon("eye-slash", "pf-v6-svg icon-eye-slash"),
                pad, pad, pad))


def field_group(title, body, el_id=None, i18n=None):
    """PatternFly's expandable field group. The sidebar carries seven panels of
    controls and only the first two are used every session, so the rest start
    folded. The component animates its own body open and shut."""
    return '''    <div class="pf-v6-c-form__field-group pf-m-expandable sidebar-section"%s>
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
''' % (' id="%s"' % el_id if el_id else "", title, icon("angle-right"),
       i18n_attr(i18n), title, body)


SETTINGS_TABS = (
    ("room", "Room", "room"),
    ("announcement", "Announcement", None),
    ("qr", "Audience QR code", None),
    ("bible", "Bible", None),
    ("cache", "TTS cache", None),
    ("service", "The whole service", None),
    # No translation key: "settings" would render this "Settings" inside a
    # dialog already titled Settings.
    ("display", "Display", None),
)


def tab_panel(key, body):
    """One panel of the settings dialog. The tab list and the panels are
    siblings, which is what PatternFly's vertical tabs expect."""
    return '''    <section class="pf-v6-c-tab-content settings-panel" id="settings-%s"
             role="tabpanel" tabindex="0" aria-labelledby="settings-tab-%s" hidden>
      <div class="pf-v6-c-tab-content__body">
        <form class="pf-v6-c-form" onsubmit="return false;">
%s        </form>
      </div>
    </section>
''' % (key, key, body)


def tab_list():
    items = []
    for i, (key, title, i18n) in enumerate(SETTINGS_TABS):
        items.append(
            '      <li class="pf-v6-c-tabs__item%s" id="settings-tabitem-%s">\n'
            '        <button class="pf-v6-c-tabs__link" type="button" role="tab"\n'
            '                id="settings-tab-%s" aria-controls="settings-%s"\n'
            '                aria-selected="%s" onclick="showSettingsTab(\'%s\')">\n'
            '          <span class="pf-v6-c-tabs__item-text"%s>%s</span>\n'
            '        </button>\n'
            '      </li>\n'
            % (" pf-m-current" if i == 0 else "", key, key, key,
               "true" if i == 0 else "false", key, i18n_attr(i18n), title))
    return '''    <div class="pf-v6-c-tabs pf-m-vertical pf-m-box settings-tabs" role="region">
      <ul class="pf-v6-c-tabs__list" role="tablist" aria-label="Settings sections">
%s      </ul>
    </div>
''' % "".join(items)


def settings_modal(panels):
    """Everything the panel is set up with rather than run with. It was a
    sidebar of seven unrelated groups beside the transcript."""
    body = [tab_list()]
    for key, _title, _i18n in SETTINGS_TABS:
        body.append(tab_panel(key, panels[key]))
    return '''  <div class="pf-v6-c-backdrop app-modal" id="settingsModal"
       onclick="hideSettings(event)">
    <div class="pf-v6-c-modal-box pf-m-lg" role="dialog" aria-modal="true"
         aria-labelledby="settingsTitle">
      <div class="pf-v6-c-modal-box__close">
        <button class="pf-v6-c-button pf-m-plain" type="button" aria-label="Close"
                onclick="hideSettings()">%s</button>
      </div>
      <header class="pf-v6-c-modal-box__header">
        <h1 class="pf-v6-c-modal-box__title" id="settingsTitle">
          <span class="pf-v6-c-modal-box__title-text" data-i18n="settings">Settings</span>
        </h1>
      </header>
      <div class="pf-v6-c-modal-box__body settings-body">
%s      </div>
    </div>
  </div>
''' % (btn_icon("times"), "".join(body))


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

def room_section():
    """Which room this panel is broadcasting to, and the way into the manager.
    It was in the masthead, where on a phone it pushed the bar to three rows."""
    body = '''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-control room-switcher">
          <span class="pf-v6-c-label pf-m-outline">
            <span class="pf-v6-c-label__content">
              <span class="pf-v6-c-label__icon">%s</span>
              <span class="pf-v6-c-label__text" id="currentRoomLabel">main</span>
            </span>
          </span>
%s
        </div>
      </div>
''' % (icon("users"),
       button("Manage rooms", "openRoomManager()", None, "secondary",
              i18n="manage_rooms", indent=10))
    return body


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
''' % (button("Start Recording", "toggleRecording()", "microphone",
              "primary pf-m-block", el_id="recordBtn", i18n="startRecording",
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
    return body


def tts_cache_section():
    stats = ('''          <dl class="pf-v6-c-description-list pf-m-horizontal pf-m-compact pf-m-fluid"
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
    return body


def bible_section():
    body = group(
        select("adminBibleSourceSelect", '<option value="">— Loading... —</option>',
               "Bible source translation", "saveBibleSourceTranslation()",
               extra=' title="Bible translation shown alongside the original-language'
                     ' caption. Choose based on the language being spoken."'),
        "Source Translation", None, "adminBibleSourceSelect",
        helper='<p class="pf-v6-c-form__helper-text" id="adminBibleSaveStatus"'
               ' role="status" aria-live="polite"></p>')
    return '<div id="bibleAdminSection">\n%s      </div>\n' % body


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
    return '<div id="announcementSection">\n%s      </div>\n' % body


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
    return '<div id="qrSection">\n%s      </div>\n' % body


# ── the details panel ─────────────────────────────────────────────────────
# Cockpit's shape, which is PatternFly's Drawer: the list keeps the whole
# content area and everything about the selected row lives in a panel beside
# it, separated by the drawer's own border rather than by a stack of floating
# cards. The three groups inside are sections of one surface divided by rules,
# so the eye reads one panel instead of three boxes.


def panel_section(title, body, i18n=None, el_id=None, extra=""):
    return ('      <section class="pf-v6-c-drawer__body panel-section"%s%s>\n'
            '        <h2 class="pf-v6-c-title pf-m-md panel-section__title"%s>%s</h2>\n'
            '%s'
            '      </section>\n'
            % (' id="%s"' % el_id if el_id else "", extra,
               i18n_attr(i18n), title, body))


def edit_section():
    body = ('        <form class="pf-v6-c-form" onsubmit="return false;">\n'
            '%s%s        </form>\n'
            '        <div class="panel-section__actions">\n%s\n%s\n        </div>\n'
            % (
                group(textarea("originalText", 2, readonly=True, indent=14),
                      "Original", "original", "originalText", indent=12),
                group(textarea("correctedText", 4, "Select an item to edit...",
                               "selectItemToEdit", indent=14),
                      "Corrected (Edit Here)", "correctedLabel", "correctedText",
                      indent=12),
                button("Save", "saveCorrection()", "save", "primary",
                       i18n="save", indent=10),
                button("Cancel", "cancelCorrection()", "times", "link",
                       i18n="cancel", indent=10),
            ))
    return panel_section("Edit &amp; Correct", body, "editAndCorrect")


def system_info_section():
    rows = (
        dl_group("Clients", '<strong id="sys-clients">0</strong>', "clients", indent=12)
        + dl_group("Transcripts", '<strong id="sys-transcriptions">0</strong>',
                   "transcriptions", indent=12)
        + dl_group("Recording", label("sys-recording", "Stopped", None, "stopped"),
                   "recording", indent=12)
        + dl_group("Language",
                   '<span id="sys-language" class="pf-v6-c-label pf-m-blue">'
                   '<span class="pf-v6-c-label__content">'
                   '<span class="pf-v6-c-label__text mono">en-US</span>'
                   '</span></span>', "language", indent=12)
    )
    body = ('        <dl class="pf-v6-c-description-list pf-m-horizontal pf-m-compact pf-m-fluid">\n'
            '%s        </dl>\n' % rows)
    return panel_section("System Info", body, "systemInfo", "systemInfo",
                         ' aria-label="System Info"')


def analytics_section():
    rows = (
        dl_group("Duration", '<strong id="stat-duration">—</strong>',
                 "statDuration", indent=12)
        + dl_group("Peak Viewers", '<strong id="stat-peak">0</strong>',
                   "statPeak", indent=12)
        + dl_group("Total Words", '<strong id="stat-words">0</strong>',
                   "statWords", indent=12)
        + dl_group("Translations", '<strong id="stat-translations">0</strong>',
                   "statTranslations", indent=12)
        + dl_group("Bible Refs", '<strong id="stat-bible-refs">0</strong>',
                   "statBibleRefs", indent=12)
        + dl_group("DB Entries", label("stat-db", "—"), "statDbEntries", indent=12)
    )
    body = ('        <dl class="pf-v6-c-description-list pf-m-horizontal pf-m-compact pf-m-fluid"\n'
            '            id="analyticsCard" aria-label="Session Analytics">\n'
            '%s        </dl>\n'
            '        <div class="panel-section__actions">\n%s\n        </div>\n'
            % (rows, button("Refresh Stats", "refreshAnalytics()", "sync-alt",
                            "secondary", i18n="refreshStats", indent=10)))
    return panel_section("Session Stats", body, "sessionStats", "analyticsSection")


def empty_state(indent=16):
    """The list is empty on load and again whenever admin.js clears it, so the
    same markup is rendered inline and into a <template> it can clone. It is a
    row of the data list, because that is what it stands in for."""
    pad = " " * indent
    return ('%s<li class="pf-v6-c-data-list__item empty-row">\n'
            '%s  <div class="pf-v6-c-data-list__item-row">\n'
            '%s    <div class="pf-v6-c-data-list__item-content">\n'
            '%s      <div class="pf-v6-c-data-list__cell">\n'
            '%s        <div class="pf-v6-c-empty-state">\n'
            '%s          <div class="pf-v6-c-empty-state__content">\n'
            '%s            <div class="pf-v6-c-empty-state__icon">%s</div>\n'
            '%s            <div class="pf-v6-c-empty-state__title">\n'
            '%s              <h2 class="pf-v6-c-empty-state__title-text"\n'
            '%s                  data-i18n="noTranscriptionsYet">No transcriptions yet</h2>\n'
            '%s            </div>\n'
            '%s            <div class="pf-v6-c-empty-state__body" data-i18n="startRecordingHelp">\n'
            '%s              Start recording to see transcriptions</div>\n'
            '%s          </div>\n'
            '%s        </div>\n'
            '%s      </div>\n'
            '%s    </div>\n'
            '%s  </div>\n'
            '%s</li>\n' % ((pad,) * 7 + (icon("comments"),) + (pad,) * 12))


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
    body = password_input("configPasswordInput", "Admin password",
                      extra=' aria-label="Admin password"'
                            " onkeydown=\"if(event.key==='Enter')confirmConfigPassword()\"")
    return modal("configPasswordModal", "Confirm identity", body,
                 "closeConfigPasswordGate()", size="sm", icon_name="lock",
                 description="Enter your admin password to access the config editor.",
                 backdrop_onclick="if(event.target===this)closeConfigPasswordGate()",
                 footer=footer(
                     button("Cancel", "closeConfigPasswordGate()", None, "link", indent=8),
                     button("Confirm", "confirmConfigPassword()", None, "primary", indent=8)))


def recording_lock_modal():
    body = '''          <div class="pf-v6-c-alert pf-m-warning pf-m-inline">
            <div class="pf-v6-c-alert__icon">%s</div>
            <p class="pf-v6-c-alert__title">
              <strong id="recordingLockOwner">Another admin</strong> is currently recording
              in this room.</p>
          </div>
%s''' % (icon("exclamation-triangle"),
         password_input("recordingLockPassword", "Admin password",
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


# term, its translation key, value, the value's translation key.
def about_link(href, text, i18n=None):
    """A link out of the app. PatternFly marks these with the external-link
    icon after the label, so a reader knows the click leaves the page before
    they make it."""
    return ('<a class="about-link" href="%s" rel="noopener noreferrer" target="_blank">'
            '<span%s>%s</span>%s</a>'
            % (href, i18n_attr(i18n), text,
               icon("external-link-alt", "pf-v6-svg about-link__icon")))


REPO = "https://github.com/gahingwoo/ezy_speech_translate"

ABOUT_ROWS = (
    ("Version", "versionLabel", "v4.0.0 - Open Source - MIT License", "version"),
    # Who wrote it. This was in the box the rewrite replaced and went missing
    # on the way; the credit badge below says the same thing in a logo, and a
    # logo is not a row anyone can read out.
    ("Made by", "madeBy", about_link("https://gahingwoo.com",
                                     "Ga Hing Woo (Jiaxing Hu)", "author"), None),
    ("Source", "source", about_link(REPO, "gahingwoo/ezy_speech_translate"), None),
    ("Feedback", "feedback",
     about_link(REPO + "/issues/new/choose", "Open an issue", "openAnIssue"), None),
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
          <!-- One element, and the stylesheet picks which of the two files it
               draws: a hidden <img> is fetched anyway, so the pair cost every
               visitor both downloads to show one. -->
          <a class="credit-badge__link" href="https://gahingwoo.com"
             rel="noopener noreferrer" target="_blank">
            <span class="credit-badge__art" role="img"
                  aria-label="Engineered by gahingwoo"></span>
          </a>
        </p>
        <p class="pf-v6-c-about-modal-box__strapline" data-i18n="tagline">
          Let language no longer stand in the way of connection</p>
      </div>
    </div>
  </div>
''' % (btn_icon("times"), rows)


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
    /* The settings dialog. PatternFly's vertical tabs: the list and the panels
       are siblings, one panel is shown at a time, and the tab that is current
       carries pf-m-current and aria-selected. */
    function showSettingsTab(key) {
      document.querySelectorAll('.settings-tabs .pf-v6-c-tabs__item').forEach(function (item) {
        const on = item.id === 'settings-tabitem-' + key;
        item.classList.toggle('pf-m-current', on);
        const link = item.querySelector('.pf-v6-c-tabs__link');
        if (link) link.setAttribute('aria-selected', String(on));
      });
      document.querySelectorAll('.settings-panel').forEach(function (panel) {
        panel.hidden = panel.id !== 'settings-' + key;
      });
    }
    window.showSettingsTab = showSettingsTab;

    function showSettings(key) {
      showSettingsTab(key || 'room');
      document.getElementById('settingsModal').classList.add('active');
    }
    window.showSettings = showSettings;

    function hideSettings(event) {
      if (event && event.target !== event.currentTarget) return;
      document.getElementById('settingsModal').classList.remove('active');
    }
    window.hideSettings = hideSettings;

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
    function closeRecordingLock() {
      document.getElementById('recordingLockModal').classList.remove('modal-overlay--open');
      const pw = document.getElementById('recordingLockPassword');
      if (pw) pw.value = '';
    }
    window.openRoomManager = openRoomManager;
    window.closeRoomManager = closeRoomManager;
    window.openConfigPasswordGate = openConfigPasswordGate;
    window.closeConfigPasswordGate = closeConfigPasswordGate;
    window.closeRecordingLock = closeRecordingLock;

    /* The details drawer. Static from lg, where the button that opens it is
       hidden; below that it slides over the list. */
    function toggleDetails(force) {
      const drawer = document.getElementById('detailsDrawer');
      const btn = document.getElementById('detailsToggle');
      const on = force === undefined ? !drawer.classList.contains('pf-m-expanded') : !!force;
      drawer.classList.toggle('pf-m-expanded', on);
      if (btn) btn.setAttribute('aria-expanded', String(on));
    }
    window.toggleDetails = toggleDetails;

    /* The eye on a password field. The button holds both eyes and the
       stylesheet shows the one that matches aria-pressed. */
    function togglePasswordField(btn) {
      const input = document.getElementById(btn.getAttribute('aria-controls'));
      if (!input) return;
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', String(show));
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      input.focus();
    }
    window.togglePasswordField = togglePasswordField;

    /* The rail is PatternFly's expandable jump links: a toggle below xl, a
       plain sticky list above it. */
    function toggleJumpLinks(btn) {
      const nav = document.getElementById('jumpNav');
      const open = !nav.classList.contains('pf-m-expanded');
      nav.classList.toggle('pf-m-expanded', open);
      btn.setAttribute('aria-expanded', String(open));
    }
    window.toggleJumpLinks = toggleJumpLinks;

  </script>
'''


def hearing_controls():
    """What the console is hearing with. The design spec keeps the console for
    watching and correcting, so this is the whole of its setup: the language
    being spoken and the microphone it comes in on. Everything else is in the
    settings dialog."""
    return (group(select("sourceLangSelect", SOURCE_LANGS, "Source language",
                         "changeSourceLanguage()", indent=26),
                  "Source Language", "sourceLanguage", "sourceLangSelect", indent=22)
            + group(select("deviceSelect", '<option data-i18n="loading">Loading...</option>',
                           "Audio device", indent=26),
                    "Audio Device", "audioDevice", "deviceSelect", indent=22))


def console_actions():
    """Everything that can be done to the list, in the transcript's own footer
    rather than in a column of its own."""
    return ('                    <div class="pf-v6-c-action-list">\n'
            '                      <div class="pf-v6-c-action-list__group">\n%s\n%s\n'
            '                      </div>\n'
            '                    </div>\n'
            % (button("Add a line", "addNewItem()", "plus", "secondary",
                      i18n="addLine", indent=24),
               button("Export", "exportData()", "download", "secondary",
                      i18n="export", indent=24)))


def session_stats():
    """What this service has come to, in four rows.

    There were ten, and three of them were the same number: the session's
    transcription counter, the length of the list in memory, and the row count
    in the database all read alike, and two of those named the storage rather
    than the thing. Lines is the number; the words are what the number is made
    of. Viewers now and viewers at peak were one idea in two rows.

    Nothing here is a pill. A count is not a status and a locale is not a
    status — PatternFly's label carries state, and the only state on this card
    is whether it is recording."""
    return (dl_group("Running", '<strong id="stat-duration">—</strong>',
                     "running", indent=22)
            # No line count here. The transcript card above is badged with it,
            # and saying a number twice on one page is how the two came to
            # disagree in the first place. This card says what the table
            # cannot: how long, how much was said, who was reading.
            + dl_group("Spoken",
                       '<strong id="stat-words">0</strong> '
                       '<span data-i18n="words">words</span>'
                       '<span class="meta"><span id="stat-translations">0</span> '
                       '<span data-i18n="linesLower">lines</span> · '
                       '<span id="stat-bible-refs">0</span> '
                       '<span data-i18n="scriptureRefs">Scripture references</span></span>',
                       "spoken", indent=22)
            + dl_group("Viewers",
                       '<strong id="sys-clients">0</strong>'
                       '<span class="meta"><span data-i18n="peakWas">peak was</span> '
                       '<span id="stat-peak">0</span></span>',
                       "viewers", indent=22)
            + dl_group("Recording", label("sys-recording", "Stopped", None, "stopped"),
                       "recording", indent=22))


def correction_modal():
    """Correcting a line is a dialog, not a panel.

    The console's job is watching; correcting is something you stop and do. A
    panel held open beside the list spent its whole life empty, and the design
    spec puts the correction against the line it belongs to instead — the
    Correction column opens this."""
    body = (group(textarea("originalText", 2, readonly=True, indent=12),
                  "Recognised", "recognised", "originalText", indent=10)
            + group(textarea("correctedText", 4, "Select an item to edit...",
                             "selectItemToEdit", indent=12),
                    "Correction", "correction", "correctedText", indent=10)
            + '        <p class="pf-v6-c-form__helper-text" data-i18n="correctionHelp">A correction'
              ' is re-translated and pushed to every viewer.</p>\n')
    return modal("correctionModal", "Correct this line", body,
                 "cancelCorrection()", size="md", icon_name="edit",
                 backdrop_onclick="if(event.target===this)cancelCorrection()",
                 footer=footer(
                     button("Cancel", "cancelCorrection()", None, "link", indent=8),
                     button("Save", "saveCorrection()", "save", "primary",
                            i18n="save", indent=8)))


def whole_service_section():
    """The two that act on a whole service rather than on a line.

    They were in the console's action bar beside Export, which put "wipe this
    service" one slip away from "save a copy of it". They belong with setting
    up, and they will move to the Setup page with the rest of it."""
    body = ('        <div class="pf-v6-c-action-list">\n'
            '          <div class="pf-v6-c-action-list__group">\n%s\n%s\n'
            '          </div>\n'
            '        </div>\n'
            '        <input type="file" id="importFileInput" accept=".json" hidden\n'
            '               onchange="handleImportFile(event)">\n'
            % (button("Import a transcript",
                      "document.getElementById('importFileInput').click()",
                      "upload", "secondary", i18n="import", indent=12),
               button("Clear this service", "clearHistory()", "trash",
                      "danger pf-m-secondary", i18n="clearAll", indent=12)))
    return body


def build():
    panels = {
        "room": room_section(),
        "announcement": announcement_section(),
        "qr": qr_section(),
        "bible": bible_section(),
        "cache": tts_cache_section(),
        "service": whole_service_section(),
        "display": settings_section(),
    }

    sidebar = audio_section() + actions_section()

    dialogs = (settings_modal(panels) + room_manager() + config_password_modal()
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
  <!-- The house layer both pages sit in, then the design's own classes, then
       what is left that is only this page's. -->
  <link href="{{ static_url('css/shell.css') }}" rel="stylesheet">
  <link href="{{ static_url('css/ezyspeech.css') }}" rel="stylesheet">
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
                  aria-controls="sidebar" aria-expanded="true" aria-label="Toggle the panel"
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
             what it writes and what is written here have to agree. The label's
             colour carries the state; an icon as well would say it twice. -->
        <span class="pf-v6-c-label pf-m-danger connection-badge offline" id="statusBadge"
              title="User server" role="status" aria-live="polite">
          <span class="pf-v6-c-label__content">
            <span class="pf-v6-c-label__icon" id="statusBadgeIcon">%(status_icon)s</span>
            <span class="pf-v6-c-label__text" data-i18n="offline">Offline</span>
          </span>
        </span>

%(settings)s

%(config)s
%(logout)s
      </div>
    </header>

    <!-- Backdrop behind the sidebar when it is a drawer, below xl. -->
    <div class="pf-v6-c-backdrop sidebar-overlay" id="sidebarOverlay" aria-hidden="true"
         onclick="toggleMobileMenu()"></div>

    <!-- The site's own navigation, the same three groups the viewer has.
         Everything under Setup opens a dialog rather than going somewhere. -->
    <div class="pf-v6-c-page__sidebar" id="sidebar" aria-label="Site">
      <div class="pf-v6-c-page__sidebar-body">
        <nav class="pf-v6-c-nav" aria-label="Site">
          <section class="pf-v6-c-nav__section" aria-labelledby="nav-service-title">
            <h2 class="pf-v6-c-nav__section-title" id="nav-service-title"
                data-i18n="nav_thisService">This service</h2>
            <ul class="pf-v6-c-nav__list" role="list">
              <li class="pf-v6-c-nav__item">
                <a href="#hearing" class="pf-v6-c-nav__link pf-m-current" aria-current="page">
                  <span class="pf-v6-c-nav__link-text" data-i18n="hearing">Hearing</span></a></li>
              <li class="pf-v6-c-nav__item">
                <a href="#transcript" class="pf-v6-c-nav__link">
                  <span class="pf-v6-c-nav__link-text" data-i18n="transcript">Transcript</span></a></li>
            </ul>
          </section>
          <section class="pf-v6-c-nav__section" aria-labelledby="nav-setup-title">
            <h2 class="pf-v6-c-nav__section-title" id="nav-setup-title"
                data-i18n="setup">Setup</h2>
            <ul class="pf-v6-c-nav__list" role="list">
              <li class="pf-v6-c-nav__item">
                <button type="button" class="pf-v6-c-nav__link" onclick="showSettings()">
                  <span class="pf-v6-c-nav__link-text" data-i18n="settings">Settings</span></button></li>
              <li class="pf-v6-c-nav__item">
                <button type="button" class="pf-v6-c-nav__link" onclick="openRoomManager()">
                  <span class="pf-v6-c-nav__link-text" data-i18n="rooms">Rooms</span></button></li>
              <li class="pf-v6-c-nav__item">
                <button type="button" class="pf-v6-c-nav__link" onclick="openConfigPasswordGate()">
                  <span class="pf-v6-c-nav__link-text" data-i18n="serverConfig">Server configuration</span></button></li>
            </ul>
          </section>
          <section class="pf-v6-c-nav__section" aria-labelledby="nav-elsewhere-title">
            <h2 class="pf-v6-c-nav__section-title" id="nav-elsewhere-title"
                data-i18n="nav_elsewhere">Elsewhere</h2>
            <ul class="pf-v6-c-nav__list" role="list">
              <li class="pf-v6-c-nav__item">
                <a href="/" class="pf-v6-c-nav__link" rel="noopener noreferrer" target="_blank">
                  <span class="pf-v6-c-nav__link-text" data-i18n="nav_liveTranslation">Live translation</span></a></li>
              <li class="pf-v6-c-nav__item">
                <a href="/projection" class="pf-v6-c-nav__link" rel="noopener noreferrer" target="_blank">
                  <span class="pf-v6-c-nav__link-text" data-i18n="projection">Projection screen</span></a></li>
            </ul>
          </section>
        </nav>
      </div>
    </div>

    <div class="pf-v6-c-page__main-container">
      <main class="pf-v6-c-page__main doc-page with-rail" id="main-content" tabindex="-1">
        <section class="pf-v6-c-page__main-section pf-m-limit-width pf-m-fill"
                 aria-label="Live console">
          <div class="pf-v6-c-page__main-body">

            <aside class="page-rail no-print">
              <nav class="pf-v6-c-jump-links pf-m-vertical pf-m-expandable pf-m-non-expandable-on-xl"
                   aria-label="On this page" id="jumpNav">
                <div class="pf-v6-c-jump-links__header" id="jumpHeader">
                  <div class="pf-v6-c-jump-links__toggle">
                    <button class="pf-v6-c-button pf-m-plain" type="button" aria-expanded="false"
                            onclick="toggleJumpLinks(this)">
                      <span class="pf-v6-c-button__icon pf-m-start">
                        <span class="pf-v6-c-jump-links__toggle-icon">%(angle_right)s</span></span>
                      <span class="pf-v6-c-button__text" data-i18n="onThisPage">On this page</span>
                    </button>
                  </div>
                  <div class="pf-v6-c-jump-links__label" data-i18n="onThisPage">On this page</div>
                </div>
                <ul class="pf-v6-c-jump-links__list" role="list" aria-labelledby="jumpHeader">
                  <li class="pf-v6-c-jump-links__item pf-m-current">
                    <span class="pf-v6-c-jump-links__link"><a class="pf-v6-c-button pf-m-link" href="#hearing">
                      <span class="pf-v6-c-button__text"><span class="pf-v6-c-jump-links__link-text"
                            data-i18n="hearing">Hearing</span></span></a></span></li>
                  <li class="pf-v6-c-jump-links__item">
                    <span class="pf-v6-c-jump-links__link"><a class="pf-v6-c-button pf-m-link" href="#transcript">
                      <span class="pf-v6-c-button__text"><span class="pf-v6-c-jump-links__link-text"
                            data-i18n="transcript">Transcript</span></span></a></span></li>
                  <li class="pf-v6-c-jump-links__item">
                    <span class="pf-v6-c-jump-links__link"><a class="pf-v6-c-button pf-m-link" href="#session">
                      <span class="pf-v6-c-button__text"><span class="pf-v6-c-jump-links__link-text"
                            data-i18n="nav_thisService">This service</span></span></a></span></li>
                </ul>
              </nav>
            </aside>

            <div class="page-content">
              <div class="page-head">
                <h1 class="page-title">
                  <span data-i18n="liveConsole">Live console</span>
                  <span class="subtitle" id="consoleSubtitle"></span>
                </h1>
%(record)s              </div>

              <!-- What the microphone is picking up right now. It is one card
                   because it is one question: is this thing hearing me. -->
              <div class="section">
                <div class="pf-v6-c-card" id="hearing">
                  <div class="pf-v6-c-card__title">
                    <h2 class="pf-v6-c-card__title-text" data-i18n="hearing">Hearing</h2>
                  </div>
                  <div class="pf-v6-c-card__body">
                    <!-- No box. The card is the box; a panel inside it was a
                         white surface on a white surface, and an empty one at
                         that. This is the most important thing on the page, so
                         it is simply the largest text on it. -->
                    <div class="pf-v6-c-content interim-display inactive"
                         id="interimDisplay" role="status" aria-live="polite">
                      <p id="interimText"
                         data-i18n="waitingForSpeech">Waiting for speech...</p>
                    </div>
                    <form class="pf-v6-c-form hearing-controls" onsubmit="return false;">
%(audio)s                    </form>
                    <span class="pf-v6-c-label pf-m-blue auto-restart-badge" id="autoRestartBadge"
                          hidden>
                      <span class="pf-v6-c-label__content">
                        <span class="pf-v6-c-label__icon">%(sync)s</span>
                        <span class="pf-v6-c-label__text" data-i18n="autoRestartEnabled">Auto-restart enabled</span>
                      </span>
                    </span>
                  </div>
                  <div class="pf-v6-c-card__footer" data-i18n="hearingHelp">Interim text. It becomes
                    a line below once the speaker pauses.</div>
                </div>
              </div>

              <!-- Every line, and the correction made to it. A correction is
                   re-translated and pushed to everyone reading. -->
              <div class="section">
                <div class="pf-v6-c-card" id="transcript">
                  <!-- Export and Delete live here and appear only once rows
                       are ticked: a destructive button with nothing to act on
                       should not be sitting there armed. The header says how
                       many are ticked, so Delete always has a subject. -->
                  <div class="pf-v6-c-card__header">
                    <div class="pf-v6-c-card__actions pf-m-no-offset">
                      <div class="pf-v6-c-action-list selection-actions" id="selectionActions"
                           hidden>
                        <div class="pf-v6-c-action-list__group">
                          <span class="meta" id="selectionCount" role="status"
                                aria-live="polite"></span>
%(bulk_export)s
%(bulk_delete)s
                        </div>
                      </div>
                    </div>
                    <div class="pf-v6-c-card__header-main">
                      <h2 class="pf-v6-c-card__title-text">
                        <span data-i18n="transcript">Transcript</span>
                        <span class="pf-v6-c-badge pf-m-read" id="itemCount"
                              aria-label="Transcription count">0</span>
                      </h2>
                    </div>
                  </div>
                  <div class="pf-v6-c-card__body">
                    <table class="pf-v6-c-table pf-m-grid-md transcript-table" role="grid"
                           aria-label="Transcript">
                      <thead class="pf-v6-c-table__thead">
                        <tr class="pf-v6-c-table__tr" role="row">
                          <td class="pf-v6-c-table__check" role="columnheader">
                            <input type="checkbox" id="selectAllRows" aria-label="Select all lines"
                                   onchange="toggleSelectAll(this.checked)">
                          </td>
                          <!-- No heading over the grips: every handle below
                               carries its own label, and the screen-reader
                               text that was here was leaking two clipped
                               characters into the corner of the table. -->
                          <td class="pf-v6-c-table__td table-drag"></td>
                          <th class="pf-v6-c-table__th" role="columnheader" scope="col"
                              data-i18n="time">Time</th>
                          <th class="pf-v6-c-table__th" role="columnheader" scope="col"
                              data-i18n="recognised">Recognised</th>
                          <th class="pf-v6-c-table__th" role="columnheader" scope="col"
                              data-i18n="correction">Correction</th>
                        </tr>
                      </thead>
                      <tbody class="pf-v6-c-table__tbody" role="rowgroup" id="transcriptionsList">
                      </tbody>
                    </table>
                    <div class="empty-slot" id="emptySlot"></div>
                  </div>
                  <!-- Stack, not a margin: the gap between the note and the
                       buttons is a layout gap and PatternFly has a token for
                       it. Writing it by hand is what made the spacing look
                       arbitrary everywhere else. -->
                  <div class="pf-v6-c-card__footer">
                    <div class="pf-v6-l-stack pf-m-gutter">
                      <div class="pf-v6-l-stack__item">
                        <p class="meta" data-i18n="correctionHelp">A correction is re-translated
                          and pushed to every viewer.</p>
                      </div>
                      <div class="pf-v6-l-stack__item">
%(actions)s                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="section">
                <div class="pf-v6-c-card" id="session">
                  <div class="pf-v6-c-card__title">
                    <h2 class="pf-v6-c-card__title-text" data-i18n="nav_thisService">This service</h2>
                  </div>
                  <div class="pf-v6-c-card__body">
                    <dl class="pf-v6-c-description-list pf-m-horizontal-on-sm kv"
                        id="analyticsCard" aria-label="Session Analytics">
%(stats)s                    </dl>
                  </div>
                  <!-- No refresh button: a console that has to be asked is
                       not live. This says when it last heard from the server
                       instead. -->
                  <div class="pf-v6-c-card__footer">
                    <p class="meta"><span data-i18n="updated">Updated</span>
                      <span id="statsUpdated">—</span></p>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>
      </main>
    </div>
  </div>

  <!-- admin.js clones this when it clears the list. -->
  <template id="emptyStateTemplate">
%(empty_template)s  </template>

%(correction)s%(dialogs)s%(script)s
  <script src="{{ static_url('js/i18n.js') }}"></script>
  <script src="{{ static_url('js/theme.js') }}"></script>
  <script src="{{ static_url('js/admin.js') }}"></script>
</body>

</html>
''' % {
        "sprite": sprite(),
        # The three masthead actions carry their label from md up; the cog
        # alone showed none, which left the icon to speak for itself.
        "status_icon": icon("exclamation-circle"),
        "settings": button("Settings", "showSettings()", "cog",
                           "plain masthead-action", el_id="settingsToggle",
                           i18n="settings",
                           extra=' aria-label="Settings" title="Settings"'
                                 ' data-i18n-title="settings"', indent=8),
        "bars": btn_icon("bars"),
        "angle_right": icon("angle-right"),
        "sync": icon("sync-alt"),
        "audio": hearing_controls(),
        "bulk_export": button("Export selected", "exportSelected()", "download",
                              "secondary", i18n="exportSelected", indent=26),
        # Outlined, not filled: nothing on this card should be the
        # only solid button, least of all the one that destroys.
        "bulk_delete": button("Delete", "deleteSelected()", "trash",
                              "danger pf-m-secondary", i18n="delete", indent=26),
        "actions": console_actions(),
        "stats": session_stats(),
        "record": button("Start Recording", "toggleRecording()", "microphone",
                         "primary", el_id="recordBtn", i18n="startRecording",
                         extra=' aria-pressed="false"', indent=16) + "\n",
        "grip": icon("grip-vertical"),
        "empty": empty_state(),
        "empty_template": empty_state(6),
        # Two cogs side by side said nothing about which was which: this one
        # opens the server's own configuration file.
        "config": button("Config", "openConfigPasswordGate()", "server",
                         "plain masthead-action",
                         extra=' title="Server configuration"'
                               ' aria-label="Server configuration"', indent=8),
        "logout": button("Logout", "logout()", "sign-out-alt",
                         "plain masthead-action", i18n="logout",
                         extra=' aria-label="Logout"', indent=8),
        "edit": edit_section(),
        "sysinfo": system_info_section(),
        "analytics": analytics_section(),
        "times": btn_icon("times"),
        "details_toggle": details_toggle(),
        "correction": correction_modal(),
        "dialogs": dialogs,
        "script": PAGE_SCRIPT,
    }


if __name__ == "__main__":
    out = ROOT / "app/templates/admin.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote %s (%d bytes)" % (out.relative_to(ROOT), out.stat().st_size))
