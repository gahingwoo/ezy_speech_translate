"""The database written after the sending (core.db_write): by one writer, in
order, with nothing lost when the writes for a line arrive in another order
than the line's own events, and without the caller waiting for the disk."""
import threading
import time

import pytest

from app.user import core


@pytest.fixture
def writer(tmp_path):
    """A database of its own and the writer running, as in the server."""
    core.db.init_db(str(tmp_path / 'translations.db'), enabled=True)
    thread = threading.Thread(target=core.db_writer_loop, daemon=True)
    thread.start()
    for _ in range(100):
        if core._db_writer_running:
            break
        time.sleep(0.01)
    yield core.db
    core._db_writes.put(None)
    thread.join(5)
    core.db.init_db(str(tmp_path / 'translations.db'), enabled=False)


@pytest.fixture
def room(request):
    rid = 'writer_' + request.node.name[:40]
    yield rid
    core._rooms.pop(rid, None)


def rows(db, room):
    lines = db.service_lines(room, core.local_now().date().isoformat())
    return {line['id']: line for line in lines}


def say(room, text, translate_at_once=None):
    """A line said, translated (if asked) the moment it has its number, as
    a cached translation is: before its own row is written."""
    def numbered(line):
        if translate_at_once:
            def keep(item):
                item['translations'] = {'zh': {'source': text, 'text': translate_at_once}}
            core.update_line(room, line['id'], keep)
            core.db_write(core.db.save_line_translation, room, line['id'], 'zh', text, translate_at_once)
    return core.add_translation({'original': text, 'corrected': text}, room, on_numbered=numbered)


def test_a_translation_saved_before_its_line_is_kept(writer, room):
    line = say(room, 'Grace and peace', translate_at_once='恩典与平安')
    assert core.db_flush()
    kept = rows(writer, room)[line['id']]
    assert kept['translations']['zh']['text'] == '恩典与平安'


def test_many_lines_in_order_none_lost(writer, room):
    said = [say(room, f'line {n}', translate_at_once=f'第{n}行' if n % 2 else None) for n in range(200)]
    assert core.db_flush()
    kept = rows(writer, room)
    assert sorted(kept) == [line['id'] for line in said]
    assert all(kept[line['id']].get('translations', {}).get('zh', {}).get('text') == f'第{n}行'
               for n, line in enumerate(said) if n % 2)


def test_a_line_deleted_at_once_stays_deleted(writer, room):
    line = say(room, 'Said by mistake')
    core.remove_lines(room, [line['id']])
    core.db_write(lambda: writer.delete_ids([line['id']], room_id=room))
    assert core.db_flush()
    assert line['id'] not in rows(writer, room)


def test_a_screen_cleared_at_once_keeps_the_line_for_the_transcript(writer, room):
    line = say(room, 'Before the clear')
    core.clear_room(room)
    core.db_write(writer.clear_live, room)
    assert core.db_flush()
    assert rows(writer, room)[line['id']]['original'] == 'Before the clear'
    assert not [i for i in writer.load_all() if i.get('room_id') == room]


def test_the_caller_does_not_wait_for_the_disk(writer):
    slow = threading.Event()
    start = time.perf_counter()
    core.db_write(lambda: (time.sleep(0.3), slow.set()))
    assert time.perf_counter() - start < 0.05
    assert core.db_flush() and slow.is_set()


def test_a_write_that_fails_does_not_stop_the_writer(writer, room):
    core.db_write(lambda: 1 / 0)
    line = say(room, 'After a failed write')
    assert core.db_flush()
    assert line['id'] in rows(writer, room)


def test_without_the_writer_a_write_is_made_at_once(tmp_path, room):
    core.db.init_db(str(tmp_path / 'direct.db'), enabled=True)
    try:
        assert not core._db_writer_running
        line = say(room, 'Written at once')
        assert line['id'] in rows(core.db, room)
    finally:
        core.db.init_db(str(tmp_path / 'direct.db'), enabled=False)
