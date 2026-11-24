"""The translation service, with stand-in providers: the order it asks them
in, what a refusal does, the cache, the glossary, and how it reports health."""
import requests

from app.services.translation._impl import GoogleTranslateService, TranslationHealth
from app.services.translation.backends import Backend, EchoBackend, providers_from, build_backends


class Refuses(Backend):
    def __init__(self, name='refuser', status=429):
        self.name, self.status, self.calls = name, status, 0

    def translate(self, text, lang, timeout):
        self.calls += 1
        response = requests.Response()
        response.status_code = self.status
        raise requests.exceptions.HTTPError(response=response)


class Answers(Backend):
    def __init__(self, name='answers', fn=None):
        self.name, self.fn, self.calls, self.seen = name, fn or (lambda t, l: f'<{l}>{t}'), 0, []

    def translate(self, text, lang, timeout):
        self.calls += 1
        self.seen.append(text)
        return self.fn(text, lang)


def service(*backends):
    return GoogleTranslateService(backends=list(backends))


def test_the_first_provider_that_answers_is_used():
    first, second = Refuses('first'), Answers('second')
    ok, text, cached = service(first, second).translate('Grace and peace', 'zh')
    assert (ok, text, cached) == (True, '<zh>Grace and peace', False)
    assert first.calls == 1 and second.calls == 1


def test_a_refusal_is_not_retried():
    refuser = Refuses()
    ok, text, _ = service(refuser).translate('Grace and peace', 'zh')
    assert (ok, text) == (False, 'Grace and peace')
    assert refuser.calls == 1


def test_an_answer_is_cached():
    answers = Answers()
    s = service(answers)
    s.translate('Grace and peace', 'zh')
    ok, text, cached = s.translate('Grace and peace', 'zh')
    assert (ok, cached, answers.calls) == (True, True, 1)


def test_glossary_terms_reach_the_provider_as_placeholders_and_come_back():
    answers = Answers(fn=lambda t, l: t.replace('We remember', '我们记念'))
    glossary = [{'source_term': "Lord's Supper", 'translation': '主的晚餐', 'case_sensitive': False}]
    ok, text, _ = service(answers).translate("We remember the Lord's Supper", 'zh', glossary=glossary)
    assert "Lord's Supper" not in answers.seen[0]
    assert ok and '主的晚餐' in text


def test_no_spaces_round_a_chinese_glossary_term():
    # The provider spaces a Latin placeholder as it would an English word.
    answers = Answers(fn=lambda t, l: '我们在 ' + t.split(' ', 2)[-1].replace('at ', '') + ' 中记念他')
    glossary = [{'source_term': "Lord's Supper", 'translation': '主的晚餐', 'case_sensitive': False}]
    ok, text, _ = service(answers).translate("We remember at Lord's Supper", 'zh', glossary=glossary)
    assert ok and '在主的晚餐中' in text, text


def test_spaces_stay_round_an_english_glossary_term():
    s = service(EchoBackend())
    placeholder = s._PH_PREFIX + '000' + s._PH_SUFFIX
    assert s._apply_glossary_restore(f'We praise the {placeholder} today',
                                     {placeholder: 'Lord'}) == 'We praise the Lord today'


def test_health_ok_degraded_failing():
    h = TranslationHealth()
    assert h.summary('google_web')['state'] == 'ok'
    h.record('deepl', [('google_web', 'refused (429)')])
    assert h.summary('google_web')['state'] == 'degraded'
    h = TranslationHealth()
    for _ in range(4):
        h.record(None, [('google_web', 'refused (429)')])
    summary = h.summary('google_web')
    assert summary['state'] == 'failing' and summary['failed'] == 4


def test_the_service_reports_its_own_health():
    s = service(Refuses('google_web'))
    for n in range(3):
        s.translate(f'line {n}', 'zh')
    assert s.health_summary()['state'] == 'failing'


def test_providers_from_a_string_or_a_list():
    assert providers_from('deepl, google_web') == ['deepl', 'google_web']
    assert providers_from(['DeepL', ' echo ']) == ['deepl', 'echo']
    assert providers_from('') == []


def test_a_provider_without_its_key_is_left_out():
    settings = {'providers': 'deepl, echo', 'deepl_api_key': ''}
    names = [b.name for b in build_backends(requests.Session(), lambda k, d=None: settings.get(k, d))]
    assert names == ['echo']
