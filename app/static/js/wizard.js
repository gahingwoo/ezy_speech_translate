/* The step machinery behind a PatternFly wizard.
 *
 * Two pages ask a few questions once and then get out of the way: the listener
 * before its first service, and the screen at the front of the room before it
 * is pointed at anything. The questions differ; moving between them does not,
 * and neither does keeping the sidebar, the phone toggle and the two footer
 * buttons in step with each other.
 *
 * Everything is found from one prefix, so a page only has to name its parts
 * the way PatternFly's wizard markup does:
 *
 *   <prefix>-<step>        the body of a step
 *   <prefix>-nav-<step>    the link to it in the sidebar
 *   <prefix>Nav            the sidebar
 *   <prefix>Toggle         the phone toggle, with Num and Title inside it
 *   <prefix>Back           the two footer buttons
 *   <prefix>Next
 */
function Wizard(prefix, steps, onFinish) {
    const el = id => document.getElementById(id);
    let at = 0;

    function show(key) {
        at = Math.max(0, steps.indexOf(key));
        steps.forEach(function (k, i) {
            const link = el(prefix + '-nav-' + k);
            if (link) {
                link.classList.toggle('pf-m-current', i === at);
                if (i === at) link.setAttribute('aria-current', 'step');
                else link.removeAttribute('aria-current');
            }
            const body = el(prefix + '-' + k);
            if (body) body.hidden = i !== at;
        });

        // The toggle is what a phone sees instead of the step list, so it has
        // to say which step this is; choosing one from it also puts it away.
        const link = el(prefix + '-nav-' + steps[at]);
        const num = el(prefix + 'ToggleNum');
        const title = el(prefix + 'ToggleTitle');
        if (num) num.textContent = String(at + 1);
        if (title && link) {
            // The key may be on the link or on the text span inside it,
            // depending on how much of PatternFly's nav markup a page uses.
            const keyed = link.hasAttribute('data-i18n')
                ? link
                : link.querySelector('[data-i18n]');
            if (keyed) title.setAttribute('data-i18n', keyed.getAttribute('data-i18n'));
            title.textContent = link.textContent.trim();
        }
        const toggle = el(prefix + 'Toggle');
        const nav = el(prefix + 'Nav');
        if (toggle && toggle.classList.contains('pf-m-expanded')) {
            toggle.classList.remove('pf-m-expanded');
            if (nav) nav.classList.remove('pf-m-expanded');
            toggle.setAttribute('aria-expanded', 'false');
        }

        const back = el(prefix + 'Back');
        const next = el(prefix + 'Next');
        if (back) back.disabled = at === 0;
        if (next) {
            // The last step finishes rather than advances. The label is
            // swapped by key, not by text: reading it out of the English table
            // left the one button on the page in English whatever language was
            // chosen.
            const last = at === steps.length - 1;
            const label = next.querySelector('.pf-v6-c-button__text') || next;
            label.setAttribute('data-i18n', last ? 'tour_done' : 'tour_next');
            label.textContent = last ? 'Done' : 'Next';
        }
        // Re-translate what was just relabelled, in the language already
        // resolved for this page. Calling with no argument would send it back
        // to whatever is in storage, which on the projection screen is the
        // listener's reading language, not the one being projected.
        if (window.applyDisplayLanguage) {
            window.applyDisplayLanguage(window._displayLanguage || undefined);
        }
    }

    function next() {
        if (at >= steps.length - 1) {
            if (typeof onFinish === 'function') onFinish();
            return;
        }
        show(steps[at + 1]);
    }

    function back() {
        if (at > 0) show(steps[at - 1]);
    }

    function toggleNav() {
        const toggle = el(prefix + 'Toggle');
        const nav = el(prefix + 'Nav');
        if (!toggle || !nav) return;
        const open = !toggle.classList.contains('pf-m-expanded');
        toggle.classList.toggle('pf-m-expanded', open);
        nav.classList.toggle('pf-m-expanded', open);
        toggle.setAttribute('aria-expanded', String(open));
    }

    return { show: show, next: next, back: back, toggleNav: toggleNav,
             at: function () { return at; } };
}
window.Wizard = Wizard;
