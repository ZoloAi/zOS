// tasklist.js — loaded via zMeta.zScripts: [&.tasklist] on the Main block.
// Teaching goal: a zBtn's `&.` plugin action (Toggle) mutates data over the
// socket but the client doesn't repaint the chunk it already rendered — a
// full reload re-runs the page's initial render path, which does repaint.
// Toggle fires an async round-trip first, so wait for it to land before
// reloading; Back is pure client-side nav (the insert already completed when
// the dialog submitted), so it reloads immediately.
//
// Delete is a zModal + zDialog now (08_data_crud.md per_row "preferred") —
// a real zData block, no plugin — so it does NOT go through this listener;
// the Refresh button (a self-hop zDelta) is the next real navigation that
// picks up the post-delete row set (per_row "gotcha": a modal detour never
// re-renders the page that opened it).
(function () {
  var ROW_ACTION_DELAY_MS = 1500;

  function closestKey(el, keys) {
    return !!(el && el.closest && el.closest(keys));
  }

  document.addEventListener("click", function (evt) {
    if (closestKey(evt.target, '[data-zkey="Back"]')) {
      window.location.reload();
    } else if (closestKey(evt.target, '[data-zkey="Toggle"]')) {
      setTimeout(function () {
        window.location.reload();
      }, ROW_ACTION_DELAY_MS);
    }
  });
})();
