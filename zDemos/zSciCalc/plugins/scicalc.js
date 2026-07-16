// scicalc.js — Bifrost-only keypad. Pure DOM/event-listener glue: it never
// computes anything, it only builds a button grid and appends into the SAME
// text field the zCLI wizard reads. Math stays in scicalc.py.
(function () {
  if (window.__zSciCalcKeypadLoaded) return;
  window.__zSciCalcKeypadLoaded = true;

  // Visuals live in styles/scicalc.css (loaded via zMeta.zBrush) — this file
  // only builds structure + behavior. `data-key` lets the CSS color-code
  // operators/functions without JS handing out per-key classes.
  var BASIC_KEYS = [
    "7", "8", "9", "/",
    "4", "5", "6", "*",
    "1", "2", "3", "-",
    "0", ".", "=", "+",
    "(", ")", "C", "sqrt(",
  ];

  // { label: what the button SHOWS, insert: what it TYPES } — lets a
  // calculator-familiar label (ln, x^y, sin⁻¹) map onto the plugin's actual
  // Python/math syntax (log(, **, asin() without a second vocabulary.
  var SCI_KEYS = [
    { label: "sin", insert: "sin(" },
    { label: "cos", insert: "cos(" },
    { label: "tan", insert: "tan(" },
    { label: "x^y", insert: "**" },
    { label: "sin⁻¹", insert: "asin(" },
    { label: "cos⁻¹", insert: "acos(" },
    { label: "tan⁻¹", insert: "atan(" },
    { label: "√", insert: "sqrt(" },
    { label: "ln", insert: "log(" },
    { label: "log", insert: "log10(" },
    { label: "eˣ", insert: "exp(" },
    { label: "|x|", insert: "abs(" },
    { label: "π", insert: "pi" },
    { label: "e", insert: "e" },
    { label: "(", insert: "(" },
    { label: ")", insert: ")" },
  ];

  // Set after a result is painted into the display: the next DIGIT starts a
  // fresh expression (real-calculator muscle memory), while an OPERATOR chains
  // onto the result. Cleared by any other edit.
  var justEvaluated = false;
  var CHAINABLE = /^[+\-*/]$|^\*\*$/;

  function findExpr() {
    return document.querySelector(".zSciCalc-expr");
  }

  function findSubmit() {
    var input = findExpr();
    var form = input && input.closest("form");
    return form ? form.querySelector("button[type='submit']") : null;
  }

  function pressKey(insert) {
    var input = findExpr();
    if (!input) return;
    if (insert === "C") {
      input.value = "";
      justEvaluated = false;
    } else if (insert === "=") {
      // "=" IS the submit — same wire as the Evaluate button / Enter key.
      var btn = findSubmit();
      if (btn) btn.click();
      return;
    } else {
      if (justEvaluated && !CHAINABLE.test(insert)) input.value = "";
      justEvaluated = false;
      input.value += insert;
    }
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  }

  function makeKey(label, insert, extraClass) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.className = "zSciCalc-key" + (extraClass ? " " + extraClass : "");
    btn.dataset.key = insert;
    btn.addEventListener("click", function () {
      pressKey(insert);
    });
    return btn;
  }

  function buildKeypad(slot) {
    slot.dataset.zSciCalcMounted = "1";

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "zSciCalc-toggle";
    toggle.textContent = "Scientific ▾";
    slot.appendChild(toggle);

    var basicGrid = document.createElement("div");
    basicGrid.className = "zSciCalc-keypad-grid zSciCalc-keypad-basic";
    BASIC_KEYS.forEach(function (key) {
      basicGrid.appendChild(makeKey(key, key));
    });
    slot.appendChild(basicGrid);

    var sciGrid = document.createElement("div");
    sciGrid.className = "zSciCalc-keypad-grid zSciCalc-keypad-sci";
    sciGrid.hidden = true;
    SCI_KEYS.forEach(function (k) {
      sciGrid.appendChild(makeKey(k.label, k.insert, "zSciCalc-key--sci"));
    });
    slot.appendChild(sciGrid);

    toggle.addEventListener("click", function () {
      var showingSci = !sciGrid.hidden;
      sciGrid.hidden = showingSci;
      toggle.textContent = showingSci ? "Scientific ▾" : "Basic ▴";
    });
  }

  // The server keeps re-hydrating the slot's placeholder text alongside our
  // buttons (async WS render, arrives after our first mount) — so instead of
  // mounting once, we keep pruning anything that isn't one of our own nodes.
  function pruneStrayChildren(slot) {
    Array.prototype.slice.call(slot.children).forEach(function (child) {
      var ours =
        child.classList.contains("zSciCalc-toggle") ||
        child.classList.contains("zSciCalc-keypad-grid");
      if (!ours) slot.removeChild(child);
    });
  }

  // The form renderer hardcodes "Submit"; a calculator says "Evaluate".
  // Only rewrite the idle label — never fight transient states
  // ("Processing…") the renderer paints mid-submit.
  function relabelSubmit() {
    var btn = findSubmit();
    if (btn && btn.textContent === "Submit") btn.textContent = "Evaluate";
  }

  // Result-to-display: the plugin's return ("expr = result") lands in the
  // dialog's .zDialog-feedback slot as a signal. Mirror the RESULT into the
  // display (like a real calculator) and let the feedback line stand as the
  // history echo. Errors stay in the slot only — the display keeps the
  // expression so the user can fix it in place.
  var lastFeedback = "";
  function mirrorResult() {
    var slot = document.querySelector(".zDialog-feedback");
    if (!slot) return;
    // textContent includes the signal's dismiss "×" button — strip any
    // non-text-node children before reading, or the LCD shows "11×".
    var text = "";
    slot.querySelectorAll("*").forEach(function (el) {
      if (el.tagName === "BUTTON") return;
      if (!el.children.length) text += el.textContent;
    });
    text = (text || slot.textContent || "").replace(/\s*×\s*$/, "").trim();
    if (!text || text === lastFeedback) return;
    lastFeedback = text;
    var m = text.match(/^(.+) = (.+)$/);
    if (!m) return;
    var input = findExpr();
    if (!input) return;
    input.value = m[2];
    justEvaluated = true;
  }

  function tick() {
    var slot = document.querySelector(".zSciCalc-keypad");
    if (slot) {
      if (!slot.dataset.zSciCalcMounted) buildKeypad(slot);
      pruneStrayChildren(slot);
    }
    relabelSubmit();
    mirrorResult();
  }

  tick();
  var observer = new MutationObserver(tick);
  observer.observe(document.body, { childList: true, subtree: true });
})();
