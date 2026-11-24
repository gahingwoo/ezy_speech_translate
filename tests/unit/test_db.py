"""The database: one line per room and number, kept when the screen is
cleared, gathered by service, deleted by service."""
import json
import sqlite3

import pytest

from app import db


@pytest.fixture
def path(tmp_path):
    p = tmp_path / 'translations.db'
    db.init_db(str(p), enabled=True)
    return p


def line(room, n, at, text=None):
    return {'id': n, 'room_id': room, 'original': text or f'{room} line {n}',
            'corrected': text or f'{room} line {n}', 'at': at, 'timestamp': at[11:]}


def test_rooms_keep_their_own_numbers(path):
    db.persist(line('main', 0, '2026-10-25T09:00:00'))
    db.persist(line('youth', 0, '2026-10-25T19:00:00'))
    rows = sqlite3.connect(path).execute(
        'SELECT room_id, id, original FROM translations ORDER BY room_id').fetchall()
    assert rows == [('main', 0, 'main line 0'), ('youth', 0, 'youth line 0')]


def test_next_id_follows_every_kept_line_cleared_or_not(path):
    for n in range(3):
        db.persist(line('main', n, f'2026-10-25T09:0{n}:00'))
    db.clear_live('main')
    assert db.next_id('main') == 3
    assert db.next_id('youth') == 0


def test_clear_takes_lines_off_the_screens_and_keeps_them(path):
    db.persist(line('main', 0, '2026-10-25T09:00:00'))
    db.persist(line('youth', 0, '2026-10-25T19:00:00'))
    db.clear_live('main')
    live = {(i['room_id'], i['id']) for i in db.load_all()}
    assert live == {('youth', 0)}
    assert [l['original'] for l in db.service_lines('main', '2026-10-25')] == ['main line 0']


def test_services_by_room_and_day_newest_first(path):
    db.persist(line('main', 0, '2026-10-18T09:00:00'))
    db.persist(line('main', 1, '2026-10-25T09:00:00'))
    db.persist(line('main', 2, '2026-10-25T10:30:00'))
    db.persist(line('youth', 0, '2026-10-25T19:00:00'))
    got = [(s['room_id'], s['date'], s['lines'], s['first'][11:16], s['last'][11:16])
           for s in db.services()]
    assert got == [('main', '2026-10-25', 2, '09:00', '10:30'),
                   ('youth', '2026-10-25', 1, '19:00', '19:00'),
                   ('main', '2026-10-18', 1, '09:00', '09:00')]


def test_a_line_without_a_date_is_in_no_service(path):
    item = line('main', 0, '2026-10-25T09:00:00')
    item['at'] = None
    db.persist(item)
    assert db.services() == []


def test_delete_service_removes_that_day_only(path):
    db.persist(line('main', 0, '2026-10-18T09:00:00'))
    db.persist(line('main', 1, '2026-10-25T09:00:00'))
    db.persist(line('youth', 0, '2026-10-25T19:00:00'))
    assert db.delete_service('main', '2026-10-25') == 1
    assert [(s['room_id'], s['date']) for s in db.services()] == [
        ('youth', '2026-10-25'), ('main', '2026-10-18')]


def test_a_translation_is_kept_on_its_line(path):
    db.persist(line('main', 0, '2026-10-25T09:00:00', 'Grace and peace'))
    db.save_line_translation('main', 0, 'zh-tw', 'Grace and peace', '恩典與平安')
    db.save_line_translation('main', 0, 'zh', 'Grace and peace', '恩典与平安')
    kept = db.service_lines('main', '2026-10-25')[0]['translations']
    assert kept == {'zh-tw': {'source': 'Grace and peace', 'text': '恩典與平安'},
                    'zh': {'source': 'Grace and peace', 'text': '恩典与平安'}}


def test_a_language_code_that_could_break_the_json_path_is_refused(path):
    db.persist(line('main', 0, '2026-10-25T09:00:00'))
    db.save_line_translation('main', 0, 'zh"]', 'x', 'y')
    assert 'translations' not in db.service_lines('main', '2026-10-25')[0]


def test_an_old_table_keyed_by_number_alone_is_moved_over(tmp_path):
    p = tmp_path / 'old.db'
    c = sqlite3.connect(p)
    c.execute("""CREATE TABLE translations (id INTEGER PRIMARY KEY, ts TEXT NOT NULL,
        original TEXT NOT NULL, corrected TEXT NOT NULL, translated TEXT,
        is_corrected INTEGER DEFAULT 0, source_language TEXT, confidence REAL,
        bible_refs TEXT, raw_json TEXT NOT NULL, room_id TEXT NOT NULL DEFAULT 'main')""")
    for n in range(3):
        c.execute('INSERT INTO translations (id, ts, original, corrected, raw_json) '
                  'VALUES (?,?,?,?,?)', (n, '09:00', f'old {n}', f'old {n}',
                                          json.dumps({'id': n, 'original': f'old {n}'})))
    c.commit()
    c.close()
    db.init_db(str(p), enabled=True)
    c = sqlite3.connect(p)
    key = [(r[1], r[5]) for r in c.execute('PRAGMA table_info(translations)') if r[5]]
    assert key == [('room_id', 1), ('id', 2)]
    assert c.execute('SELECT COUNT(*) FROM translations').fetchone()[0] == 3
    db.init_db(str(p), enabled=True)          # a second start leaves it be
    assert len(db.load_all()) == 3


def test_default_glossary_is_added_once_and_spares_a_church_s_own(tmp_path, path):
    source = tmp_path / 'glossary.json'
    source.write_text(json.dumps({'_about': 'test', 'entries': [
        {'source_term': "Lord's Supper", 'zh': '主的晚餐', 'zh-tw': '主的晚餐'},
        {'source_term': 'Holy Spirit', 'zh': '圣灵'},
    ]}, ensure_ascii=False), encoding='utf-8')
    db.glossary_add('Holy Spirit', 'zh', '聖神', created_by='church')
    added = db.seed_default_glossary(str(source))
    assert added == 2                          # the church's own Holy Spirit stays
    assert db.seed_default_glossary(str(source)) == 0
    terms = {(e['source_term'], e['target_lang']): e['translation'] for e in db.glossary_list()}
    assert terms[('Holy Spirit', 'zh')] == '聖神'
    assert terms[("Lord's Supper", 'zh-tw')] == '主的晚餐'


def test_nothing_is_written_when_the_database_is_off(tmp_path):
    db.init_db(str(tmp_path / 'off.db'), enabled=False)
    db.persist(line('main', 0, '2026-10-25T09:00:00'))
    assert db.load_all() == [] and db.services() == [] and db.next_id('main') == 0
