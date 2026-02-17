// Auto-dismiss toasts after 5 seconds
(function() {
    function dismissToasts() {
        var toasts = document.querySelectorAll('.toast');
        toasts.forEach(function(toast) {
            if (toast.dataset.timerSet) return;
            toast.dataset.timerSet = 'true';
            setTimeout(function() {
                toast.classList.add('toast-fade-out');
                setTimeout(function() { toast.remove(); }, 300);
            }, 5000);
        });
    }
    dismissToasts();
    // Re-run after HTMX swaps (messages may appear after redirects)
    document.body.addEventListener('htmx:afterSettle', dismissToasts);
})();
