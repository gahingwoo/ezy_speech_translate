/* The page's own sidebar, opened and closed.
 *
 * PatternFly owns the state; this only says which class applies at which
 * width. Below xl the panel is a drawer that .pf-m-expanded slides in; from xl
 * it is a column that .pf-m-collapsed folds away, and the main container
 * widens into the space. One toggle, two classes, because which one applies
 * depends on the width.
 *
 * It lives here rather than in one page's script because the settings page has
 * a sidebar too and had no way to open it: below xl the panel slid off the
 * left and the masthead carried no toggle, so on a laptop in a split window,
 * or on a phone, the list of setting groups was simply gone.
 *
 * Everything is found by role, not by id, so a page only has to lay the parts
 * out and name them the way PatternFly does.
 */
(function () {
    function sidebar() {
        return document.querySelector('.pf-v6-c-page__sidebar');
    }

    function overlay() {
        return document.querySelector('.sidebar-overlay');
    }

    function toggleButton() {
        return document.querySelector('.pf-v6-c-masthead__toggle .pf-v6-c-button');
    }

    function sidebarIsWide() {
        return window.matchMedia('(min-width: 75rem)').matches;
    }
    window.sidebarIsWide = sidebarIsWide;

    function isSidebarOpen() {
        const el = sidebar();
        if (!el) return false;
        return sidebarIsWide()
            ? !el.classList.contains('pf-m-collapsed')
            : el.classList.contains('pf-m-expanded');
    }
    window.isSidebarOpen = isSidebarOpen;

    function setSidebarOpen(open) {
        const el = sidebar();
        if (!el) return;
        const wide = sidebarIsWide();
        el.classList.toggle('pf-m-collapsed', wide && !open);
        el.classList.toggle('pf-m-expanded', !wide && open);
        const dim = overlay();
        if (dim) dim.classList.toggle('active', open && !wide);
        const button = toggleButton();
        if (button) {
            button.classList.toggle('active', open);
            button.setAttribute('aria-expanded', String(open));
        }
    }
    window.setSidebarOpen = setSidebarOpen;

    window.toggleMobileMenu = function () {
        setSidebarOpen(!isSidebarOpen());
    };

    /* Only the drawer closes on its own; folding the desktop panel away
       because someone pressed a button inside it would be a surprise. */
    window.closeMobileMenu = function () {
        if (!sidebarIsWide()) setSidebarOpen(false);
    };
})();
