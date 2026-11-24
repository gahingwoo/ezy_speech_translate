/* A service's transcript: its language, what was said beside it, the theme.
   The server writes the text; this only moves between languages and shows
   or hides the original. */

(function () {
    const root = document.documentElement;
    const lang = root.getAttribute('lang') || 'en';

    // The page's own words in the transcript's language, where the app has
    // them. Not saved: the reader's listener page keeps its own choice.
    document.addEventListener('DOMContentLoaded', function () {
        try { window.applyDisplayLanguage(lang); } catch (e) { /* English stays */ }

        // The date, written out as the reader's language writes it.
        const when = document.getElementById('transcriptDate');
        if (when) {
            try {
                const d = new Date(when.getAttribute('datetime') + 'T12:00:00');
                when.textContent = d.toLocaleDateString(lang, {
                    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
                });
            } catch (e) { /* the ISO date stays */ }
        }

        try {
            if (localStorage.getItem('transcriptShowSaid') === '1') {
                const box = document.getElementById('transcriptSaid');
                if (box) { box.checked = true; window.transcriptShowSaid(true); }
            }
        } catch (e) { /* storage blocked */ }

        updateThemeLabel(root.classList.contains('pf-v6-theme-dark') ? 'dark' : 'light');
    });

    window.transcriptLanguage = function (next) {
        const url = new URL(window.location.href);
        url.searchParams.set('lang', next);
        window.location.assign(url.toString());
    };

    window.transcriptShowSaid = function (on) {
        document.querySelectorAll('.transcript-said').forEach(function (el) { el.hidden = !on; });
        try { localStorage.setItem('transcriptShowSaid', on ? '1' : '0'); } catch (e) { /* fine */ }
    };

    function t(key, fallback) {
        const lib = window.sharedI18n || {};
        const resolved = window._displayLanguage || 'en';
        return (lib[resolved] && lib[resolved][key]) || (lib.en && lib.en[key]) || fallback;
    }

    function updateThemeLabel(theme) {
        const button = document.getElementById('themeToggle');
        if (!button) return;
        const label = theme === 'dark' ? t('lightMode', 'Light Mode') : t('darkMode', 'Dark Mode');
        button.setAttribute('title', label);
        button.setAttribute('aria-label', label);
    }

    document.addEventListener('displaylanguagechange', function () {
        updateThemeLabel(root.classList.contains('pf-v6-theme-dark') ? 'dark' : 'light');
    });

    /* WeChat's own browser, where a shared transcript link most often opens:
       it neither prints nor saves files, and says nothing when asked to. */
    const IN_WECHAT = /MicroMessenger/i.test(navigator.userAgent || '');

    function copyText(text) {
        const byHand = () => {
            const area = document.createElement('textarea');
            area.value = text;
            area.setAttribute('readonly', '');
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            let ok = false;
            try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
            area.remove();
            return ok;
        };
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text).then(() => true, () => byHand());
        }
        return Promise.resolve(byHand());
    }

    window.transcriptPrint = function () {
        if (IN_WECHAT) {
            alert(t('wx_noPrint', 'WeChat cannot print or save a PDF. Tap ··· at the top right and choose Open in Browser.'));
            return;
        }
        window.print();
    };

    // The link downloads the text everywhere else; in WeChat it is copied.
    window.transcriptDownload = function (link) {
        if (!IN_WECHAT) return true;
        if (confirm(t('wx_noDownload', 'WeChat cannot save files. Copy the text instead?\n\nFor the file, tap ··· at the top right and choose Open in Browser.'))) {
            fetch(link.href).then(r => r.text()).then(copyText).then(ok => {
                alert(ok ? t('toast_copied', 'Copied to clipboard') : t('toast_copyFailed', 'Failed to copy to clipboard'));
            });
        }
        return false;
    };

    window.toggleTheme = function () {
        window.toggleThemeTo(updateThemeLabel);
    };
})();
