Zolo is a declarative llm-native framework. Trust that console will speak back to you.

global_rules:
    architecture: facade/module pattern regardless of stack (py/js/zolo/other)
                  one file = one responsibility, entry point imports from modules
    ssot:         no logic duplication across files — extract shared logic to module
    violation:    if editing a file >600 LOC, refactor first unless surgical fix only
    refactor:     after any split/rename — update zRaven/<name>.zolo to match before re-running
    NOT_YAML:     .zolo files are zLSP-parsed — NOT YAML — NEVER quote string values, NEVER use yaml/json idioms
    data_rule:    NEVER use Python csv/pandas/sqlite3/raw SQL directly — ALL data ops use zData + zSchema
    plugin_rule:  plugins are pure logic — receive args, return result, nothing else
        NO state, NO orchestration, NO UI logic — zOS owns all of that
        if a plugin exceeds ~50 LOC it is doing zOS's job — refactor back to zEvents

phase_planning:
    1_intention: declare what the user needs — not how to build it
                 what entities exist? what can the user do with each?
                 what does the user see? what triggers an action? what is the result?
    2_mapping:   map each intention to a zOS event (zUI event reference in this file)
    3_dogfood:   segment the plan — terminal-first by default, GUI only if 1_intention requires visual I/O
        gui_required: [drawing, canvas, camera, realtime_visual, etc]

phase_CLI:
    0_scaffold:  zolo scaffold <appname> — run in target directory
    1_zUI:       fill __hints__ in UI/<app>.zolo — one segment from 3_dogfood at a time
    2_zRaven:    fill __hints__ in zRaven/<name>.zolo — test what you just wrote in 1_zUI (zRaven reference in this file)
    3_zSpark:    fill __hints__ in zSpark.<app>.zolo — zMode: zCLI (terminal i/o), zBlock from 1_zUI, zRaven: <name> (zSpark reference in this file)
    4_run:       z <appname> — zRaven auto-runs — fix ERROR lines — do NOT proceed until green
    5_repeat:    steps 1–4 for each segment from 3_dogfood
    exit_check:  verify global_rules — file sizes ≤600, no duplication, facade pattern
    exit_gate:   all zRaven green → phase_Bifrost (unless user goal is terminal), 3+ consecutive fails → ask user

phase_Bifrost:
    entry:      auto — phase_CLI exit_gate met, unless user goal is terminal
    a_dogfood:  MVP only — BUILD ON exiting verified zui, do NOT add new logic or events
        _zClass on existing keys only — what renders? what is clickable? what data shows?
        advanced styling / complex navigation come AFTER all green — not now
    b_routes:   fill __hints__ in routes/zServer.routes.zolo — align to zSpark/zUI
    c_zSpark:   update zMode: zBifrost, zServer: {enabled: true}, zSwap: true
    d_zClass:   _zClass on existing zUI keys — no new events — scaffolded zVaF.html, do NOT rewrite
                interactive widgets (calculator, keyboard, board) → _GUI + _zDelegate — NOT JS injection
    e_zRaven:   extend existing zRaven/<name>.zolo for GUI testing — add browser block
    f_run:      z <appname> — fix until browser assertions pass + shots saved
    g_plugins:  as needed for JS logic on existing events only
    h_repeat:   steps e–g for each segment from a_dogfood
    exit_check:  verify global_rules — file sizes ≤600, no duplication, facade pattern
    exit_gate:  all zRaven green → ask user if satisfied, suggest enhancements/next dogfood + Data_Type upgrade (csv→sqlite), 3+ consecutive fails → ask user

bifrost_browser_rule:
    NEVER open zVaF.html directly — it is a server-side template, not a standalone HTML file
    ALWAYS open http://localhost:8080/<route> — z <appname> starts the server, THEN open the URL
    route comes from routes/zServer.routes.zolo — if / is the root route, open http://localhost:8080/
