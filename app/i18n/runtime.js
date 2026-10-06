/* The language runtime: which languages exist, loading the ones a page needs,
 * and applying them to everything marked data-i18n.
 *
 * Source for app/static/js/i18n/core.js, which tools/i18n/build.mjs writes by
 * putting the list of language files in front of this. The strings are in
 * app/i18n/strings.js.
 *
 * Every language used to arrive with every page: 316KB, a twenty-second of it
 * read. Now a page loads English, which every missing string falls back to,
 * and the languages it may be shown in: the one chosen before, the one in the
 * address, the browser's. They are written into the document while it is
 * still being parsed, so they run before the page's own scripts exactly as the
 * single file did, and nothing has to wait for them. Switching to another
 * language fetches it first.
 */
(function () {
    const EZY = window.EZY_I18N || { languages: ['en'], files: {} };
    window.sharedI18n = window.sharedI18n || {};
    window.sharedAiStatusLibrary = window.sharedAiStatusLibrary || {};
    const i18n = window.sharedI18n;

    // Whether a language exists, which is not the same as whether it has
    // arrived: the four helpers below used to decide by the second.
    function has(lang) { return EZY.languages.indexOf(lang) !== -1; }
    window.isDisplayLanguage = has;

    const here = (document.currentScript && document.currentScript.src) || '';
    const base = here.slice(0, here.lastIndexOf('/') + 1);
    const pending = {};

    function src(lang) { return base + EZY.files[lang]; }

    window.ensureDisplayLanguage = function (lang) {
        if (!has(lang) || i18n[lang]) return Promise.resolve();
        if (!pending[lang]) {
            pending[lang] = new Promise(function (done) {
                const s = document.createElement('script');
                s.src = src(lang);
                s.onload = s.onerror = function () { done(); };
                document.head.appendChild(s);
            });
        }
        return pending[lang];
    };

    window.detectDisplayLanguage = function () {
        const browserLang = (navigator.language || navigator.userLanguage || 'en').toLowerCase();
            // Exact match
        if (has(browserLang)) return browserLang;
        // Base match (e.g., 'en' from 'en-US')
        const base = browserLang.split('-')[0];
        if (has(base)) return base;
        // Chinese variants — prefer available keys
        if (browserLang.startsWith('zh')) {
            if ((browserLang.includes('tw') || browserLang.includes('hant') || browserLang.includes('hk')) && has('zh-tw')) return 'zh-tw';
            if ((browserLang.includes('yue') || browserLang.includes('cantonese')) && has('yue')) return 'yue';
            if (has('zh')) return 'zh';
        }
        return 'en';
    };

    // Resolve a possibly-variant language code to a language that exists
    window.resolveDisplayLang = function (lang) {
        if (!lang) return window.detectDisplayLanguage();
        const lower = String(lang).toLowerCase();
        // Exact key
        if (has(lang)) return lang;
        if (has(lower)) return lower;
        // Base (en-US -> en)
        const base = lower.split('-')[0];
        if (has(base)) return base;
        // Common aliases
        if (lower.startsWith('yue') || lower.includes('cantonese') || lower.includes('hk')) {
            if (has('yue')) return 'yue';
        }
        if (lower.startsWith('zh')) {
            if (lower.includes('tw') || lower.includes('hant')) {
                if (has('zh-tw')) return 'zh-tw';
            }
            if (has('zh')) return 'zh';
        }
        return 'en';
    };

    window.applyDisplayLanguage = function (lang) {
        const raw = lang || localStorage.getItem('displayLanguage') || window.detectDisplayLanguage();
        const i18n = window.sharedI18n || {};
        const resolved = window.resolveDisplayLang(raw);
        // Not here yet: show what there is (English stands in for any missing
        // string), fetch it, and apply again when it lands.
        if (!i18n[resolved]) {
            window.ensureDisplayLanguage(resolved).then(function () {
                if (i18n[resolved]) window.applyDisplayLanguage(resolved);
            });
        }
        // Guard to prevent re-entrancy when programmatically updating selects
        if (window._applyingDisplayLanguage) return resolved;
        window._applyingDisplayLanguage = true;
        try {
            window._displayLanguage = resolved;

            // Text content. {version} is the running version, which the server
            // writes on the root element: the strings no longer hold a number
            // of their own to fall out of date.
            const version = document.documentElement.getAttribute('data-version') || '';
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                const text = (i18n[resolved] && i18n[resolved][key]) || (i18n['en'] && i18n['en'][key]);
                if (text) el.textContent = text.replace('{version}', version);
            });

            // Placeholders
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                if (i18n[resolved] && i18n[resolved][key]) el.placeholder = i18n[resolved][key];
                else if (i18n['en'] && i18n['en'][key]) el.placeholder = i18n['en'][key];
            });

            // Titles
            document.querySelectorAll('[data-i18n-title]').forEach(el => {
                const key = el.getAttribute('data-i18n-title');
                if (i18n[resolved] && i18n[resolved][key]) el.title = i18n[resolved][key];
                else if (i18n['en'] && i18n['en'][key]) el.title = i18n['en'][key];
            });

            // Document title and meta description via data attributes
            try {
                let titleKey = 'metaTitle';
                // If this page includes the admin brand label, or is the login/admin path,
                // prefer the admin meta title. This is a fallback for templates where
                // the brand marker may not be detected early enough.
                if (document.querySelector('[data-i18n="brand_admin"]') ||
                    (window.location && window.location.pathname && (window.location.pathname.includes('/admin') || window.location.pathname.includes('/login')))
                ) titleKey = 'metaTitle_admin';
                const titleText = (i18n[resolved] && (i18n[resolved][titleKey] || i18n[resolved]['metaTitle'])) || (i18n['en'] && (i18n['en'][titleKey] || i18n['en']['metaTitle']));
                if (titleText) document.title = titleText;
            } catch (e) {
            }

            document.querySelectorAll('meta[data-i18n-meta]').forEach(el => {
                const key = el.getAttribute('data-i18n-meta');
                if (i18n[resolved] && i18n[resolved][key]) el.setAttribute('content', i18n[resolved][key]);
                else if (i18n['en'] && i18n['en'][key]) el.setAttribute('content', i18n['en'][key]);
            });

            // Update any inputs/selects that reflect chosen display language (set value only)
            const selects = document.querySelectorAll('select[id=displayLanguage]');
            selects.forEach(s => {
                if (s.value !== resolved) s.value = resolved;
            });

            // Update status badges if present
            const badge = document.getElementById('statusBadge');
            if (badge) {
                // The badge is a PatternFly label: its text node is a class down,
                // and `span:last-child` matches the content wrapper instead, so
                // writing to that would flatten the label's structure.
                const span = badge.querySelector('.pf-v6-c-label__text')
                    || badge.querySelector('span:last-child');
                if (span) {
                    if (badge.classList.contains('online')) span.textContent = (i18n[resolved] && i18n[resolved]['online']) || span.textContent;
                    else if (badge.classList.contains('offline')) span.textContent = (i18n[resolved] && i18n[resolved]['offline']) || span.textContent;
                    else span.textContent = (i18n[resolved] && i18n[resolved]['waiting']) || span.textContent;
                }
            }
        } finally {
            window._applyingDisplayLanguage = false;
        }
    };

    window.changeDisplayLanguage = function (lang) {
        if (!lang) return;
        if (window._applyingDisplayLanguage) return;
        const resolved = window.resolveDisplayLang(lang);
        try {
            localStorage.setItem('displayLanguage', resolved);
        } catch (e) {
        }
        window.applyDisplayLanguage(resolved);
    };

    // Auto-apply on load
    document.addEventListener('DOMContentLoaded', () => {
        try {
            window.applyDisplayLanguage();
        } catch (e) {
            console.warn('i18n apply failed:', e);
        }
    });

    // What this page is likely to be shown in, loaded now, in order, while
    // the document is still being parsed.
    const wanted = ['en'];
    function want(lang) {
        if (!lang) return;
        const resolved = window.resolveDisplayLang(lang);
        if (has(resolved) && wanted.indexOf(resolved) === -1) wanted.push(resolved);
    }
    try { want(localStorage.getItem('displayLanguage')); } catch (e) { /* storage blocked */ }
    try { want(new URLSearchParams(window.location.search).get('lang')); } catch (e) { /* no URL API */ }
    want(window.detectDisplayLanguage());
    // The listener reads Hong Kong and Macau as Cantonese where this file
    // reads them as traditional Chinese; fetch both rather than flash English.
    if (/-(hk|mo)\b/i.test(navigator.language || '')) want('yue');
    if (document.readyState === 'loading') {
        wanted.forEach(function (lang) {
            if (!i18n[lang]) document.write('<script src="' + src(lang) + '"><\/script>');
        });
    } else {
        wanted.forEach(window.ensureDisplayLanguage);
    }
})();
