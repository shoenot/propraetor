/**
 * Inline Create – adds a [+] button next to every searchable-select dropdown
 * so users can create new FK entries on the fly without leaving the current
 * form.
 *
 * Flow:
 *   1. A [+] button is injected into each `.ss-container`.
 *   2. Clicking it opens a styled modal overlay and fetches the creation form
 *      from `/modal/create/<model_key>/` via `fetch()`.
 *   3. The form is rendered inside the modal. Searchable-selects within the
 *      modal are initialised so nested FK lookups work.
 *   4. On submit the form is POSTed via `fetch()`.
 *      – Success (JSON `{success, id, text}`) → new `<option>` is injected
 *        into the originating `<select>`, selected, and the modal closes.
 *      – Validation errors → the modal body is replaced with the re-rendered
 *        form fragment (which includes error messages).
 *   5. Modals stack – you can open a [+] inside a modal and it layers on top.
 *      Closing the inner modal returns focus to the outer one.
 */
(function () {
    'use strict';

    var CREATE_URL_PREFIX = '/modal/create/';

    // Models that support inline creation (must match _MODAL_CREATE_CONFIGS keys).
    var CREATABLE_MODELS = [
        'company', 'asset_model', 'employee', 'location', 'category',
        'department', 'vendor', 'component_type', 'requisition', 'invoice',
        'asset', 'component', 'invoice_line_item'
    ];

    var CREATABLE_SET = {};
    CREATABLE_MODELS.forEach(function (m) { CREATABLE_SET[m] = true; });

    // Stack of open modals (for layering z-index and Escape handling).
    var modalStack = [];
    var BASE_Z = 10000;

    /* ------------------------------------------------------------------ */
    /*  Helpers                                                            */
    /* ------------------------------------------------------------------ */

    function getCSRFToken() {
        // Try cookie first, then meta tag, then hidden input
        var cookie = document.cookie.split(';').find(function (c) {
            return c.trim().startsWith('csrftoken=');
        });
        if (cookie) return cookie.split('=')[1];

        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');

        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;

        // Read from the hx-headers attribute on body (Django pattern used in this project)
        var body = document.body;
        if (body) {
            var hxHeaders = body.getAttribute('hx-headers');
            if (hxHeaders) {
                try {
                    var parsed = JSON.parse(hxHeaders);
                    if (parsed['x-csrftoken']) return parsed['x-csrftoken'];
                } catch (e) { /* ignore */ }
            }
        }

        return '';
    }

    /* ------------------------------------------------------------------ */
    /*  Modal DOM creation                                                 */
    /* ------------------------------------------------------------------ */

    function createModal(modelKey, title, onCreated) {
        var depth = modalStack.length;
        var zIndex = BASE_Z + depth * 10;

        // -- Overlay --
        var overlay = document.createElement('div');
        overlay.className = 'ic-overlay';
        overlay.style.zIndex = zIndex;

        // -- Modal box --
        var modal = document.createElement('div');
        modal.className = 'ic-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-label', title);

        // -- Header --
        var header = document.createElement('div');
        header.className = 'ic-modal-header';

        var titleEl = document.createElement('h3');
        titleEl.className = 'ic-modal-title';
        titleEl.textContent = '> ' + title;

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'ic-modal-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.title = 'Close';

        header.appendChild(titleEl);
        header.appendChild(closeBtn);

        // -- Body (will hold the form) --
        var body = document.createElement('div');
        body.className = 'ic-modal-body';
        body.innerHTML = '<div class="ic-loading">loading form\u2026</div>';

        // -- Footer --
        var footer = document.createElement('div');
        footer.className = 'ic-modal-footer';

        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'btn btn-ghost';
        cancelBtn.textContent = 'cancel';

        var submitBtn = document.createElement('button');
        submitBtn.type = 'button';
        submitBtn.className = 'btn btn-primary';
        submitBtn.innerHTML =
            '<svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
            '</svg> create';

        footer.appendChild(cancelBtn);
        footer.appendChild(submitBtn);

        modal.appendChild(header);
        modal.appendChild(body);
        modal.appendChild(footer);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Force reflow then show
        overlay.offsetHeight; // eslint-disable-line no-unused-expressions
        overlay.classList.add('ic-visible');

        // -- State object --
        var state = {
            overlay: overlay,
            modal: modal,
            body: body,
            submitBtn: submitBtn,
            modelKey: modelKey,
            onCreated: onCreated,
            closed: false
        };

        modalStack.push(state);

        // -- Close handlers --
        function close() {
            if (state.closed) return;
            state.closed = true;
            overlay.classList.remove('ic-visible');
            setTimeout(function () {
                if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
            }, 200);
            var idx = modalStack.indexOf(state);
            if (idx !== -1) modalStack.splice(idx, 1);
        }

        closeBtn.addEventListener('click', close);
        cancelBtn.addEventListener('click', close);
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) close();
        });

        state.close = close;

        // -- Load form --
        fetchForm(state);

        // -- Submit handler --
        submitBtn.addEventListener('click', function () {
            submitForm(state);
        });

        return state;
    }

    /* ------------------------------------------------------------------ */
    /*  Fetch form HTML from the server                                    */
    /* ------------------------------------------------------------------ */

    function fetchForm(state) {
        state.body.innerHTML = '<div class="ic-loading">loading form\u2026</div>';

        fetch(CREATE_URL_PREFIX + state.modelKey + '/', {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (r) { return r.text(); })
        .then(function (html) {
            injectForm(state, html);
        })
        .catch(function () {
            state.body.innerHTML = '<div class="ic-loading ic-error">failed to load form</div>';
        });
    }

    function injectForm(state, html) {
        state.body.innerHTML = html;

        // Initialise searchable-selects inside the modal
        if (window.SearchableSelect) {
            window.SearchableSelect.init(state.body);
        }

        // Initialise [+] buttons inside the modal (for nested creation)
        initAll(state.body);

        // Allow Enter inside inputs to submit
        state.body.querySelectorAll('input, select').forEach(function (el) {
            el.addEventListener('keydown', function (e) {
                // Don't intercept Enter inside searchable-select inputs
                if (e.key === 'Enter' && !el.classList.contains('ss-search')) {
                    e.preventDefault();
                    submitForm(state);
                }
            });
        });

        // Focus first visible input
        var first = state.body.querySelector('input:not([type="hidden"]), select, textarea');
        if (first) {
            setTimeout(function () { first.focus(); }, 50);
        }
    }

    /* ------------------------------------------------------------------ */
    /*  Submit form via fetch()                                            */
    /* ------------------------------------------------------------------ */

    function submitForm(state) {
        if (state.closed) return;

        // Build FormData from all inputs inside the modal body
        var formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCSRFToken());

        // Collect all form inputs within the modal body
        state.body.querySelectorAll('input, select, textarea').forEach(function (el) {
            if (!el.name) return;

            if (el.type === 'checkbox') {
                if (el.checked) formData.append(el.name, el.value || 'on');
            } else if (el.type === 'radio') {
                if (el.checked) formData.append(el.name, el.value);
            } else if (el.tagName === 'SELECT') {
                // For selects (including hidden ones behind searchable-select),
                // use the real <select> value
                if (el.value) formData.append(el.name, el.value);
            } else {
                formData.append(el.name, el.value);
            }
        });

        // Disable submit button to prevent double-clicks
        state.submitBtn.disabled = true;
        state.submitBtn.textContent = 'saving\u2026';

        fetch(CREATE_URL_PREFIX + state.modelKey + '/', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCSRFToken()
            },
            body: formData
        })
        .then(function (response) {
            var ct = response.headers.get('content-type') || '';
            if (ct.indexOf('application/json') !== -1) {
                return response.json().then(function (data) {
                    return { type: 'json', data: data };
                });
            }
            return response.text().then(function (html) {
                return { type: 'html', data: html };
            });
        })
        .then(function (result) {
            if (result.type === 'json' && result.data.success) {
                // Success! Call back to set the value and close.
                if (state.onCreated) {
                    state.onCreated(result.data.id, result.data.text);
                }
                state.close();
            } else if (result.type === 'html') {
                // Validation errors – re-render form
                injectForm(state, result.data);
                state.submitBtn.disabled = false;
                state.submitBtn.innerHTML =
                    '<svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
                    '</svg> create';
            } else {
                // Unexpected JSON without success
                state.body.innerHTML = '<div class="ic-loading ic-error">unexpected server response</div>';
                state.submitBtn.disabled = false;
                state.submitBtn.textContent = 'retry';
            }
        })
        .catch(function () {
            state.body.insertAdjacentHTML(
                'afterbegin',
                '<div class="form-errors-banner"><ul><li>network error – please try again</li></ul></div>'
            );
            state.submitBtn.disabled = false;
            state.submitBtn.innerHTML =
                '<svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>' +
                '</svg> create';
        });
    }

    /* ------------------------------------------------------------------ */
    /*  Inject [+] buttons into searchable-select containers               */
    /* ------------------------------------------------------------------ */

    function initAll(root) {
        root = root || document;
        var containers = root.querySelectorAll('.ss-container');

        containers.forEach(function (container) {
            // Skip if already has a [+] button
            if (container.querySelector('.ic-add-btn')) return;

            var select = container.querySelector('select[data-searchable]');
            if (!select) return;

            var modelKey = select.getAttribute('data-searchable');
            if (!CREATABLE_SET[modelKey]) return;

            // Create the [+] button
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'ic-add-btn';
            btn.title = 'Create new\u2026';
            btn.innerHTML = '+';

            // Insert button into the container (after ss-search, before dropdown)
            var searchInput = container.querySelector('.ss-search');
            if (searchInput && searchInput.nextSibling) {
                container.insertBefore(btn, searchInput.nextSibling);
            } else {
                container.appendChild(btn);
            }

            // Adjust padding on search input to make room for [+] button
            searchInput.style.paddingRight = '40px';

            // Move clear button a bit to the left to make room for [+] button
            var clearBtn = container.querySelector('.ss-clear');
            if (clearBtn) {
                clearBtn.style.right = '38px';
            }

            // Click handler
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                var title = modelKey.replace(/_/g, ' ');

                createModal(modelKey, 'new ' + title, function (newId, newText) {
                    // Inject new <option> into the original <select>
                    var opt = document.createElement('option');
                    opt.value = newId;
                    opt.textContent = newText;
                    select.appendChild(opt);
                    select.value = String(newId);

                    // Update the visible search input text
                    if (searchInput) {
                        searchInput.value = newText;
                    }

                    // Show clear button
                    if (clearBtn) {
                        clearBtn.style.display = '';
                    }

                    // Dispatch change so other dependent fields react
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                });
            });
        });
    }

    /* ------------------------------------------------------------------ */
    /*  Global Escape key handler (closes topmost modal)                   */
    /* ------------------------------------------------------------------ */

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modalStack.length > 0) {
            // Don't close if a searchable-select dropdown is open inside the modal
            var topModal = modalStack[modalStack.length - 1];
            var openDropdown = topModal.body.querySelector('.ss-dropdown[style*="block"]');
            if (openDropdown) return; // let searchable-select handle this Escape
            e.preventDefault();
            e.stopPropagation();
            topModal.close();
        }
    });

    /* ------------------------------------------------------------------ */
    /*  Bootstrap & HTMX re-init                                           */
    /* ------------------------------------------------------------------ */

    function boot() {
        initAll(document);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    // Re-init after HTMX swaps
    document.addEventListener('htmx:afterSettle', function () {
        initAll(document);
    });

    // Expose for manual use
    window.InlineCreate = {
        init: initAll,
        openModal: function (modelKey, onCreated) {
            var title = modelKey.replace(/_/g, ' ');
            return createModal(modelKey, 'new ' + title, onCreated);
        }
    };

})();