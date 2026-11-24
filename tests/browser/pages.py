"""The pages, in a real browser, against an installed EzySpeech: each opens
without a script error and does the one thing it is for.

    python tests/browser/pages.py --password PW [--base http://127.0.0.1]

Run after tests/smoke/check.py live, which has said a line, so there is a
line to mark and a service to open. Needs Playwright for Python and its
Chromium (pip install playwright; python -m playwright install chromium).
"""
import argparse
import hashlib
import sys

import requests
from playwright.sync_api import sync_playwright

p = argparse.ArgumentParser()
p.add_argument('--base', default='http://127.0.0.1')
p.add_argument('--port', type=int, default=1915)
p.add_argument('--admin-port', type=int, default=1916)
p.add_argument('--user', default='admin')
p.add_argument('--password', required=True)
ARGS = p.parse_args()
U, A = f'{ARGS.base}:{ARGS.port}', f'{ARGS.base}:{ARGS.admin_port}'
problems = []


def ok(message):
    print(f'ok    {message}', flush=True)


def check(cond, message):
    if cond:
        ok(message)
    else:
        problems.append(message)
        print(f'FAIL  {message}', flush=True)


def watch(page, name):
    errors = []
    page.on('pageerror', lambda e: errors.append(f'{name}: {e}'))
    return errors


with sync_playwright() as pw:
    browser = pw.chromium.launch()

    # The listener page, on a phone: a line, its star, the marked lines.
    phone = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True)
    phone.add_init_script("localStorage.setItem('onboardingSeen_v1','1');"
                          "localStorage.setItem('targetLang','zh');")
    page = phone.new_page()
    errors = watch(page, 'listener')
    page.goto(f'{U}/?room=main')
    page.wait_for_selector('#translationsList .translation-card', timeout=20000)
    check(page.locator('#translationsList .translation-card').count() > 0, 'listener shows the lines said')
    page.locator('#translationsList .mark-btn').first.click()
    check(page.locator('#marksCount').inner_text().strip() == '1', 'a line is marked')
    page.evaluate('showMarks()')
    check(page.locator('#marksBody .marks-line').count() == 1, 'the marked line is listed')
    manifest = requests.get(f'{U}/manifest.webmanifest', timeout=10)
    check(manifest.status_code == 200 and manifest.json().get('display') == 'standalone',
          'the page can be added to a home screen')
    check(not errors, 'listener without script errors ' + '; '.join(errors))

    # The console: signed in, live, and its past services.
    desk = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = desk.new_page()
    errors = watch(page, 'console')
    page.goto(f'{A}/login')
    page.fill('#username', ARGS.user)
    page.fill('#password', ARGS.password)
    page.click('#loginButton')
    page.wait_for_url('**/admin**', timeout=20000)
    # (A selector, not a function: the console's CSP has no unsafe-eval.)
    page.wait_for_selector('#statusBadge.online', timeout=20000)
    ok('console signed in and online')
    page.click('#sidebar a[href="#past-services"]')
    page.wait_for_selector('#servicesMonths .pf-v6-c-card', timeout=20000)
    check(page.locator('#servicesMonths tbody tr').count() >= 1, 'past services lists the service')
    check(not errors, 'console without script errors ' + '; '.join(errors))

    # The service's transcript, by the console's own link.
    token = requests.post(f'{A}/api/login', timeout=10, json={
        'username': ARGS.user, 'password_hash': hashlib.sha256(ARGS.password.encode()).hexdigest()}).json()['token']
    service = requests.get(f'{U}/api/transcripts', timeout=10,
                           headers={'Authorization': 'Bearer ' + token}).json()['services'][0]
    page = desk.new_page()
    errors = watch(page, 'transcript')
    page.goto(U + service['path'] + '&lang=zh')
    check(page.locator('.transcript-paragraph').count() >= 1, 'the transcript opens by its link')
    check(not errors, 'transcript without script errors ' + '; '.join(errors))

    # The projection screen.
    page = desk.new_page()
    errors = watch(page, 'projection')
    page.goto(f'{U}/projection?room=main&lang=zh')
    page.wait_for_timeout(2500)
    check(page.locator('#projNow').count() == 1, 'the projection screen opens')
    check(not errors, 'projection without script errors ' + '; '.join(errors))

    browser.close()

if problems:
    print(f'{len(problems)} failed', file=sys.stderr)
    sys.exit(1)
print('passed')
