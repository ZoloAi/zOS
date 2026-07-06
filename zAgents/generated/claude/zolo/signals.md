zSignals: feedback events — tell the user HOW it went | one message, built-in meaning + colour | coloured line in zCLI, dismissible card/toast in zBifrost | the SSOT forms + dialogs reuse

pick_one:
    zSuccess — it worked          (green)
    zError   — it failed          (red)
    zWarning — proceed with care  (yellow)
    zInfo    — for your info       (cyan)
    zPrimary / zSecondary — brand emphasis, NO status meaning (use sparingly — emphasis, not feedback)
    rule: a real outcome? -> success/error/warning/info | just drawing the eye? -> primary/secondary

shorthand: the quick way — message as a plain string
    zSuccess: Record saved.     — the string IS the content; colour comes from which event you picked
    rule: reach for shorthand for a one-off line; switch to content: when it needs flush or more

zSignal: the longhand — choose the mood at runtime, not by key
    zSignal: { type, content, flush }
    type:    success | error | warning | info | primary | secondary — picks the mood when your DATA decides it
    rule: same render as the shorthands — zSuccess == zSignal type: success

props:
    content — the message shown — required (string)
    type    — which mood (zSignal longhand only)
    flush   — true -> pops as a timed top-right TOAST, slides away (click × to close); Bifrost-only, terminal keeps the line

fires:
    on load   — a signal in the chunk shows when the chunk renders
    on action — tuck one in a button's `action:` -> fires on click (the feedback a form/dialog raises when it acts)
    rule: action takes ONE event — a shorthand (zSuccess) or the zSignal longhand

canonical_classes: written by Bifrost (zbase theme) — override = restyle EVERY signal, never add by hand
    .zSignal             — the card (base)
    .zSignal-success | -error | -warning | -info | -primary | -secondary — the mood tint
    rule: zCLI renders the same meaning as a coloured line; flush is ignored there

seek_as_need: !needed to raise a signal — meet them again where feedback is raised
    forms submit / dialogs act -> that feedback IS a signal, reused -> Forms ref
