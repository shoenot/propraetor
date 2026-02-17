/**
 * Searchable Select – transforms <select data-searchable="model_name"> into
 * AJAX-powered search dropdowns.
 *
 * Attributes read from the original <select>:
 *   data-searchable   – model key sent to /api/search/?model=…
 *   data-placeholder   – placeholder text for the search input
 *   data-filters       – extra query-string params, e.g. "filter_company=3"
 *   data-min-chars     – min chars before searching (default 2)
 */
(function () {
    'use strict';

    var DEBOUNCE_MS = 250;
    var DEFAULT_MIN_CHARS = 2;
    var MAX_RESULTS = 20;
    var SEARCH_URL = '/api/search/';

    /* ------------------------------------------------------------------ */
    /*  Utilities                                                          */
    /* ------------------------------------------------------------------ */

    function debounce(fn, ms) {
        var timer;
        return function () {
            var ctx = this, args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
        };
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    /* ------------------------------------------------------------------ */
    /*  Build the UI around one <select>                                   */
    /* ------------------------------------------------------------------ */

    function initSelect(select) {
        if (select.hasAttribute('data-ss-init')) return;
        select.setAttribute('data-ss-init', '1');

        var model       = select.getAttribute('data-searchable');
        var placeholder = select.getAttribute('data-placeholder') || 'type to search\u2026';
        var filters     = select.getAttribute('data-filters') || '';
        var minChars    = parseInt(select.getAttribute('data-min-chars'), 10) || DEFAULT_MIN_CHARS;

        /* Hide original select (keep in DOM for form submission) */
        select.style.display = 'none';
        select.tabIndex = -1;

        /* ---- Container ---- */
        var container = document.createElement('div');
        container.className = 'ss-container';
        select.parentNode.insertBefore(container, select);
        container.appendChild(select);               // move select inside

        /* ---- Search input ---- */
        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'ss-search form-select';
        input.placeholder = placeholder;
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('spellcheck', 'false');
        container.appendChild(input);

        /* ---- Clear button ---- */
        var clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.className = 'ss-clear';
        clearBtn.innerHTML = '&times;';
        clearBtn.title = 'Clear';
        container.appendChild(clearBtn);

        /* ---- Dropdown ---- */
        var dropdown = document.createElement('div');
        dropdown.className = 'ss-dropdown';
        container.appendChild(dropdown);

        /* ---- State ---- */
        var highlightIdx = -1;
        var isOpen = false;
        var lastQuery = '';
        var userCleared = false;

        /* ---- Helpers ---- */

        function selectedText() {
            var opt = select.options[select.selectedIndex];
            if (opt && opt.value) return opt.textContent.trim();
            return '';
        }

        function syncDisplay() {
            var txt = selectedText();
            input.value = txt;
            clearBtn.style.display = txt ? '' : 'none';
        }

        function open() {
            dropdown.style.display = 'block';
            isOpen = true;
        }

        function close() {
            dropdown.style.display = 'none';
            isOpen = false;
            highlightIdx = -1;
        }

        function setValue(id, text) {
            /* Ensure an <option> with this id exists */
            var opt = select.querySelector('option[value="' + id + '"]');
            if (!opt) {
                opt = document.createElement('option');
                opt.value = id;
                opt.textContent = text;
                select.appendChild(opt);
            }
            select.value = String(id);
            input.value = text;
            clearBtn.style.display = '';
            userCleared = false;
            close();
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function clearValue() {
            select.value = '';
            input.value = '';
            clearBtn.style.display = 'none';
            userCleared = true;
            close();
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function highlightOption(idx) {
            var items = dropdown.querySelectorAll('.ss-option');
            items.forEach(function (el) { el.classList.remove('ss-highlighted'); });
            if (idx >= 0 && idx < items.length) {
                items[idx].classList.add('ss-highlighted');
                /* Scroll into view if needed */
                var rect = items[idx].getBoundingClientRect();
                var ddRect = dropdown.getBoundingClientRect();
                if (rect.bottom > ddRect.bottom) {
                    dropdown.scrollTop += rect.bottom - ddRect.bottom;
                } else if (rect.top < ddRect.top) {
                    dropdown.scrollTop -= ddRect.top - rect.top;
                }
            }
            highlightIdx = idx;
        }

        /* ---- Render helpers ---- */

        function renderHint(text) {
            dropdown.innerHTML = '<div class="ss-hint">' + escapeHtml(text) + '</div>';
            open();
        }

        function renderResults(data, query) {
            dropdown.innerHTML = '';

            if (data.results.length === 0) {
                dropdown.innerHTML = '<div class="ss-hint">no results found</div>';
                open();
                return;
            }

            data.results.forEach(function (item, i) {
                var div = document.createElement('div');
                div.className = 'ss-option';
                div.setAttribute('data-value', item.id);

                /* Highlight matching substring */
                var txt = item.text;
                if (query) {
                    var lc = txt.toLowerCase();
                    var qi = lc.indexOf(query.toLowerCase());
                    if (qi !== -1) {
                        div.innerHTML =
                            escapeHtml(txt.substring(0, qi)) +
                            '<mark>' + escapeHtml(txt.substring(qi, qi + query.length)) + '</mark>' +
                            escapeHtml(txt.substring(qi + query.length));
                    } else {
                        div.textContent = txt;
                    }
                } else {
                    div.textContent = txt;
                }

                div.addEventListener('mousedown', function (e) {
                    /* mousedown so it fires before input blur */
                    e.preventDefault();
                    setValue(item.id, item.text);
                });

                div.addEventListener('mouseenter', function () {
                    highlightOption(i);
                });

                dropdown.appendChild(div);
            });

            /* "more results" hint */
            if (data.total > data.results.length) {
                var hint = document.createElement('div');
                hint.className = 'ss-hint';
                hint.textContent = 'showing ' + data.results.length + ' of ' + data.total + ' \u2014 narrow your search';
                dropdown.appendChild(hint);
            }

            highlightIdx = -1;
            open();
        }

        /* ---- Fetch ---- */

        function doSearch(query) {
            if (query === lastQuery && isOpen) return;
            lastQuery = query;

            var params = 'model=' + encodeURIComponent(model) +
                         '&q=' + encodeURIComponent(query) +
                         '&limit=' + MAX_RESULTS;
            if (filters) params += '&' + filters;

            fetch(SEARCH_URL + '?' + params)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    /* Only render if this is still the latest query */
                    if (query !== lastQuery) return;
                    renderResults(data, query);
                })
                .catch(function () {
                    dropdown.innerHTML = '<div class="ss-hint ss-error">search error</div>';
                    open();
                });
        }

        var debouncedSearch = debounce(function () {
            var q = input.value.trim();
            if (q.length < minChars) {
                renderHint('type ' + minChars + '+ characters to search');
                return;
            }
            doSearch(q);
        }, DEBOUNCE_MS);

        /* ---- Events ---- */

        input.addEventListener('input', function () {
            var q = this.value.trim();
            /* If user manually cleared the input, clear the selection */
            if (q.length === 0) {
                if (select.value) {
                    userCleared = true;
                    select.value = '';
                    clearBtn.style.display = 'none';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                }
                lastQuery = '';
                close();
                return;
            }
            /* Reset userCleared flag when user starts typing */
            userCleared = false;
            if (q.length < minChars) {
                lastQuery = '';
                renderHint('type ' + minChars + '+ characters to search');
                return;
            }
            debouncedSearch();
        });

        input.addEventListener('focus', function () {
            var q = this.value.trim();
            this.select();                 // select text for easy overwrite
            /* Reset userCleared flag on focus only if there is text */
            if (q.length > 0) {
                userCleared = false;
            }
            if (q.length < minChars) {
                renderHint('type ' + minChars + '+ characters to search');
            } else if (dropdown.innerHTML) {
                open();
            } else {
                doSearch(q);
            }
        });

        input.addEventListener('blur', function () {
            /* Delay close so click on option can fire first */
            setTimeout(function () {
                close();
                if (userCleared) {
                    /* User intentionally cleared — keep it empty */
                    input.value = '';
                } else {
                    /* Restore display text if user typed gibberish */
                    var cur = selectedText();
                    if (cur) {
                        input.value = cur;
                    } else {
                        input.value = '';
                    }
                }
            }, 200);
        });

        input.addEventListener('keydown', function (e) {
            var items = dropdown.querySelectorAll('.ss-option');
            var count = items.length;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (!isOpen) {
                    var q = input.value.trim();
                    if (q.length >= minChars) doSearch(q);
                    return;
                }
                highlightOption(highlightIdx < count - 1 ? highlightIdx + 1 : 0);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (!isOpen) return;
                highlightOption(highlightIdx > 0 ? highlightIdx - 1 : count - 1);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (isOpen && highlightIdx >= 0 && highlightIdx < count) {
                    var chosen = items[highlightIdx];
                    setValue(
                        chosen.getAttribute('data-value'),
                        chosen.textContent
                    );
                }
            } else if (e.key === 'Escape') {
                e.preventDefault();
                /* If the input is empty, treat Escape as an intentional clear */
                if (input.value.trim() === '' && select.value) {
                    clearValue();
                } else {
                    close();
                }
                input.blur();
            } else if (e.key === 'Tab') {
                /* Allow normal tab but pick highlighted if any */
                if (isOpen && highlightIdx >= 0 && highlightIdx < count) {
                    var tab_chosen = items[highlightIdx];
                    setValue(
                        tab_chosen.getAttribute('data-value'),
                        tab_chosen.textContent
                    );
                }
                close();
            }
        });

        clearBtn.addEventListener('click', function (e) {
            e.preventDefault();
            clearValue();
            input.focus();
        });

        /* Close on outside click */
        document.addEventListener('mousedown', function (e) {
            if (!container.contains(e.target)) {
                close();
            }
        });

        /* ---- Initial state ---- */
        syncDisplay();
    }

    /* ------------------------------------------------------------------ */
    /*  Bootstrap & HTMX re-init                                           */
    /* ------------------------------------------------------------------ */

    function initAll(root) {
        root = root || document;
        var selects = root.querySelectorAll('select[data-searchable]:not([data-ss-init])');
        for (var i = 0; i < selects.length; i++) {
            initSelect(selects[i]);
        }
    }

    /* On initial page load */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initAll(); });
    } else {
        initAll();
    }

    /* After HTMX swaps new content in (use document, not e.detail.target,
       because hx-swap="outerHTML" detaches the old target from the DOM) */
    document.addEventListener('htmx:afterSettle', function () {
        initAll(document);
    });

    /* Expose for manual calls if needed */
    window.SearchableSelect = { init: initAll };

})();