// ── Styled confirmation modal (replaces browser confirm()) ──────
(function() {
    var overlay = document.getElementById('confirm-overlay');
    var bodyEl  = document.getElementById('confirm-body');
    var cancelBtn = document.getElementById('confirm-cancel');
    var closeX    = document.getElementById('confirm-close-x');
    var proceedBtn = document.getElementById('confirm-proceed');
    var pendingEvt = null;

    function openModal(message) {
        bodyEl.textContent = message;
        overlay.classList.add('confirm-visible');
        overlay.setAttribute('aria-hidden', 'false');
        proceedBtn.focus();
    }

    function closeModal() {
        overlay.classList.remove('confirm-visible');
        overlay.setAttribute('aria-hidden', 'true');
        pendingEvt = null;
    }

    // Cancel / close handlers
    cancelBtn.addEventListener('click', closeModal);
    closeX.addEventListener('click', closeModal);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closeModal();
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && overlay.classList.contains('confirm-visible')) {
            closeModal();
        }
    });

    // Proceed handler — re-issue the htmx request
    proceedBtn.addEventListener('click', function() {
        if (pendingEvt) {
            pendingEvt.detail.issueRequest(true);
        }
        closeModal();
    });

    // Intercept htmx:confirm to show styled modal instead of browser dialog
    document.body.addEventListener('htmx:confirm', function(e) {
        var el = e.detail.elt;
        var msg = el.getAttribute('data-confirm-message') || el.getAttribute('hx-confirm');
        if (!msg) return; // no confirmation needed
        e.preventDefault();
        pendingEvt = e;
        openModal(msg);
    });

    // Also handle the bulk-action confirm() calls inside reusable_table.html
    // by monkey-patching window.confirm so bulk buttons also get the styled modal.
    var _nativeConfirm = window.confirm;
    window.confirm = function(msg) {
        // If called outside htmx (e.g. from inline JS), fall back to a
        // promise-based approach that can't block. For bulk actions we
        // return true here and let the htmx:confirm handler deal with
        // htmx-driven actions. Non-htmx callers still get native confirm.
        return _nativeConfirm.call(window, msg);
    };
})();
