// Nav interactions (mobile toggle + dropdowns). Encapsulated so we can re-bind after HTMX swaps.
(function() {
    function bindNavInteractions() {
        // Mobile nav toggle
        const toggle = document.getElementById('nav-toggle');
        const nav = document.getElementById('main-nav');
        if (toggle && nav) {
            // Avoid binding multiple times by marking elements once bound
            if (!toggle.dataset.bound) {
                toggle.addEventListener('click', function() {
                    const expanded = toggle.getAttribute('aria-expanded') === 'true';
                    toggle.setAttribute('aria-expanded', String(!expanded));
                    toggle.classList.toggle('active');
                    nav.classList.toggle('nav-open');
                });
                toggle.dataset.bound = 'true';
            }

            // Close menu when a nav link is clicked
            nav.querySelectorAll('a').forEach(function(link) {
                if (link.dataset.bound) return;
                link.addEventListener('click', function() {
                    toggle.setAttribute('aria-expanded', 'false');
                    toggle.classList.remove('active');
                    nav.classList.remove('nav-open');
                });
                link.dataset.bound = 'true';
            });

            // Close menu when clicking outside
            if (!document.body.dataset.navOutsideBound) {
                document.addEventListener('click', function(e) {
                    if (!toggle.contains(e.target) && !nav.contains(e.target)) {
                        toggle.setAttribute('aria-expanded', 'false');
                        toggle.classList.remove('active');
                        nav.classList.remove('nav-open');
                    }
                });
                document.body.dataset.navOutsideBound = 'true';
            }
        }

        // Dropdown nav toggle
        document.querySelectorAll('.nav-dropdown-toggle').forEach(function(btn) {
            if (btn.dataset.bound) return;
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const dropdown = btn.closest('.nav-dropdown');
                const isOpen = dropdown.classList.contains('open');

                // Close all other dropdowns
                document.querySelectorAll('.nav-dropdown.open').forEach(function(d) {
                    if (d !== dropdown) {
                        d.classList.remove('open');
                        d.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
                    }
                });

                dropdown.classList.toggle('open', !isOpen);
                btn.setAttribute('aria-expanded', String(!isOpen));
            });
            btn.dataset.bound = 'true';
        });

        // Close dropdowns when clicking outside
        if (!document.body.dataset.dropdownOutsideBound) {
            document.addEventListener('click', function(e) {
                if (!e.target.closest('.nav-dropdown')) {
                    document.querySelectorAll('.nav-dropdown.open').forEach(function(d) {
                        d.classList.remove('open');
                        d.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
                    });
                }
            });
            document.body.dataset.dropdownOutsideBound = 'true';
        }

        // Close dropdown when a link inside it is clicked
        document.querySelectorAll('.nav-dropdown-menu a').forEach(function(link) {
            if (link.dataset.bound) return;
            link.addEventListener('click', function() {
                const dropdown = link.closest('.nav-dropdown');
                if (dropdown) {
                    dropdown.classList.remove('open');
                    dropdown.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
                }
                document.querySelectorAll('.nav-dropdown.open').forEach(function(d) {
                    d.classList.remove('open');
                    d.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
                });
                const toggle = document.getElementById('nav-toggle');
                const nav = document.getElementById('main-nav');
                if (toggle && nav) {
                    toggle.setAttribute('aria-expanded', 'false');
                    toggle.classList.remove('active');
                    nav.classList.remove('nav-open');
                }
            });
            link.dataset.bound = 'true';
        });
    }

    // Bind on initial load and re-bind after HTMX swaps so event listeners persist.
    document.addEventListener('DOMContentLoaded', bindNavInteractions);
    if (window.htmx) {
        document.body.addEventListener('htmx:afterOnLoad', bindNavInteractions);
        document.body.addEventListener('htmx:afterSettle', bindNavInteractions);
    }
    // Run immediately in case script executes after DOMContentLoaded
    bindNavInteractions();
})();

// Configure htmx to avoid scrolling on boosted navigations
if (window.htmx) {
    // Prevent htmx from forcing scroll on boost-driven requests
    htmx.config.scrollIntoViewOnBoost = false;
    // Use instant behavior so the viewport position is preserved
    htmx.config.scrollBehavior = 'instant';

    // Close all open nav dropdowns (and mobile menu) as soon as
    // htmx begins processing a boosted navigation request.
    document.body.addEventListener('htmx:beforeRequest', function() {
        document.querySelectorAll('.nav-dropdown.open').forEach(function(d) {
            d.classList.remove('open');
            d.querySelector('.nav-dropdown-toggle').setAttribute('aria-expanded', 'false');
        });
        var toggle = document.getElementById('nav-toggle');
        var nav = document.getElementById('main-nav');
        if (toggle && nav) {
            toggle.setAttribute('aria-expanded', 'false');
            toggle.classList.remove('active');
            nav.classList.remove('nav-open');
        }
    });
}

// Update navigation highlighting (direct links and dropdown toggles)
function updateNavHighlighting() {
    const currentPath = window.location.pathname;

    // Update direct nav links
    document.querySelectorAll('#main-nav > a').forEach(link => {
        const linkPath = link.getAttribute('href');
        if (!linkPath) return;
        if (linkPath === '/') {
            link.classList.toggle('active', currentPath === '/');
        } else {
            link.classList.toggle('active', currentPath.startsWith(linkPath));
        }
    });

    // Update dropdown menu links and toggle buttons. Also sync aria-expanded and open state.
    document.querySelectorAll('.nav-dropdown').forEach(dropdown => {
        let hasActive = false;
        dropdown.querySelectorAll('.nav-dropdown-menu a').forEach(link => {
            const linkPath = link.getAttribute('href');
            const isActive = linkPath && (linkPath === '/' ? currentPath === '/' : currentPath.startsWith(linkPath));
            link.classList.toggle('active', isActive);
            if (isActive) hasActive = true;
        });
        const toggleBtn = dropdown.querySelector('.nav-dropdown-toggle');
        if (toggleBtn) {
            // visual active class only; do not auto-open dropdowns or change aria-expanded.
            // This keeps the child link highlighted but prevents updateNavHighlighting()
            // from forcing dropdowns to open after navigation.
            toggleBtn.classList.toggle('active', hasActive);
        }
    });
}

// Run on initial load, and after HTMX swaps/loads so highlighting stays correct
document.addEventListener('DOMContentLoaded', updateNavHighlighting);
if (window.htmx) {
    document.body.addEventListener('htmx:afterOnLoad', updateNavHighlighting);
    document.body.addEventListener('htmx:afterSettle', updateNavHighlighting);
}
// Ensure it's applied immediately in case this script runs after DOMContentLoaded
updateNavHighlighting();
