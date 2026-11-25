"""A page's own PatternFly stylesheet, with only what the page can use, so a
phone parses what it shows and not the console's wizard, tables and drag and
drop as well. Run by build.sh:

    python3 tools/patternfly/page_css.py PACKAGE OUT PAGE[,PAGE...] -- PART...

PACKAGE is the unpacked @patternfly/patternfly, OUT the folder written to,
PART the component and layout files build.sh assembles (Button/button,
layouts/Flex/flex, ...), in its order. For each page (PAGES: its generated
template) it reads the template and every script it loads, and writes
OUT/patternfly-PAGE.css in four steps:

  1. parts: the base, and each part whose own block (the one it names most)
     the page names;
  2. minified: comments and blank space out;
  3. rules: a rule goes when each of its selectors names a PatternFly class
     (pf-v6-c-..., pf-m-...) that nothing on the page names. A class inside
     :not(), :is(), :where() or :has() does not count against a rule, so
     when in doubt a rule stays;
  4. tokens: a custom property goes when nothing left refers to it, directly
     or through another: not a rule, not the page's own stylesheets, not
     its template or scripts.

A class put together in a script ('pf-v6-c-' + name, `pf-m-${state}`) could
not be seen, so one fails the build instead. tools/patternfly/same_look.py
checks the result against the full stylesheet in a browser, element by
element.

Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu). AGPL-3.0-or-later; see LICENSE.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Each page with a stylesheet of its own, by its generated template.
PAGES = {
    'user': 'app/templates/user.html',
    'admin': 'app/templates/admin.html',
    'config': 'app/templates/config.html',
    'login': 'app/templates/login.html',
    'projection': 'app/templates/projection.html',
    'transcript': 'app/templates/transcript.html',
}

BLOCK = re.compile(r'pf-v6-([cl])-([a-z0-9]+(?:-[a-z0-9]+)*)')
CLASS_NAME = re.compile(r'pf-(?:v6-[clu]-|m-|v6-theme-)[a-z0-9]+(?:[-_]+[a-z0-9]+)*')
CLASS_IN_SELECTOR = re.compile(r'\.(' + CLASS_NAME.pattern + r')')
ASSEMBLED = re.compile(r'''pf-(?:v6-[cl]-|m-)['"`]\s*\+|pf-(?:v6-[cl]-|m-)\$\{''')
STATIC = re.compile(r"""static_url\('([^']+)'\)""")
TOKEN_DECL = re.compile(r'(?<=[{;])(--[\w-]+):')
VAR = re.compile(r'var\((--[\w-]+)')
TOKEN_NAME = re.compile(r'--pf-[\w-]+')


def sources(page):
    """The template, and the scripts it loads from this app."""
    template = ROOT / PAGES[page]
    yield template
    for path in STATIC.findall(template.read_text(encoding='utf-8')):
        if path.endswith('.js'):
            yield ROOT / 'app' / 'static' / path


def own_stylesheets(page):
    """The page's own stylesheets (not PatternFly's): what they refer to stays."""
    template = (ROOT / PAGES[page]).read_text(encoding='utf-8')
    for path in STATIC.findall(template):
        if path.endswith('.css') and not path.startswith('patternfly/'):
            yield ROOT / 'app' / 'static' / path


def page_text(page):
    texts = []
    for path in sources(page):
        text = path.read_text(encoding='utf-8')
        if ASSEMBLED.search(text):
            raise SystemExit(f'{path}: a PatternFly class put together in code; '
                             'page_css.py cannot see which it is')
        texts.append(text)
    return '\n'.join(texts)


def own_block(css):
    """The block a part is about: the one it names most. (A part names other
    blocks too, as the login styles its buttons; those do not bring it in.)"""
    counts = {}
    for kind, name in BLOCK.findall(css):
        block = (kind, name.split('__')[0])
        counts[block] = counts.get(block, 0) + 1
    return max(counts, key=counts.get)


def minify(css):
    """Comments and blank space out; strings and url() left as they are."""
    out, i, n = [], 0, len(css)
    while i < n:
        c = css[i]
        if css.startswith('/*', i):
            end = css.find('*/', i + 2)
            i = n if end < 0 else end + 2
            continue
        if c in '"\'':
            end = _string_end(css, i)
            out.append(css[i:end])
            i = end
            continue
        if c.isspace():
            while i < n and css[i].isspace():
                i += 1
            prev = out[-1][-1] if out and out[-1] else ''
            nxt = css[i] if i < n else ''
            # (Not before ':': '.a :is(.b)' is a descendant, '.a:is(.b)' the same element.)
            if prev and nxt and prev not in '{};:,>(' and nxt not in '{};,>)!':
                out.append(' ')
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def _string_end(css, i):
    quote, j = css[i], i + 1
    while j < len(css) and css[j] != quote:
        j += 2 if css[j] == '\\' else 1
    return j + 1


def _block_end(css, i):
    """css[i] is '{': the index after its matching '}'."""
    depth, j = 0, i
    while j < len(css):
        c = css[j]
        if c in '"\'':
            j = _string_end(css, j)
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError('unbalanced braces')


def _top_level_commas(selector):
    parts, depth, start = [], 0, 0
    for k, c in enumerate(selector):
        if c in '([':
            depth += 1
        elif c in ')]':
            depth -= 1
        elif c == ',' and depth == 0:
            parts.append(selector[start:k])
            start = k + 1
    parts.append(selector[start:])
    return parts


def _required_classes(selector):
    """The PatternFly classes an element must have for this selector to
    match: not those inside a pseudo-class's parentheses."""
    out, depth = [], 0
    for c in selector:
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif depth == 0:
            out.append(c)
            continue
        out.append(' ')
    return CLASS_IN_SELECTOR.findall(''.join(out))


def keep_rules(css, named):
    """css with each style rule that cannot match on the page taken out, and
    any @media left empty by that."""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j < 0:
            out.append(css[i:])
            break
        head = css[i:j]
        end = _block_end(css, j)
        if head.startswith(('@media', '@supports', '@layer', '@container')):
            inner = keep_rules(css[j + 1:end - 1], named)
            if inner:
                out.append(head + '{' + inner + '}')
        elif head.startswith('@') or any(
                all(c in named for c in _required_classes(one)) for one in _top_level_commas(head)):
            out.append(css[i:end])
        i = end
    return ''.join(out)


def _declarations(css):
    """(start, end, name) of each custom property declared, end at its ; or }."""
    found = []
    for m in TOKEN_DECL.finditer(css):
        k, depth = m.end(), 0
        while k < len(css):
            c = css[k]
            if c in '"\'':
                k = _string_end(css, k)
                continue
            if c in '([':
                depth += 1
            elif c in ')]':
                depth -= 1
            elif c in ';}' and depth == 0:
                break
            k += 1
        found.append((m.start(), k, m.group(1)))
    return found


def keep_tokens(css, also_named):
    """css without the custom properties nothing refers to. also_named: the
    text of the page's own stylesheets, template and scripts."""
    decls = _declarations(css)
    values = {}
    for start, end, name in decls:
        values.setdefault(name, []).append(css[start:end])
    outside = list(css)
    for start, end, _ in decls:
        outside[start:end] = ' ' * (end - start)
    needed = set(VAR.findall(''.join(outside))) | set(TOKEN_NAME.findall(also_named))
    todo = list(needed)
    while todo:
        for value in values.get(todo.pop(), []):
            for ref in VAR.findall(value):
                if ref not in needed:
                    needed.add(ref)
                    todo.append(ref)
    out, last = [], 0
    for start, end, name in decls:
        if name in needed:
            continue
        out.append(css[last:start])
        last = end + 1 if end < len(css) and css[end] == ';' else end
    out.append(css[last:])
    # A rule left with nothing in it (and then an @media), or a stray ';'
    css = ''.join(out).replace(';}', '}')
    while True:
        tidier = re.sub(r'[^{}]+\{\}', '', css)
        if tidier == css:
            return css
        css = tidier


def main(argv):
    package, out, pages = Path(argv[0]), Path(argv[1]), argv[2].split(',')
    parts = argv[argv.index('--') + 1:]
    version = re.search(r'"version":\s*"([^"]+)"', (package / 'package.json').read_text()).group(1)
    base = (package / 'patternfly-base.css').read_text(encoding='utf-8')
    texts = []
    for part in parts:
        folder, name = ('layouts', part.split('/', 1)[1]) if part.startswith('layouts/') else ('components', part)
        texts.append((part, (package / folder / f'{name}.css').read_text(encoding='utf-8')))
    for page in pages:
        text = page_text(page)
        blocks = {(kind, name.split('__')[0]) for kind, name in BLOCK.findall(text)}
        named = set(CLASS_NAME.findall(text))
        kept = [(part, css) for part, css in texts if own_block(css) in blocks]
        css = minify('\n'.join([base] + [c for _, c in kept]))
        css = keep_rules(css, named)
        css = keep_tokens(css, text + '\n'.join(p.read_text(encoding='utf-8') for p in own_stylesheets(page)))
        head = (f'/* Built by tools/patternfly/build.sh from @patternfly/patternfly {version} for the '
                f'{page} page (tools/patternfly/page_css.py): {", ".join(p for p, _ in kept)}. Do not edit. */\n')
        target = out / f'patternfly-{page}.css'
        target.write_text(head + css + '\n', encoding='utf-8')
        print(f'{target}: {len(kept)} of {len(texts)} parts, {target.stat().st_size // 1024} KB')


if __name__ == '__main__':
    main(sys.argv[1:])
