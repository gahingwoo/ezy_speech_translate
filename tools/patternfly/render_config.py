#!/usr/bin/env python3
"""Generate app/templates/config.html: the settings page.

The admin panel used to edit config.yaml in a textarea, which hands the whole
document back from the browser — a key the page did not render was a key that
got dropped, and the save rewrote the file and took its comments with it. This
page sends named fields instead, through /api/config/fields, which refuses a
path that is not already in the file and refuses any path ending in a secret.
config/secrets.key and the file's format are untouched either way.

    python3 tools/patternfly/render_config.py

The fields, their labels and their help text are in config_schema.py; the help
comes from config.yaml's own comments.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from config_schema import GROUPS                      # noqa: E402
from render_admin import (ROOT, btn_icon, button,     # noqa: E402
                          icon, sprite)


def field_id(path):
    return "cfg-" + path.replace(".", "-")


def control(path, kind, options):
    """One PatternFly control, named by its dotted path so config.js can read
    the whole form back without a second table."""
    el_id, data = field_id(path), ' data-config-path="%s"' % path

    if kind == "switch":
        return ('''          <div class="pf-v6-c-switch">
            <input class="pf-v6-c-switch__input" type="checkbox" id="%s"%s>
            <label class="pf-v6-c-switch__label" for="%s">
              <span class="pf-v6-c-switch__toggle"></span>
            </label>
          </div>''' % (el_id, data, el_id))

    if kind == "select":
        opts = "".join('<option value="%s">%s</option>' % o for o in options)
        return ('''          <span class="pf-v6-c-form-control">
            <select id="%s"%s>%s</select>
            <span class="pf-v6-c-form-control__utilities">
              <span class="pf-v6-c-form-control__toggle-icon">%s</span>
            </span>
          </span>''' % (el_id, data, opts, icon("angle-down")))

    return ('''          <span class="pf-v6-c-form-control">
            <input type="%s" id="%s"%s>
          </span>''' % ("number" if kind == "number" else "text", el_id, data))


def group_card(title, description, fields):
    body = []
    for path, label, kind, help_text, options in fields:
        el_id = field_id(path)
        helper = ""
        if help_text:
            helper = ('        <div class="pf-v6-c-form__helper-text">%s</div>\n'
                      % help_text)
        body.append('''      <div class="pf-v6-c-form__group">
        <div class="pf-v6-c-form__group-label">
          <label class="pf-v6-c-form__label" for="%s">
            <span class="pf-v6-c-form__label-text">%s</span>
          </label>
        </div>
        <div class="pf-v6-c-form__group-control">
%s
        </div>
%s      </div>
''' % (el_id, label, control(path, kind, options), helper))

    desc = ""
    if description:
        desc = ('      <div class="pf-v6-c-card__body config-card__intro">%s</div>\n'
                % description)

    return '''    <section class="pf-v6-c-card config-card">
      <div class="pf-v6-c-card__header">
        <div class="pf-v6-c-card__header-main">
          <h2 class="pf-v6-c-card__title-text">%s</h2>
        </div>
      </div>
%s      <div class="pf-v6-c-card__body">
        <div class="pf-v6-c-form">
%s        </div>
      </div>
    </section>
''' % (title, desc, "".join(body))


def advanced_card():
    """The old editor, kept as the way to reach a setting this page does not
    model. It still rewrites the whole file, so it says so."""
    return '''    <section class="pf-v6-c-card config-card" id="rawEditorCard">
      <div class="pf-v6-c-card__header">
        <div class="pf-v6-c-card__header-toggle">
          <button class="pf-v6-c-button pf-m-plain" type="button" id="rawEditorToggle"
                  aria-expanded="false" aria-controls="rawEditorBody"
                  aria-label="Toggle the file editor" onclick="toggleRawEditor()">
            <span class="pf-v6-c-card__header-toggle-icon">%s</span>
          </button>
        </div>
        <div class="pf-v6-c-card__header-main">
          <h2 class="pf-v6-c-card__title-text">Edit config.yaml directly</h2>
        </div>
      </div>
      <div class="pf-v6-c-card__expandable-content" id="rawEditorBody" hidden>
        <div class="pf-v6-c-card__body">
          <div class="pf-v6-c-alert pf-m-warning pf-m-inline">
            <div class="pf-v6-c-alert__icon">%s</div>
            <p class="pf-v6-c-alert__title">Saving here rewrites the whole file and
              drops its comments. The fields above change one setting at a time and
              leave the rest of the file alone.</p>
          </div>
          <p class="pf-v6-c-form__helper-text">Passwords and secrets read as
            <code>***</code> and are put back untouched on save.</p>
          <span class="pf-v6-c-form-control pf-m-textarea config-editor">
            <textarea id="configEditorTextarea" spellcheck="false"
                      aria-label="config.yaml" placeholder="Loading…"></textarea>
          </span>
        </div>
        <div class="pf-v6-c-card__footer">
%s
        </div>
      </div>
    </section>
''' % (icon("angle-right"), icon("exclamation-triangle"),
       button("Save the file", "saveRawConfig()", "save", "secondary", indent=10))


def build():
    cards = "".join(group_card(title, description, fields)
                    for title, description, fields in GROUPS)

    return '''<!DOCTYPE html>
<!-- Generated by tools/patternfly/render_config.py. Edit that, not this. -->
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta content="width=device-width, initial-scale=1.0" name="viewport">
  <title>EzySpeech - Settings</title>
  <!-- Favicon will be set by OEM loader -->
  <link href="{{ static_url('patternfly/patternfly.css') }}" rel="stylesheet">
  <link href="{{ static_url('css/admin.css') }}" rel="stylesheet">
  <script src="{{ static_url('js/oem-loader.js') }}"></script>
</head>

<body data-theme="light" data-page="admin">
  <a class="pf-v6-c-skip-to-content pf-v6-c-button pf-m-primary" href="#main-content">Skip to content</a>

%(sprite)s
  <ul class="pf-v6-c-alert-group pf-m-toast toast-container" id="toastContainer" role="list"
      aria-live="polite" aria-atomic="true"></ul>

  <div class="pf-v6-c-page">
    <header class="pf-v6-c-masthead pf-m-display-inline-on-md" role="banner">
      <div class="pf-v6-c-masthead__main">
        <div class="pf-v6-c-masthead__brand">
          <div class="pf-v6-c-masthead__logo brand">
            <span aria-hidden="true"><img class="pf-v6-c-brand brand-mark"
                 src="{{ static_url('img/mabc-mark.png') }}" width="208" height="208" alt=""></span>
            <span>EzySpeech Admin</span>
          </div>
        </div>
      </div>

      <div class="pf-v6-c-masthead__content">
%(back)s
%(logout)s
      </div>
    </header>

    <div class="pf-v6-c-page__main-container">
      <main class="pf-v6-c-page__main" id="main-content" tabindex="-1">
        <section class="pf-v6-c-page__main-section">
          <div class="pf-v6-c-page__main-body config-page">
            <div class="content-header">
              <h1 class="pf-v6-c-title pf-m-2xl">Settings</h1>
            </div>
            <p class="pf-v6-c-form__helper-text config-page__intro">
              These are the settings in <code id="configPath">config/config.yaml</code>.
              Ports, secrets and the servers themselves only take effect after a
              restart. The admin password and the signing keys are held in
              <code>config/secrets.key</code> and are not editable here.
            </p>

%(cards)s%(advanced)s
          </div>
        </section>
      </main>
    </div>
  </div>

  <!-- The save bar, shown by config.js once something has changed. -->
  <div class="config-actions" id="configActions" hidden role="region" aria-label="Unsaved changes">
    <span class="config-actions__count" id="configDirtyCount" role="status" aria-live="polite"></span>
%(discard)s
%(save)s
  </div>

  <!-- The gate. config.js asks for the password again before it loads anything. -->
  <div class="pf-v6-c-backdrop app-modal" id="configPasswordModal"
       onclick="if(event.target===this)cancelConfigGate()">
    <div class="pf-v6-c-modal-box pf-m-sm" role="dialog" aria-modal="true"
         aria-labelledby="configPasswordModalTitle">
      <header class="pf-v6-c-modal-box__header">
        <h1 class="pf-v6-c-modal-box__title pf-m-icon" id="configPasswordModalTitle">
          <span class="pf-v6-c-modal-box__title-icon">%(lock)s</span>
          <span class="pf-v6-c-modal-box__title-text">Confirm identity</span>
        </h1>
      </header>
      <div class="pf-v6-c-modal-box__body">
        <p class="pf-v6-c-modal-box__description">Enter your admin password to open
          the settings.</p>
        <span class="pf-v6-c-form-control">
          <input type="password" id="configPasswordInput" placeholder="Admin password"
                 aria-label="Admin password"
                 onkeydown="if(event.key==='Enter')confirmConfigGate()">
        </span>
      </div>
      <footer class="pf-v6-c-modal-box__footer">
%(cancel)s
%(confirm)s
      </footer>
    </div>
  </div>

  <script src="{{ static_url('js/i18n.js') }}"></script>
  <script src="{{ static_url('js/config.js') }}"></script>
</body>

</html>
''' % {
        "sprite": sprite(),
        "cards": cards,
        "advanced": advanced_card(),
        "lock": icon("lock"),
        "back": button("Dashboard", "window.location.href='/admin'", "angle-left",
                       "link pf-m-inline", extra=' aria-label="Back to the dashboard"',
                       indent=8),
        "logout": button("Logout", "logout()", "sign-out-alt", "plain masthead-action",
                         extra=' aria-label="Logout"', indent=8),
        "discard": button("Discard", "discardChanges()", None, "link", indent=4),
        "save": button("Save changes", "saveChanges()", "save", "primary",
                       el_id="configSaveButton", indent=4),
        "cancel": button("Cancel", "cancelConfigGate()", None, "link", indent=8),
        "confirm": button("Confirm", "confirmConfigGate()", None, "primary", indent=8),
    }


if __name__ == "__main__":
    out = ROOT / "app/templates/config.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote %s (%d bytes)" % (out.relative_to(ROOT), out.stat().st_size))
