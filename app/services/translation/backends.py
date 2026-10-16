"""Where translations come from.

Each backend turns a line into another language, or returns None when it
cannot (that language, that moment). The service tries them in the order
config.yaml names them, so a paid, official one can stand behind the free
endpoint, or replace it:

    translation:
      providers: "google_web, deepl"

    google_web      Google's web endpoint: no key, and the default. It is not a
                    published API; it can refuse a server outright (429), and
                    the listener's browser then asks it directly instead.
    deepl           DeepL's API (deepl_api_key; a free-plan key ends in ":fx")
    google_cloud    Google Cloud Translation (google_cloud_api_key)
    libretranslate  a LibreTranslate server, such as one run on this machine
                    (libretranslate_url, and libretranslate_api_key if it asks)
    echo            for tests: "[zh] text", without leaving the machine

Keys are secrets: the settings page shows them as *** and does not change
them; set them in config.yaml (or the page's raw editor).

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)
This file is part of EzySpeech, and is free software under the GNU Affero
General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class Backend:
    name = "?"

    def supports(self, lang: str) -> bool:
        return True

    def translate(self, text: str, lang: str, timeout: float) -> Optional[str]:
        """The translation, or None. Network trouble is raised: the service
        retries a timeout and moves on from a refusal."""
        raise NotImplementedError


class GoogleWebBackend(Backend):
    name = "google_web"
    API_URL = "https://translate.googleapis.com/translate_a/single"
    LANG_MAP = {'zh': 'zh-CN', 'zh-tw': 'zh-TW'}

    def __init__(self, session: requests.Session):
        self.session = session

    def translate(self, text, lang, timeout):
        response = self.session.get(self.API_URL, params={
            'client': 'gtx', 'sl': 'auto', 'tl': self.LANG_MAP.get(lang, lang), 'dt': 't', 'q': text,
        }, timeout=timeout)
        response.raise_for_status()
        return self.extract(response.json())

    @staticmethod
    def extract(data) -> Optional[str]:
        """The endpoint answers with nested lists; the first holds the
        translated segments, each starting with its text."""
        if not data or not isinstance(data, list) or not data[0] or not isinstance(data[0], list):
            return None
        parts = [item[0] for item in data[0]
                 if isinstance(item, list) and item and isinstance(item[0], str)]
        return ''.join(parts) or None


class DeepLBackend(Backend):
    name = "deepl"
    # DeepL's target languages, in its own codes
    TARGETS = {
        'ar': 'AR', 'bg': 'BG', 'cs': 'CS', 'da': 'DA', 'de': 'DE', 'el': 'EL',
        'en': 'EN-US', 'es': 'ES', 'et': 'ET', 'fi': 'FI', 'fr': 'FR', 'he': 'HE',
        'hu': 'HU', 'id': 'ID', 'it': 'IT', 'ja': 'JA', 'ko': 'KO', 'lt': 'LT',
        'lv': 'LV', 'nb': 'NB', 'nl': 'NL', 'pl': 'PL', 'pt': 'PT-BR', 'ro': 'RO',
        'ru': 'RU', 'sk': 'SK', 'sl': 'SL', 'sv': 'SV', 'th': 'TH', 'tr': 'TR',
        'uk': 'UK', 'vi': 'VI', 'zh': 'ZH-HANS', 'zh-tw': 'ZH-HANT',
    }

    def __init__(self, session: requests.Session, key: str):
        self.session = session
        self.key = key
        # A free-plan key has its own address
        host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
        self.url = f'https://{host}/v2/translate'

    def supports(self, lang):
        return lang in self.TARGETS

    def translate(self, text, lang, timeout):
        response = self.session.post(self.url, timeout=timeout,
                                     headers={'Authorization': f'DeepL-Auth-Key {self.key}'},
                                     data={'text': text, 'target_lang': self.TARGETS[lang]})
        response.raise_for_status()
        found = response.json().get('translations') or []
        return found[0].get('text') if found else None


class GoogleCloudBackend(Backend):
    name = "google_cloud"
    URL = "https://translation.googleapis.com/language/translate/v2"
    LANG_MAP = {'zh': 'zh-CN', 'zh-tw': 'zh-TW'}

    def __init__(self, session: requests.Session, key: str):
        self.session = session
        self.key = key

    def translate(self, text, lang, timeout):
        response = self.session.post(self.URL, params={'key': self.key}, timeout=timeout,
                                     json={'q': text, 'target': self.LANG_MAP.get(lang, lang),
                                           'format': 'text'})
        response.raise_for_status()
        found = (response.json().get('data') or {}).get('translations') or []
        return found[0].get('translatedText') if found else None


class LibreTranslateBackend(Backend):
    name = "libretranslate"
    LANG_MAP = {'zh-tw': 'zt'}

    def __init__(self, session: requests.Session, url: str, key: str = ''):
        self.session = session
        self.url = url.rstrip('/') + '/translate'
        self.key = key

    def translate(self, text, lang, timeout):
        body = {'q': text, 'source': 'auto', 'target': self.LANG_MAP.get(lang, lang), 'format': 'text'}
        if self.key:
            body['api_key'] = self.key
        response = self.session.post(self.url, json=body, timeout=timeout)
        response.raise_for_status()
        return response.json().get('translatedText') or None


class EchoBackend(Backend):
    """For tests: the line, marked with its language, never sent anywhere."""
    name = "echo"

    def translate(self, text, lang, timeout):
        return f'[{lang}] {text}'


def providers_from(setting) -> list:
    """config's providers: a comma-separated string, or a list."""
    if isinstance(setting, str):
        setting = setting.split(',')
    return [str(p).strip().lower() for p in (setting or []) if str(p).strip()]


def build_backends(session: requests.Session, get) -> list:
    """The backends config.yaml asks for, in its order. `get` reads a
    translation.* setting. One that is named but cannot work (no key) is
    left out, with a warning; with none at all, google_web, as before."""
    out = []
    for name in providers_from(get('providers', 'google_web')):
        if name == 'google_web':
            out.append(GoogleWebBackend(session))
        elif name == 'deepl':
            key = get('deepl_api_key', '')
            if key:
                out.append(DeepLBackend(session, key))
            else:
                logger.warning('Translation provider deepl is named but has no deepl_api_key; skipped')
        elif name == 'google_cloud':
            key = get('google_cloud_api_key', '')
            if key:
                out.append(GoogleCloudBackend(session, key))
            else:
                logger.warning('Translation provider google_cloud is named but has no '
                               'google_cloud_api_key; skipped')
        elif name == 'libretranslate':
            url = get('libretranslate_url', '')
            if url:
                out.append(LibreTranslateBackend(session, url, get('libretranslate_api_key', '')))
            else:
                logger.warning('Translation provider libretranslate is named but has no '
                               'libretranslate_url; skipped')
        elif name == 'echo':
            out.append(EchoBackend())
        else:
            logger.warning('Unknown translation provider %r; skipped', name)
    if not out:
        out.append(GoogleWebBackend(session))
    logger.info('Translation providers, in order: %s', ', '.join(b.name for b in out))
    return out
