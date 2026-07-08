// contacts.js — loaded via zMeta.zScripts: [&.contacts] on the Main block.
// Teaching goal: same as zTaskList's plugin — a zBtn's `&.` action (Delete)
// mutates data over the socket but doesn't repaint the SAME block it already
// rendered (zDelta nav blocks re-render fresh on their own; a same-block
// action doesn't). A full reload re-runs the initial render path, which
// does repaint. Delete fires an async round-trip first, so wait for it to
// land before reloading.
(function () {
    var ROW_ACTION_DELAY_MS = 1500;

    function closestKey(el, keys) {
        return !!(el && el.closest && el.closest(keys));
    }

    document.addEventListener("click", function (evt) {
        if (closestKey(evt.target, '[data-zkey="Delete"]')) {
            setTimeout(function () {
                window.location.reload();
            }, ROW_ACTION_DELAY_MS);
        }
    });
})();
