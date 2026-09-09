/* One place that paints a theme.
 *
 * Four pages each carried the same two lines — set data-theme, toggle
 * PatternFly's dark class — so a change to how a theme is applied had to be
 * made four times and was made three. It is applied here, and the pages ask
 * for a theme rather than describing one.
 *
 * The switch is a crossfade rather than a jump. A page in the middle of a
 * service is mostly text on a large surface, and inverting it in a single
 * frame is a flash in a dark room. The browser's own view transition does the
 * work: one composited fade of the whole page, no per-element transitions to
 * run down a stream that may be hundreds of rows long. Where the API is
 * missing the paint simply happens, which is what happened before.
 */
(function () {
    function paint(theme) {
        const root = document.documentElement;
        root.setAttribute('data-theme', theme);
        // PatternFly switches its own tokens on this class; data-theme stays
        // because the app's own CSS still reads it.
        root.classList.toggle('pf-v6-theme-dark', theme === 'dark');
    }

    function motionIsUnwelcome() {
        try {
            return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        } catch (e) {
            return false;
        }
    }

    /* Straight to it, no fade: what a page does on load, where there is no
       previous state to cross from and a fade would only be a flash. */
    window.paintTheme = paint;

    /* theme: 'light' or 'dark'. `after` runs with the new theme painted, so
       whatever a page has to relabel changes inside the same fade. */
    window.applyTheme = function (theme, after) {
        const done = function () {
            paint(theme);
            if (typeof after === 'function') after(theme);
        };
        if (typeof document.startViewTransition !== 'function' || motionIsUnwelcome()) {
            done();
            return;
        }
        document.startViewTransition(done);
    };

    /* The other half: flip to whichever theme is not on now, remember it, and
       hand back the one chosen. */
    window.toggleThemeTo = function (after) {
        const now = document.documentElement.getAttribute('data-theme');
        const next = now === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem('theme', next); } catch (e) {}
        window.applyTheme(next, after);
        return next;
    };
})();
