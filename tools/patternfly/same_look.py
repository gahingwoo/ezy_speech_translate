"""Does a page look the same with its own stylesheet as with the full one?

    python tools/patternfly/same_look.py PAGE [--phone] [--password PW]

PAGE is user, admin, config, login, projection or transcript; the console's
pages and a transcript need the admin password.

Opens the page in Chromium, puts it in each state a reader can reach (PAGES:
a dialog open, the other theme, phone and desktop width), and in each reads
the computed style of every element and its ::before and ::after, first with
the page's own stylesheet (patternfly-PAGE.css) and then, in the same page,
with the full patternfly.css. Any property that differs is printed, with the
element; nothing printed means nothing a reader can see has changed. Needs a
running listener server with a line or two said (tests/smoke/check.py live),
and Playwright for Python.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu). AGPL-3.0-or-later; see LICENSE.
"""
import argparse
import sys

from playwright.sync_api import sync_playwright

# Each page: where it is (U the listener server, A the console's), whether
# it is behind the console's sign-in, what shows it is ready, and the states
# to compare, each (name, script that gets there) on a fresh page.
LISTENER_INIT = ("localStorage.setItem('targetLang','zh');"
                 "localStorage.setItem('onboardingSeen_v1','1');")
PAGES = {
    'user': {
        'url': 'U/?room=main', 'wait': '#translationsList .translation-card', 'init': LISTENER_INIT,
        'states': [
            ('lines', ''),
            ('dark', "document.documentElement.classList.add('pf-v6-theme-dark')"),
            ('settings view', "showSettings(); showSettingsTab('view')"),
            ('settings language', "showSettings(); showSettingsTab('language')"),
            ('settings speech', "showSettings(); showSettingsTab('speech')"),
            ('settings bible', "showSettings(); showSettingsTab('bible')"),
            ('settings export', "showSettings(); showSettingsTab('export')"),
            ('settings dark', "document.documentElement.classList.add('pf-v6-theme-dark'); showSettings()"),
            ('language', 'showLanguageDialog()'),
            ('about', 'showAbout()'),
            ('shortcuts', 'showShortcuts()'),
            ('tour', 'showTour()'),
            ('marks', 'showMarks()'),
            ('mobile menu', 'toggleMobileMenu()'),
            ('mobile search', 'toggleMobileSearch()'),
            ('toasts', "['info', 'success', 'warning', 'danger'].forEach(t => showToast('A ' + t, t, 60000))"),
            ('toasts dark', "document.documentElement.classList.add('pf-v6-theme-dark');"
                            " ['info', 'success', 'warning', 'danger'].forEach(t => showToast('A ' + t, t, 60000))"),
            ('offline', "setConnectionStatus('offline')"),
            ('announcement', "showAnnouncement('Notice for everyone', 0, 'warning')"),
            ('wechat notice', "document.getElementById('wechatHint').hidden = false"),
            # Only where a line has named a passage (Bible detection on)
            ('passage', "showPassage(translations.find(t => (t.bible_refs || []).length).bible_refs[0])", 'optional'),
            ('jump links', "document.querySelector('#jumpNav .pf-v6-c-jump-links__toggle button').click()"),
            ('welcome', 'FIRST_VISIT'),
            ('welcome dark', 'FIRST_VISIT_DARK'),
        ],
    },
    'admin': {
        'url': 'A/admin', 'signed_in': True, 'wait': '#statusBadge.online',
        'states': [
            ('session', ''),
            ('dark', "document.documentElement.classList.add('pf-v6-theme-dark')"),
            ('hearing', "document.querySelector('#sidebar a[href=\"#hearing\"]').click()"),
            ('transcript', "document.querySelector('#sidebar a[href=\"#transcript\"]').click()"),
            ('past services', "document.querySelector('#sidebar a[href=\"#past-services\"]').click()"),
            ('past services dark', "document.documentElement.classList.add('pf-v6-theme-dark'); document.querySelector('#sidebar a[href=\"#past-services\"]').click()"),
            ('toasts', "['info', 'success', 'warning', 'danger'].forEach(t => showToast('A ' + t, t, 60000))"),
            ('aboutModal', "document.getElementById('aboutModal').classList.add('active')"),
            ('configPasswordModal', "document.getElementById('configPasswordModal').classList.add('active')"),
            ('correctionModal', "document.getElementById('correctionModal').classList.add('active')"),
            ('exportModal', "document.getElementById('exportModal').classList.add('active')"),
            ('inputModal', "document.getElementById('inputModal').classList.add('active')"),
            ('preflightModal', "document.getElementById('preflightModal').classList.add('active')"),
            ('recordingLockModal', "document.getElementById('recordingLockModal').classList.add('active')"),
            ('roomManagerModal', "document.getElementById('roomManagerModal').classList.add('active')"),
            ('settingsModal', "document.getElementById('settingsModal').classList.add('active')"),
            ('shortcutsModal', "document.getElementById('shortcutsModal').classList.add('active')"),
        ],
    },
    'config': {
        'url': 'A/config', 'signed_in': True, 'wait': 'form, .pf-v6-c-form',
        'states': [
            ('settings', ''),
            ('dark', "document.documentElement.classList.add('pf-v6-theme-dark')"),
            ('toasts', "['info', 'success', 'warning', 'danger'].forEach(t => showToast('A ' + t, t, 60000))"),
            ('configPasswordModal', "document.getElementById('configPasswordModal').classList.add('active')"),
        ],
    },
    'login': {
        'url': 'A/login', 'wait': '#loginButton',
        'states': [
            ('form', ''),
            ('dark', "document.documentElement.classList.add('pf-v6-theme-dark')"),
            ('refused', "const e = document.getElementById('loginError'); e.textContent = 'Wrong'; e.style.display = 'block'"),
        ],
    },
    'projection': {
        'url': 'U/projection?room=main&lang=zh', 'wait': '#projNow',
        'states': [
            ('screen', ''),
            ('dark', "document.documentElement.classList.add('pf-v6-theme-dark')"),
            ('setup', 'openSetup()'),
        ],
    },
    'transcript': {
        'url': 'TRANSCRIPT', 'wait': '.transcript-paragraph',
        'states': [
            ('text', ''),
            ('dark', "document.documentElement.classList.add('pf-v6-theme-dark')"),
        ],
    },
}

SNAPSHOT = """() => {
  const out = {};
  const els = document.querySelectorAll('*');
  els.forEach((el, i) => {
    const key = i + ':' + el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
      + (el.className && el.className.baseVal === undefined ? '.' + String(el.className).trim().split(/\\s+/).slice(0, 3).join('.') : '');
    for (const pseudo of [null, '::before', '::after']) {
      const cs = getComputedStyle(el, pseudo);
      if (pseudo && (cs.content === 'none' || cs.content === 'normal')) continue;
      const style = {};
      for (let k = 0; k < cs.length; k++) {
        const prop = cs[k];
        if (prop.startsWith('--')) continue;      // tokens; what they do shows in the rest
        style[prop] = cs.getPropertyValue(prop);
      }
      out[key + (pseudo || '')] = style;
    }
  });
  return out;
}"""

SWAP = """async (to) => {
  const link = [...document.querySelectorAll('link[rel=stylesheet]')]
    .find(l => /patternfly\\/patternfly(-[a-z]+)?\\.css/.test(l.href));
  const href = link.href.replace(/patternfly(-[a-z]+)?\\.css/, to);
  await new Promise(done => {
    const next = document.createElement('link');
    next.rel = 'stylesheet'; next.href = href; next.onload = done; next.onerror = done;
    link.after(next); link.remove();
  });
  await new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)));
}"""


def transcript_path(admin, listener, user, password):
    """A service's transcript, by the console's own link to it."""
    import hashlib
    import requests
    token = requests.post(f'{admin}/api/login', timeout=10, json={
        'username': user, 'password_hash': hashlib.sha256(password.encode()).hexdigest()}).json()['token']
    service = requests.get(f'{listener}/api/transcripts', timeout=10,
                           headers={'Authorization': 'Bearer ' + token}).json()['services'][0]
    return service['path'] + '&lang=zh'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('page', choices=sorted(PAGES))
    p.add_argument('--base', default='http://127.0.0.1')
    p.add_argument('--port', type=int, default=1915)
    p.add_argument('--admin-port', type=int, default=1916)
    p.add_argument('--user', default='admin')
    p.add_argument('--password', help='for the console and its pages, and a transcript')
    p.add_argument('--phone', action='store_true', help='phone width only (quicker)')
    args = p.parse_args()
    listener, admin = f'{args.base}:{args.port}', f'{args.base}:{args.admin_port}'
    spec = PAGES[args.page]
    url = spec['url']
    if url == 'TRANSCRIPT':
        url = listener + transcript_path(admin, listener, args.user, args.password)
    url = url.replace('U/', listener + '/', 1).replace('A/', admin + '/', 1)
    differences = unreached = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        widths = ((390, 844, True),) if args.phone else ((390, 844, True), (1440, 900, False))
        for width, height, mobile in widths:
            for name, action, *optional in spec['states']:
                if mobile is False and name.startswith('mobile'):
                    continue
                ctx = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=mobile,
                                          reduced_motion='reduce')
                first = action.startswith('FIRST_VISIT')
                init = spec.get('init', '')
                if first:                               # the listener's first visit
                    init = "localStorage.setItem('targetLang','zh');" + (
                        "localStorage.setItem('theme','dark');" if action == 'FIRST_VISIT_DARK' else '')
                if init:
                    ctx.add_init_script(init)
                page = ctx.new_page()
                if spec.get('signed_in'):
                    page.goto(f'{admin}/login')
                    page.fill('#username', args.user)
                    page.fill('#password', args.password)
                    page.click('#loginButton')
                    page.wait_for_url('**/admin**', timeout=20000)
                page.goto(url, wait_until='load')
                if not first:
                    page.wait_for_selector(spec['wait'], timeout=20000)
                try:
                    if action and not first:
                        page.evaluate(f'() => {{ {action} }}')
                except Exception as exc:                # a state it could not reach
                    print(f'SKIP  {width}px {name}: {str(exc).splitlines()[0]}')
                    unreached += not optional
                    ctx.close()
                    continue
                # Transitions and animations off, the same for both: a
                # stylesheet swapped in restarts them, and a value caught
                # half-way is timing, not a difference.
                page.add_style_tag(content='*, *::before, *::after { transition: none !important;'
                                           ' animation: none !important; }')
                page.wait_for_timeout(1500)
                # Own, full, own again: what the page did by itself meanwhile
                # (a translation arriving, a banner on a timer) differs
                # between the two of its own as well, and is not counted.
                own = page.evaluate(SNAPSHOT)
                page.evaluate(SWAP, 'patternfly.css')
                page.wait_for_timeout(300)
                full = page.evaluate(SNAPSHOT)
                page.evaluate(SWAP, f'patternfly-{args.page}.css')
                page.wait_for_timeout(300)
                again = page.evaluate(SNAPSHOT)
                found, moved = [], 0
                for key, b in full.items():
                    a, c = own.get(key), again.get(key)
                    if a is None or c is None:          # came or went by itself
                        moved += 1
                        continue
                    if any(a.get(prop) != c.get(prop) for prop in b):
                        moved += 1
                    for prop, value in b.items():
                        if a.get(prop) == c.get(prop) != value:
                            found.append(f'{key} {prop}: own {a.get(prop)!r}, full {value!r}')
                label = f'{width}px {name}'
                note = f', {moved} changed by themselves' if moved else ''
                if found:
                    differences += len(found)
                    print(f'DIFF  {label}: {len(found)}{note}')
                    for line in found[:15]:
                        print('      ' + line)
                else:
                    print(f'same  {label} ({len(full)} elements{note})')
                ctx.close()
        browser.close()
    sys.exit(1 if differences or unreached else 0)


if __name__ == '__main__':
    main()
