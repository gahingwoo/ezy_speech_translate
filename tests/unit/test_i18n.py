"""Every language has every string the interface shows, with the same
placeholders and line breaks as the English, so no page falls back to English
in the middle of a sentence or prints a {name} it was meant to fill."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='needs node')


@pytest.fixture(scope='module')
def strings():
    script = """
      const vm = require('vm'), fs = require('fs');
      const ctx = { window: {} }; vm.createContext(ctx);
      vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
      process.stdout.write(JSON.stringify(ctx.window.sharedI18n));
    """
    out = subprocess.run(['node', '-e', script, str(ROOT / 'app/i18n/strings.js')],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def placeholders(text):
    return sorted(re.findall(r'\{\w+\}', text or ''))


def test_twenty_six_languages(strings):
    assert len(strings) == 26 and 'en' in strings


def test_no_language_is_missing_a_string(strings):
    en = strings['en']
    missing = {lang: sorted(set(en) - set(table)) for lang, table in strings.items()}
    assert {lang: keys for lang, keys in missing.items() if keys} == {}


def test_placeholders_and_line_breaks_match_the_english(strings):
    en = strings['en']
    wrong = []
    for lang, table in strings.items():
        for key, text in table.items():
            if key not in en or not isinstance(text, str) or not isinstance(en[key], str):
                continue
            if placeholders(text) != placeholders(en[key]):
                wrong.append(f'{lang}.{key}: {placeholders(text)} != {placeholders(en[key])}')
            elif text.count('\n') != en[key].count('\n'):
                wrong.append(f'{lang}.{key}: line breaks')
    assert wrong == []
