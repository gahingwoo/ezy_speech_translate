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

    /* The dim, faded in and out. A transition needs two states and a frame
       between them: [hidden] comes off first and the class goes on in the next
       frame, so there is an opacity to travel from. On the way back the class
       comes off, the fade runs, and only then is the element taken out of the
       layout; taking it out at once would cut the fade to nothing, which is
       what the display toggle it replaces did. */
    function setOverlay(on) {
        const dim = overlay();
        if (!dim) return;
        if (on) {
            dim.hidden = false;
            // Read a layout property to make the browser settle on the opacity
            // of nought before the class asks for one. Waiting a frame instead
            // was not enough: the first style it computed for the element
            // already had the class on it, so there was nothing to travel from
            // and the dim arrived at full strength at once.
            void dim.offsetHeight;
            dim.classList.add('active');
            return;
        }
        dim.classList.remove('active');
        if (dim.hidden === false) {
            window.setTimeout(function () {
                if (!dim.classList.contains('active')) dim.hidden = true;
            }, 250);
        }
    }

    function setSidebarOpen(open) {
        const el = sidebar();
        if (!el) return;
        const wide = sidebarIsWide();
        el.classList.toggle('pf-m-collapsed', wide && !open);
        el.classList.toggle('pf-m-expanded', !wide && open);
        setOverlay(open && !wide);
        const button = toggleButton();
        if (button) {
            button.classList.toggle('active', open);
            button.setAttribute('aria-expanded', String(open));
        }
    }
    window.setSidebarOpen = setSidebarOpen;

    /* Escape closes the drawer, the way it closes every other thing that opens
       over the page. Only the drawer: folding the desktop column away because
       someone pressed Escape in a field would be a surprise. */
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !sidebarIsWide() && isSidebarOpen()) setSidebarOpen(false);
    });

    /* A width change can leave the drawer's dim over a layout that no longer
       has a drawer. */
    window.matchMedia('(min-width: 75rem)').addEventListener('change', function (e) {
        if (e.matches) setOverlay(false);
    });

    window.toggleMobileMenu = function () {
        setSidebarOpen(!isSidebarOpen());
    };

    /* Only the drawer closes on its own; folding the desktop panel away
       because someone pressed a button inside it would be a surprise. */
    window.closeMobileMenu = function () {
        if (!sidebarIsWide()) setSidebarOpen(false);
    };
})();
