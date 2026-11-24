# Tests

| Where | What | Runs in CI |
|---|---|---|
| `unit/` | The code on its own: the database, translation, passwords and tokens, that every language has every string, the sockets (a listener counted and forgotten), the live state hammered from real threads (`test_threads.py`), and the concurrency module each way | the `code` job: `python -m pytest tests/unit` |
| `smoke/check.py` | An installed EzySpeech used from outside, as a speaker, a listener and an admin do | after each of the three installs |
| `browser/pages.py` | The pages in Chromium: listener, console, past services, a transcript, the projection screen | after the native install |

The `code` job also re-runs every generator (the templates, the language
files) and fails if the output differs from what is committed.

Locally:

```bash
python -m pytest -q tests/unit             # needs requirements.txt and pytest; node for the strings
```
