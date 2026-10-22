/* The listener page, part of: Bible references: the Scripture section, a passage and its dialog.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

// ── Language → PrayerPulse language-name mapping ─────────────────────
// Maps UI lang codes to the PrayerPulse language group name and a
// preferred default translation code for that language.
const _LANG_BIBLE = {
    en:      { pp: 'English',             def: 'KJV'    },
    zh:      { pp: 'Chinese',             def: 'CUNPS',  script: 'simplified' },  // simplified → new punct (simplified edition)
    'zh-tw': { pp: 'Chinese',             def: 'CUV',    script: 'traditional' },  // traditional
    yue:     { pp: 'Chinese',             def: 'CUV',    script: 'traditional' },  // Cantonese → traditional
    ja:      { pp: 'Japanese',            def: null     },  // first available
    ko:      { pp: 'Korean',              def: 'KRV'    },
    es:      { pp: 'Spanish',             def: 'RV1960' },
    fr:      { pp: 'French',              def: null     },  // first available
    de:      { pp: 'German',              def: 'ELB'    },
    ru:      { pp: 'Russian',             def: 'SYNOD'  },
    pt:      { pp: 'Portuguese',          def: null     },
    id:      { pp: 'Indonesian',          def: 'TB'     },
    ar:      { pp: 'Arabic',              def: null     },
    hi:      { pp: 'Hindi',               def: null     },
    nl:      { pp: 'Dutch',               def: null     },
    pl:      { pp: 'Polish',              def: null     },
    vi:      { pp: 'Vietnamese',          def: null     },
    tr:      { pp: null,                  def: null     },  // not in PrayerPulse
    th:      { pp: null,                  def: null     },
    it:      { pp: null,                  def: null     },
    ms:      { pp: 'Indonesian',          def: 'TB'     },  // closest available
    ta:      { pp: 'Tamil',               def: null     },
};

// Fetched once from /api/bible/languages and cached in-memory.
// Shape: [{ language: "English", translations: [{short_name, full_name}, ...] }, ...]
let _bibleLanguageData = null;

async function _loadBibleLanguages() {
    if (_bibleLanguageData) return _bibleLanguageData;
    try {
        const r = await fetch('/api/bible/languages');
        if (r.ok) _bibleLanguageData = await r.json();
    } catch (e) { /* offline / not enabled */ }
    return _bibleLanguageData || [];
}

// Classify a Chinese Bible translation as 'simplified' or 'traditional'.
// The bolls.life "Chinese" group mixes both scripts, so we inspect the name:
// explicit English markers first, then simplified/traditional-only characters.
const _ZH_TRAD_CHARS = '聖標點經傳啟後羅馬譯證書現體國語當達靈際東與聞約詩';
const _ZH_SIMP_CHARS = '圣标点经传启后罗马译证书现体国语当达灵际东与闻约诗';
function _zhScriptOf(t) {
    const name = `${(t && t.full_name) || ''} ${(t && t.short_name) || ''}`;
    if (/simplified/i.test(name)) return 'simplified';
    if (/traditional/i.test(name)) return 'traditional';
    let s = 0, tr = 0;
    for (const ch of name) {
        if (_ZH_SIMP_CHARS.includes(ch)) s++;
        else if (_ZH_TRAD_CHARS.includes(ch)) tr++;
    }
    if (s > tr) return 'simplified';
    if (tr > s) return 'traditional';
    // Fallback: an "…S" short name is usually the simplified sibling.
    return /S$/.test((t && t.short_name) || '') ? 'simplified' : 'traditional';
}

/**
 * Populate the target translation <select> with all options from PrayerPulse,
 * putting the user's matched language group first, then everything else.
 * Auto-selects the best default for the given langCode.
 */
/* Editions that do not belong in the same list as the rest.
 *
 * 思高聖經 is a Catholic translation whose book names and verse numbering do
 * not line up with 和合本. A reader who picks it by accident gets references
 * that do not resolve — and in a live service they have no way of knowing
 * that is why. It is left out rather than explained.
 */
const _EXCLUDED_BIBLES = ['CHISB'];

function _excludedBible(t) {
    const code = String(t.short_name || '').toUpperCase();
    const name = String(t.full_name || '');
    return _EXCLUDED_BIBLES.includes(code)
        || name.includes('思高') || /studium biblicum/i.test(name);
}

/* The script of a stored translation code, looked up in the language list we
   already have rather than guessed from the code. */
function _zhScriptOfCode(langData, code) {
    for (const group of langData || []) {
        for (const t of group.translations || []) {
            if (t.short_name === code) return _zhScriptOf(t);
        }
    }
    return null;
}

async function loadBibleTranslationOptions(langCode) {
    const sel = document.getElementById('bibleTargetTranslation');
    if (!sel) return;
    const prevTgt = bibleTargetTrans;

    const langData = await _loadBibleLanguages();
    if (!langData || !langData.length) {
        // Fallback: keep whatever is currently selected
        return;
    }

    const hint = document.getElementById('bibleTransLoadingHint');
    const info = _LANG_BIBLE[langCode] || {};
    const ppLangName = info.pp || null;

    sel.innerHTML = '<option value="">— None —</option>';

    // Only show translations for the user's matched language — no giant global list.
    const matched = langData.filter(g =>
        ppLangName && g.language.toLowerCase().startsWith(ppLangName.toLowerCase())
    ).map(g => Object.assign({}, g, {
        translations: (g.translations || []).filter(t => !_excludedBible(t))
    }));

    // Build options for the matched language group.
    const allMatchedCodes = [];
    const addOptgroup = (label, translations) => {
        if (!translations.length) return;
        const og = document.createElement('optgroup');
        og.label = label;
        translations.forEach(t => {
            const o = document.createElement('option');
            o.value = t.short_name;
            o.textContent = `${t.short_name} — ${t.full_name}`;
            og.appendChild(o);
            allMatchedCodes.push(t.short_name);
        });
        sel.appendChild(og);
    };
    matched.forEach(group => {
        const translations = group.translations || [];
        if (ppLangName === 'Chinese') {
            // bolls.life returns one mixed "Chinese" group — split by script so
            // Simplified and Traditional editions land under the right header.
            const simp = [], trad = [];
            translations.forEach(t => (_zhScriptOf(t) === 'simplified' ? simp : trad).push(t));
            const order = info.script === 'traditional'
                ? [['中文 — 繁體 (Traditional)', trad], ['中文 — 简体 (Simplified)', simp]]
                : [['中文 — 简体 (Simplified)', simp], ['中文 — 繁體 (Traditional)', trad]];
            order.forEach(([label, list]) => addOptgroup(label, list));
        } else {
            addOptgroup(group.language, translations);
        }
    });

    // If no match (language not in PrayerPulse), show English as fallback
    if (!matched.length) {
        const enGroup = langData.find(g => g.language === 'English');
        if (enGroup) {
            const og = document.createElement('optgroup');
            og.label = 'English (fallback)';
            (enGroup.translations || []).forEach(t => {
                const o = document.createElement('option');
                o.value = t.short_name;
                o.textContent = `${t.short_name} — ${t.full_name}`;
                og.appendChild(o);
                allMatchedCodes.push(t.short_name);
            });
            sel.appendChild(og);
        }
    }

    if (hint) hint.hidden = !ppLangName;

    // Restore saved preference if still valid for this language, else auto-match.
    // "Valid" has to mean the script too: bolls.life returns Simplified and
    // Traditional Chinese in one group, so a reader who switched from 粵語 to
    // 简体中文 kept CUV and got a Traditional Bible under a Simplified page —
    // both scripts on one screen, which is the thing this page must not do.
    const keeps = bibleTargetTrans && allMatchedCodes.includes(bibleTargetTrans)
        && (ppLangName !== 'Chinese' || !info.script
            || _zhScriptOfCode(langData, bibleTargetTrans) === info.script);
    if (keeps) {
        sel.value = bibleTargetTrans;
    } else {
        // Auto-match: use language default, or first in matched group
        const preferred = info.def;
        if (preferred && allMatchedCodes.includes(preferred)) {
            sel.value = preferred;
        } else if (allMatchedCodes.length) {
            sel.value = allMatchedCodes[0];
        } else {
            sel.value = '';
        }
        bibleTargetTrans = sel.value;
        try { localStorage.setItem('bibleTargetTrans', bibleTargetTrans); } catch (e) {}
    }

    // If the effective target translation changed, clear cache and reload visible panels
    if (bibleTargetTrans !== prevTgt) {
        _bibleLookupCache.clear();
        if (showBibleVerse) {
            translations.forEach(item => {
                if (item.bible_refs && item.bible_refs.length) {
                    const card = document.getElementById('translation-' + item.id);
                    if (card) loadBiblePanel(card, item.bible_refs);
                }
            });
        }
    }
}

// In-flight lookup promises: key = refs+translation fingerprint → Promise<enrichedRefs>
const _bibleLookupCache = new Map();

async function _fetchBibleVerses(refs, tgt) {
    // Source translation is admin-configured — not sent by client.
    const cacheKey = JSON.stringify({ refs: refs.map(r => r.display).sort(), tgt });
    if (_bibleLookupCache.has(cacheKey)) return _bibleLookupCache.get(cacheKey);

    const promise = fetch('/api/bible/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refs, target_translation: tgt }),
    })
    .then(r => r.ok ? r.json() : [])
    .catch(() => []);

    _bibleLookupCache.set(cacheKey, promise);
    setTimeout(() => _bibleLookupCache.delete(cacheKey), 120000);
    return promise;
}

/**
 * Fetch verse text for refs and attach to card.
 */
async function loadBiblePanel(card, refs) {
    if (!card || !refs || !refs.length) return;
    if (!bibleFeatureAvailable) return;
    // In transcription mode show source text only (no target translation).
    const tgt = displayMode === 'transcription' ? '' : bibleTargetTrans;
    const when = card.querySelector('.card-time');
    try {
        const enriched = await _fetchBibleVerses(refs, tgt);
        if (!enriched || !enriched.length) { speakDeferred(card); return; }
        // The lookup rebuilds each ref around the verse text and drops what it
        // did not ask about — including `match`, which is the whole of how the
        // page decides whether to show a verse at all. Put the detector's own
        // fields back.
        const merged = enriched.map((found, i) => {
            const original = refs.find(r => r.display === found.display) || refs[i] || {};
            return Object.assign({}, original, found, {
                // Refs stored before there was a `match` came from the
                // reference detector, and a reference is what they are.
                match: original.match || found.match || 'reference',
                verse_start: original.verse_start != null
                    ? original.verse_start : found.verse_start,
                verse_end: original.verse_end != null
                    ? original.verse_end : found.verse_end
            });
        });
        // The record of what this service read is kept whether or not the
        // verses are shown in the stream: switching them off is a reading
        // preference, not an instruction to forget the readings.
        merged.forEach(ref => addToScripture(ref, when ? when.textContent : ''));
        if (!showBibleVerse) { speakDeferred(card); return; }
        // The lookup takes a few hundred milliseconds, and a line that arrives
        // while the speaker is talking can be re-rendered inside that window —
        // the row this was called with is then detached, and the verse used to
        // be dropped on the floor. It only ever showed up after a reload,
        // which is the one moment nobody is watching. Find the row again.
        const live = card.isConnected
            ? card
            : (card.id ? document.getElementById(card.id) : null);
        // Whatever happens, a line held back for a verse gets read: nothing
        // may be worse than the wrong thing, but silence is worse than both.
        if (live) attachBiblePanel(live, merged);
        else speakDeferred(card);
    } catch (e) {
        console.warn('loadBiblePanel failed:', e);
        speakDeferred(card);
    }
}

function initBibleFeature() {
    // The server renders the Bible section only when bible_detection is enabled.
    bibleFeatureAvailable = !!document.getElementById('bibleVerseToggle');
    if (!bibleFeatureAvailable) return;

    // Prefer targetLang (translation output language) as the Bible language;
    // fall back to displayLanguage (UI language) for users who haven’t set a target.
    const currentLang = (typeof targetLang !== 'undefined' && targetLang && targetLang !== 'en'
            ? targetLang
            : null)
        || localStorage.getItem('targetLang')
        || (typeof displayLanguage !== 'undefined' ? displayLanguage : null)
        || localStorage.getItem('displayLanguage')
        || 'en';
    loadBibleTranslationOptions(currentLang);
    updateBibleToggleUI();
}

function onBibleTranslationChange() {
    const tgtSel = document.getElementById('bibleTargetTranslation');
    if (tgtSel) bibleTargetTrans = tgtSel.value;

    try { localStorage.setItem('bibleTargetTrans', bibleTargetTrans); } catch (e) {}
    _bibleLookupCache.clear();

    // Re-fetch for all visible cards
    if (showBibleVerse) {
        translations.forEach(item => {
            if (item.bible_refs && item.bible_refs.length) {
                const card = document.getElementById('translation-' + item.id);
                if (card) loadBiblePanel(card, item.bible_refs);
            }
        });
    }
}

function toggleBibleVerse() {
    showBibleVerse = !showBibleVerse;
    localStorage.setItem('showBibleVerse', showBibleVerse);
    updateBibleToggleUI();

    if (showBibleVerse) {
        // Load verse text for all cards that have refs
        translations.forEach(item => {
            if (item.bible_refs && item.bible_refs.length) {
                const card = document.getElementById('translation-' + item.id);
                if (card) loadBiblePanel(card, item.bible_refs);
            }
        });
    } else {
        // The verse stood in for the translation, so putting the verses away
        // has to put the translation back: rendering the list again is the one
        // path that rebuilds every row from what the item actually holds.
        renderTranslations();
    }
}

function updateBibleToggleUI() {
    const textSpan = document.getElementById('bibleVerseText');
    if (!textSpan) return;
    const onText = (i18n && i18n[displayLanguage] && i18n[displayLanguage].bibleVerseHide) || (i18n && i18n.en && i18n.en.bibleVerseHide) || 'Hide Bible Verses';
    const offText = (i18n && i18n[displayLanguage] && i18n[displayLanguage].bibleVerseShow) || (i18n && i18n.en && i18n.en.bibleVerseShow) || 'Show Bible Verses';
    textSpan.textContent = showBibleVerse ? onText : offText;
}

/**
 * Build the verse panel DOM for a list of enriched refs and append to `card`.
 * Idempotent — replaces any existing panel. Uses only textContent/createElement
 * to prevent any HTML injection from API responses.
 */
function attachBiblePanel(card, refs) {
    if (!card || !refs || !refs.length) return;

    const text = card.querySelector('.stream-text');
    if (!text) return;
    text.querySelectorAll('.sc-offer').forEach(el => el.remove());

    // A verse the speaker read goes where the machine translation would have
    // been: it IS the line, which is the whole point of looking it up in the
    // reader's own Bible rather than translating it.
    //
    // But only when the line is the verse. "John 3:16" is; "John 3:16, and
    // I've told you about this before" is a sentence that happens to name one,
    // and swallowing it loses everything the speaker actually said. Then the
    // verse sits under the translation instead of replacing it.
    const shown = refs.find(r => r.match === 'reference' || r.match === 'wording');
    if (shown) {
        if (shown.match === 'wording' || saidNothingElse(card, shown)) {
            substituteVerse(card, text, shown);
        } else {
            alongsideVerse(card, text, shown);
        }
    }

    // Anything doubtful is offered *instead* — which is what "instead" has to
    // mean. A row already showing Matthew 5:19 was still offering "This may be
    // Matthew 5:20" and "This may be Matthew 18:4" underneath it: three
    // answers to one question, two of them guesses, under a verse the page was
    // sure enough about to put in place of what the speaker said.
    if (!shown) {
        refs.filter(r => r.match === 'offer' || r.match === 'cited')
            .forEach(r => text.appendChild(buildOffer(r)));
    }

    // The row has settled: read it now if reading it was held back.
    speakDeferred(card);
}

/* Did the speaker say anything besides the reference?

   Take the words out that naming a passage needs — the book, the numbers, and
   the few words English uses to point at one — and see what is left. Nothing
   means they read it; a sentence means they were talking, and what they said
   has to be translated like any other line. */
function saidNothingElse(card, ref) {
    const item = translations.find(t => 'translation-' + t.id === card.id);
    const said = ((item && (item.corrected || item.original)) || '').toLowerCase();
    if (!said) return true;
    const rest = said
        .replace((ref.book || '').toLowerCase(), ' ')
        .replace(/\d+\s*[:\uff1a]\s*\d+(\s*[-\u2013\u2014]\s*\d+)?/g, ' ')
        .replace(/\b(chapter|chapters|verse|verses|ch|v|vv)\b/g, ' ')
        .replace(/[^a-z\u4e00-\u9fff]+/g, ' ')
        .trim();
    const words = rest.split(/\s+/).filter(Boolean);
    return words.length < 3;
}

/* What the play button on a row reads out. A row whose line was a reference
   has the verse put in place of it on screen, but the button kept the words
   that were transcribed — so pressing play on "For God so loved the world"
   said "john 3:16 to 18" instead, and with reading aloud on that reference
   was spoken before the next line's own words. The button says what the row
   says. */
function setRowSpeech(card, text) {
    const btn = card && card.querySelector('.tts-icon');
    if (btn && text) btn.setAttribute('data-text', text);
    // Once a row reads a verse, the background translation landing later must
    // not put the transcribed reference back on the button.
    if (card && text) card.setAttribute('data-speaks-verse', '1');
}

/* A line that carries a reference is not read aloud when it arrives: the
   lookup takes a second or two, and by the time it lands the row may be
   showing the verse instead of the words that were transcribed. Speaking
   immediately meant hearing "john 3:16 to 18" and then, on the next line, the
   sermon going on without the verse ever being read. The row is marked, and
   whatever it settles on is spoken once the lookup is done. */
function deferSpeech(card) {
    if (card) card.setAttribute('data-await-verse', '1');
}

function speakDeferred(card) {
    if (!card || card.getAttribute('data-await-verse') !== '1') return;
    card.removeAttribute('data-await-verse');
    if (!ttsEnabled || displayMode === 'transcription') return;
    const btn = card.querySelector('.tts-icon');
    const text = btn && btn.getAttribute('data-text');
    if (text) speakText(text, true);
}

/* Is this line nothing but a reference, so that the verse will take its
   place? The speak sites need to know before the lookup comes back. */
function willBecomeVerse(data) {
    return !!(showBibleVerse && bibleFeatureAvailable
              && data && data.bible_refs && data.bible_refs.length);
}

function verseSpeech(slot) {
    return slot.verses.map(function (v) { return tidyVerseText(v.text); })
        .join(' ').trim();
}

/* The verse under the translation rather than in place of it, for a line that
   named a passage while saying something of its own. */
function alongsideVerse(card, text, ref) {
    const both = pickVersions(ref);
    const slot = both.primary;
    if (!slot || !slot.verses || !slot.verses.length) return;

    text.querySelectorAll('.sc-verse, .sc-more').forEach(el => el.remove());
    const verse = document.createElement('div');
    verse.className = 'sc-verse';
    renderWindow(verse, slot.verses, ref, both.secondary);
    text.appendChild(verse);
    if (slot.verses.length > VERSE_WINDOW) {
        text.appendChild(buildShowAll(ref, slot.verses.length));
    }
    writeVerseTag(card, ref, both);
}

function substituteVerse(card, text, ref) {
    const both = pickVersions(ref);
    const slot = both.primary;
    if (!slot || !slot.verses || !slot.verses.length) return;

    const holder = text.querySelector('.sc-verse') || text.querySelector('.stream-zh');
    if (!holder) return;

    const verse = document.createElement('div');
    verse.className = 'sc-verse';
    renderWindow(verse, slot.verses, ref, both.secondary);
    holder.replaceWith(verse);

    text.querySelectorAll('.sc-more').forEach(el => el.remove());
    if (slot.verses.length > VERSE_WINDOW) {
        verse.insertAdjacentElement('afterend', buildShowAll(ref, slot.verses.length));
    }

    setRowSpeech(card, verseSpeech(slot));
    writeVerseTag(card, ref, both);
}

/* A passage named in the reader's Bible, and as the speaker said it: the
   lookup brings back each translation's own name for the book, so a reader of
   the CUNPS sees 马太福音 5:17 with Matthew 5:17 beside it, the way the verse
   itself is shown above its original. One name when the two are the same. */
function passageNames(ref) {
    const both = pickVersions(ref);
    const said = ref.display || '';
    const own = (both.primary && both.primary.display) || said;
    return { main: own, original: own !== said ? said : '' };
}

function writePassageHeading(el, ref) {
    const names = passageNames(ref);
    el.textContent = names.main;
    if (names.original) {
        const original = document.createElement('span');
        original.className = 'sc-original';
        original.lang = 'en';
        original.textContent = names.original;
        el.appendChild(original);
    }
}

/* The reference and how it was found belong against the timestamp, not in a
   header of their own: the row already has a place for saying what a line is. */
function writeVerseTag(card, ref, both) {
    const term = card.querySelector('.pf-v6-c-description-list__text');
    if (!term) return;
    term.querySelectorAll('.stream-tag').forEach(el => el.remove());
    const tag = document.createElement('span');
    tag.className = 'stream-tag';
    const heading = passageNames(ref);
    const bits = [heading.original ? heading.main + ' (' + heading.original + ')' : heading.main];
    const names = [both.primary && both.primary.translation,
                   both.secondary && both.secondary.translation]
        .filter(Boolean).map(n => n.toUpperCase());
    if (names.length) bits.push(names.join(' / '));
    bits.push(ref.match === 'wording'
        ? t('sc_byWording', 'matched by wording')
        : t('sc_fromBible', 'from the Bible, not translated'));
    tag.textContent = bits.join(' · ');
    term.appendChild(tag);
}

/* The two Bibles this verse is read in, in the order the page reads: the
   reader's own first, the English under it — the same shape as every other row,
   where the translation leads and the English sits quietly beneath. */
function pickVersions(ref) {
    const has = slot => slot && slot.verses && slot.verses.length;
    const target = has(ref.target) ? ref.target : null;
    const source = has(ref.source) ? ref.source : null;
    const legacy = (!target && !source && ref.verses && ref.verses.length)
        ? { translation: ref.translation, verses: ref.verses } : null;

    const primary = target || source || legacy;
    let secondary = null;
    if (target && source && target.translation !== source.translation) {
        secondary = source;
    }
    return { primary: primary, secondary: secondary };
}

function buildShowAll(ref, total) {
    const more = document.createElement('p');
    more.className = 'sc-more';
    const btn = document.createElement('button');
    btn.className = 'pf-v6-c-button pf-m-inline pf-m-link';
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.onclick = () => showPassage(ref);
    const label = document.createElement('span');
    label.className = 'pf-v6-c-button__text';
    label.textContent = t('sc_showAll', 'Show all %n verses').replace('%n', String(total))
        + ' — ' + (ref.display || '');
    btn.appendChild(label);
    more.appendChild(btn);
    return more;
}

/* One quiet line: the reference, and a way to read it. */
function buildOffer(ref) {
    const line = document.createElement('p');
    line.className = 'sc-offer';
    const label = document.createElement('span');
    label.textContent = (ref.match === 'cited'
        ? t('sc_cited', 'Mentioned')
        : t('sc_maybe', 'This may be')) + ' — ';
    line.appendChild(label);
    const open = document.createElement('button');
    open.className = 'pf-v6-c-button pf-m-inline pf-m-link';
    open.type = 'button';
    open.setAttribute('aria-haspopup', 'dialog');
    open.onclick = () => showPassage(ref);
    const openText = document.createElement('span');
    openText.className = 'pf-v6-c-button__text';
    openText.textContent = ref.display || '';
    open.appendChild(openText);
    line.appendChild(open);
    return line;
}

/* ── the Scripture section ────────────────────────────────────────────────
   Every passage this service has been through, gathered in one place, so
   somebody who looked away can find the reading without scrolling the stream.
   Offers and citations are listed too: what was mentioned is part of the
   record even when it was not read out. */
/* One entry per passage. It was one per label and way of finding it, so a
   verse that was cited and later recognised from its wording was listed
   twice; a passage that comes up again now adds its time to the entry it
   already has, and takes the surer way of finding it if this one is surer. */
const scriptureSeen = new Map();     // passage -> {group, strength, times, hasText}
const MATCH_STRENGTH = { reference: 4, wording: 3, cited: 2, offer: 1 };

function passageKey(ref) {
    if (ref.book) {
        return [ref.book, ref.chapter, ref.verse_start, ref.verse_end]
            .map(v => (v == null ? '' : String(v))).join('|');
    }
    return String(ref.display || '');
}

function addToScripture(ref, timestamps) {
    const list = document.getElementById('scriptureList');
    if (!list || !ref || !ref.display) return;
    // Verses looked up in a Bible other than the one now chosen (a lookup
    // made just before the reading language changed) are not this list's:
    // the passage is kept, its translated text is not.
    if (ref.target && ref.target.translation && bibleTargetTrans
            && ref.target.translation !== bibleTargetTrans) {
        ref = Object.assign({}, ref, { target: undefined });
    }
    const key = passageKey(ref);
    const times = [].concat(timestamps || []).filter(Boolean);
    const strength = MATCH_STRENGTH[ref.match] || 0;
    const hasText = !!(ref.source && ref.source.verses && ref.source.verses.length)
        || !!(ref.target && ref.target.verses && ref.target.verses.length);
    const version = (ref.target && ref.target.translation) || '';
    const known = scriptureSeen.get(key);
    if (known) {
        times.forEach(t => { if (known.times.indexOf(t) === -1) known.times.push(t); });
        known.times.sort();
        // Rebuilt when found more surely, when its verses have arrived, or
        // when they have arrived in the Bible now chosen; a rebuild keeps the
        // surest way it was found.
        const newVersion = hasText && version && version !== known.version;
        if (strength > known.strength || (hasText && !known.hasText && strength >= known.strength)
                || newVersion) {
            const surer = strength >= known.strength ? ref : Object.assign({}, ref, { match: known.match });
            const fresh = buildScriptureEntry(surer, known.times);
            known.group.replaceWith(fresh);
            known.group = fresh;
            known.strength = Math.max(strength, known.strength);
            known.match = surer.match;
            known.hasText = known.hasText || hasText;
            if (version) known.version = version;
        } else {
            const when = known.group.querySelector('.sc-time');
            if (when) when.textContent = known.times.join(' · ');
        }
        return;
    }

    const empty = list.querySelector('.scripture-empty');
    if (empty) empty.remove();

    times.sort();
    const group = buildScriptureEntry(ref, times);
    scriptureSeen.set(key, { group, strength, times, hasText, version, match: ref.match });
    list.insertBefore(group, list.firstChild);
}
window.addToScripture = addToScripture;

function buildScriptureEntry(ref, times) {
    const group = document.createElement('div');
    group.className = 'pf-v6-c-description-list__group';

    // The reference is the term here, with the time under it — this page is
    // read by passage, not by clock.
    const dt = document.createElement('dt');
    dt.className = 'pf-v6-c-description-list__term';
    const dtText = document.createElement('span');
    dtText.className = 'pf-v6-c-description-list__text';
    writePassageHeading(dtText, ref);
    const when = document.createElement('span');
    when.className = 'sc-time';
    when.textContent = times.join(' · ');
    dtText.appendChild(when);
    dt.appendChild(dtText);
    group.appendChild(dt);

    const dd = document.createElement('dd');
    dd.className = 'pf-v6-c-description-list__description';
    const ddText = document.createElement('div');
    ddText.className = 'pf-v6-c-description-list__text';

    const both = pickVersions(ref);
    const slot = both.primary;
    if (slot && slot.verses && slot.verses.length) {
        const verse = document.createElement('div');
        verse.className = 'sc-verse';
        renderWindow(verse, slot.verses, ref, both.secondary);
        ddText.appendChild(verse);
        if (slot.verses.length > VERSE_WINDOW) {
            ddText.appendChild(buildShowAll(ref, slot.verses.length));
        }
    } else {
        ddText.appendChild(buildOffer(ref));
    }

    // How it was found, and which verse the speaker actually read — said in
    // words, because this page is the record and a record has to explain
    // itself later.
    const how = document.createElement('span');
    how.className = 'meta';
    const parts = [{
        reference: t('sc_wasSpoken', 'The reference was spoken'),
        wording: t('sc_byWording', 'matched by wording'),
        offer: t('sc_maybe', 'This may be'),
        cited: t('sc_cited', 'Mentioned')
    }[ref.match] || ''];
    const names = [slot && slot.translation, both.secondary && both.secondary.translation]
        .filter(Boolean).map(n => n.toUpperCase());
    if (names.length) parts.push(names.join(' / '));
    if (ref.verse_start && ref.verse_end === ref.verse_start
            && slot && slot.verses && slot.verses.length > 1) {
        parts.push(t('sc_verseRead', 'verse %n was the one read aloud')
            .replace('%n', String(ref.verse_start)));
    }
    how.textContent = parts.filter(Boolean).join(' · ');
    ddText.appendChild(how);

    dd.appendChild(ddText);
    group.appendChild(dd);
    return group;
}

/* The whole service's passages, not only those of the lines loaded. A
   listener sees the newest thirty lines; a passage read before them never
   reached this section, which is the one place meant to hold them all. */
function clearScripture() {
    const list = document.getElementById('scriptureList');
    if (!list) return;
    scriptureSeen.clear();
    list.querySelectorAll('.pf-v6-c-description-list__group:not(.scripture-empty)')
        .forEach(g => g.remove());
    if (!list.querySelector('.scripture-empty')) {
        const empty = document.createElement('div');
        empty.className = 'pf-v6-c-description-list__group scripture-empty';
        const dd = document.createElement('dd');
        dd.className = 'pf-v6-c-description-list__description';
        const text = document.createElement('div');
        text.className = 'pf-v6-c-description-list__text meta';
        text.setAttribute('data-i18n', 'sc_none');
        text.textContent = t('sc_none', 'Passages read in this service will appear here.');
        dd.appendChild(text);
        empty.appendChild(dd);
        list.appendChild(empty);
    }
}

async function loadScriptureRecord() {
    if (!bibleFeatureAvailable || !apiSessionToken) return;
    try {
        const res = await fetch('/api/scripture?api_token=' + encodeURIComponent(apiSessionToken)
            + '&room=' + encodeURIComponent(window.CURRENT_ROOM_ID || 'main'));
        if (!res.ok) return;
        const passages = ((await res.json()) || {}).passages || [];
        // Listed at once, each with a link to open it; the verses fill in as
        // they arrive. Waiting for all of them held the section empty for ten
        // seconds on a service with sixteen passages.
        passages.forEach(function (p) {
            addToScripture(Object.assign({}, p, { match: p.match || 'reference' }), p.times);
        });
        const tgt = displayMode === 'transcription' ? '' : bibleTargetTrans;
        for (let i = 0; i < passages.length; i += 20) {
            const batch = passages.slice(i, i + 20);
            const enriched = await _fetchBibleVerses(batch, tgt) || [];
            batch.forEach(function (original, j) {
                const found = enriched.find(f => f.display === original.display) || enriched[j] || {};
                addToScripture(Object.assign({}, original, found, {
                    match: original.match || 'reference',
                    verse_start: original.verse_start,
                    verse_end: original.verse_end,
                }), original.times);
            });
        }
    } catch (e) {
        console.warn('Scripture record could not be loaded:', e);
    }
}

/* ── the window over a long passage ───────────────────────────────────────
   Up to three verses are shown whole. Beyond that the window has to contain
   the verse that was actually read — not simply the first three — or the
   reader is shown the run-up to the point and never the point. */
const VERSE_WINDOW = 3;

function verseWindow(verses, ref) {
    if (verses.length <= VERSE_WINDOW) return { start: 0, verses: verses };
    // When the whole passage was read, nothing is singled out and the window
    // starts at the top.
    const read = (ref.verse_start && ref.verse_end && ref.verse_end > ref.verse_start
                  && (ref.verse_end - ref.verse_start + 1) >= verses.length)
        ? null : ref.verse_start;
    let start = 0;
    if (read != null) {
        const at = verses.findIndex(v => Number(v.n) === Number(read));
        if (at > 0) start = Math.min(Math.max(0, at - 1), verses.length - VERSE_WINDOW);
    }
    return { start: start, verses: verses.slice(start, start + VERSE_WINDOW) };
}

function renderWindow(host, verses, ref, secondary) {
    const win = verseWindow(verses, ref);
    const above = win.start;
    const below = verses.length - win.start - win.verses.length;

    // The other version, indexed by verse number: the two Bibles do not always
    // return the same run, and a line pairs with its own number or with
    // nothing at all.
    const other = new Map();
    (secondary && secondary.verses || []).forEach(v => other.set(String(v.n), v));

    if (above > 0) host.appendChild(elide(above));
    win.verses.forEach(v => {
        host.appendChild(verseLine(v, ref));
        const pair = other.get(String(v.n));
        if (pair) host.appendChild(verseLine(pair, ref, true));
    });
    if (below > 0) host.appendChild(elide(below));
}

function elide(count) {
    const line = document.createElement('p');
    line.className = 'sc-elide';
    line.textContent = '⋯ ';
    const label = document.createElement('span');
    label.textContent = t('sc_moreVerses', '%n more verses').replace('%n', String(count));
    line.appendChild(label);
    return line;
}

/* Some Chinese Bibles are stored with a space between every character —
   "我 雖 然 行 過 死 蔭 的 幽 谷" — which is how the text was typeset, not how it
   is read. A space between two Han characters carries no meaning and pulls a
   verse to twice its width, so it goes; a space beside anything else stays,
   because there it is doing a job. */
function tidyVerseText(text) {
    return String(text || '')
        .replace(/([\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef])[ \t]+(?=[\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef])/g, '$1')
        .trim();
}

function verseLine(v, ref, paired) {
    const line = document.createElement('p');
    line.className = paired ? 'sc-line sc-pair' : 'sc-line';
    // Context around the verse that was read is dimmed, so the eye lands on
    // the one the speaker actually said.
    if (ref && ref.verse_start && ref.verse_end === ref.verse_start
            && Number(v.n) !== Number(ref.verse_start)) {
        line.classList.add('sc-dim');
    }
    if (paired) {
        // The number is already on the line above; repeating it would make a
        // pair look like two verses.
        const spacer = document.createElement('sup');
        spacer.className = 'sc-n';
        spacer.setAttribute('aria-hidden', 'true');
        line.appendChild(spacer);
    } else {
        const num = document.createElement('sup');
        num.className = 'sc-n';
        num.textContent = String(v.n);
        line.appendChild(num);
    }
    line.appendChild(document.createTextNode(' ' + tidyVerseText(v.text)));
    return line;
}

/* ── the passage dialog ───────────────────────────────────────────────────
   The whole passage at a reading measure. Its footer reads it aloud; the
   stream never starts a passage on its own. */
async function showPassage(ref) {
    const modal = document.getElementById('passageModal');
    if (!modal) return;
    writePassageHeading(document.getElementById('passageTitle'), ref);
    const sub = document.querySelector('#passageModal .modal-sub');
    if (sub) {
        const names = [ref.target && ref.target.translation, ref.source && ref.source.translation]
            .filter(Boolean).map(n => n.toUpperCase());
        sub.textContent = names.length
            ? names.join(' / ') + ' · ' + t('sc_fromBible', 'from the Bible, not translated')
            : t('sc_fromBible', 'from the Bible, not translated');
    }
    const body = document.getElementById('passageBody');
    body.replaceChildren();
    const loading = document.createElement('p');
    loading.className = 'sc-elide';
    loading.textContent = t('bibleLoading', '— Loading... —');
    body.appendChild(loading);
    modal.classList.add('active');

    let full = ref;
    if (!ref.source && !ref.target) {
        try {
            const got = await _fetchBibleVerses([ref], displayMode === 'transcription'
                ? '' : bibleTargetTrans);
            if (got && got.length) full = got[0];
        } catch (e) {
            console.warn('passage lookup failed', e);
        }
    }

    body.replaceChildren();
    const both = pickVersions(full);
    if (both.primary) {
        const other = new Map();
        (both.secondary && both.secondary.verses || []).forEach(v => other.set(String(v.n), v));
        const wrap = document.createElement('div');
        wrap.className = 'modal-verses';
        both.primary.verses.forEach(v => {
            wrap.appendChild(verseLine(v, null));
            const pair = other.get(String(v.n));
            if (pair) wrap.appendChild(verseLine(pair, null, true));
        });
        body.appendChild(wrap);
    }
    if (!body.childNodes.length) {
        const empty = document.createElement('p');
        empty.className = 'bible-verse-missing';
        empty.textContent = t('sc_unavailable', 'Verse text unavailable');
        body.appendChild(empty);
    }
    modal._passage = full;
}
window.showPassage = showPassage;

function hidePassage() {
    const modal = document.getElementById('passageModal');
    if (modal) modal.classList.remove('active');
}
window.hidePassage = hidePassage;

/* The one place a whole passage is ever spoken. */
function readPassageAloud() {
    const modal = document.getElementById('passageModal');
    const full = modal && modal._passage;
    if (!full) return;
    const slot = (full.target && full.target.verses && full.target.verses.length)
        ? full.target : full.source;
    if (!slot || !slot.verses) return;
    speakText(slot.verses.map(v => tidyVerseText(v.text)).join(' '));
}
window.readPassageAloud = readPassageAloud;

/* =========================
   Translation (uses Google translate endpoints like before)
   ========================= */
/* Two language codes name the same language when their base subtag matches —
   en-US and en, cmn-Hans-CN and zh — except that Chinese splits by script, so
   simplified and traditional stay apart. */
function sameLanguage(a, b) {
    if (!a || !b) return false;
    const base = code => {
        const s = String(code).toLowerCase();
        // Cantonese is written in traditional script but is its own language,
        // so it has to be recognised before the script test.
        if (s.startsWith('yue')) return 'yue';
        if (s.startsWith('zh-tw') || s.includes('-hant')) return 'zh-tw';
        if (s.startsWith('zh')) return 'zh';
        return s.split('-')[0];
    };
    return base(a) === base(b);
}
window.sameLanguage = sameLanguage;

/* There were two functions called translateText here. JavaScript keeps the
   last one, so this one — which asked the endpoint directly and would have
   worked — was dead the moment it was written. It is gone; the live one is
   below, and its fallback now does what this did.
*/

/* =========================
   Rendering (minimal)
   ========================= */
