"""Change single values in config.yaml without disturbing the rest of it.

The file is the documentation as much as the settings: every line carries a
comment saying what it is for. Dumping the parsed YAML back out would throw
all of that away, so a change rewrites only the value on the line it names.
Used by the settings screen and by the container's first-run setup.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)

This file is part of EzySpeech, and is free software under the GNU Affero
General Public License, version 3 or later. See LICENSE and TRADEMARK.md.
"""

import re

import yaml

_KEY_LINE = re.compile(r'^(?P<indent>[ ]*)(?P<key>[A-Za-z0-9_]+)[ ]*:(?P<rest>.*)$')


def _scalar_text(value):
    """One scalar, written the way YAML writes it."""
    text = yaml.safe_dump(value, default_flow_style=True, allow_unicode=True).rstrip()
    if text.endswith('\n...'):
        text = text[:-4].rstrip()
    return text


def _split_comment(rest):
    """The value and the trailing comment on a `key: value  # why` line.
    None when the line is not a plain scalar this can safely rewrite."""
    value, comment, quote = [], '', ''
    for i, ch in enumerate(rest):
        if quote:
            if ch == quote:
                quote = ''
        elif ch in ('"', "'"):
            quote = ch
        elif ch == '#' and (not value or value[-1] in ' \t'):
            comment = rest[i:]
            break
        value.append(ch)
    if quote:
        return None                       # an unterminated quote: leave it be
    joined = ''.join(value)
    if not joined.strip():
        return None                       # a mapping or a block, not a scalar
    if joined.lstrip()[0] in ('&', '*', '|', '>'):
        return None                       # anchors and block scalars
    return joined, comment


def write_in_place(text, changes):
    """Rewrite the values of named scalars and leave the rest of the file — its
    comments, its order, its blank lines — exactly as it was.

    Returns the new text, or None when a path could not be found on a line this
    can safely rewrite, so the caller falls back to dumping the document.
    """
    lines = text.split('\n')
    stack, done = [], set()
    for n, line in enumerate(lines):
        match = _KEY_LINE.match(line)
        if not match:
            continue
        indent = len(match.group('indent'))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, match.group('key')))
        path = '.'.join(key for _, key in stack)
        if path not in changes or path in done:
            continue
        split = _split_comment(match.group('rest'))
        if split is None:
            return None
        comment = split[1]
        prefix = line[:line.index(':', indent) + 1]
        written = prefix + ' ' + _scalar_text(changes[path])
        if comment:
            # Put the comment back in the column it was in, so a file that
            # lines its comments up stays lined up.
            column = len(line) - len(comment)
            written += ' ' * max(1, column - len(written)) + comment
        lines[n] = written
        done.add(path)

    if done != set(changes):
        return None
    return '\n'.join(lines)
