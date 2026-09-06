# zJack — grammar & dual-mode proposal (for Gal's review, gates item id 11)

Status: MVP PROVEN (2026-09-06, Gal approved the baseline to experiment).
The zlag rig's jack raven is green end to end: a button with NO onSuccess
writes a row and the subscribed block repaints twice consecutively — write →
DataOrchestrator broadcast → client scoped re-walk (`zlag/c3`). Grammar as
proposed below; `zJack: true` auto-derive and `every:` heartbeat not yet wired.
Bring-up findings that shaped the implementation:
- Registration lives at the message_walker seam (the only place holding both
  the block dict and its NAME) into the SESSION dict, read LIVE at emit time —
  the orchestrator's constructor session is a boot-time snapshot and zGuard
  installs a fresh session per connection.
- `zos.comm.websocket` is the SYNC server (no browser clients); the Bifrost
  bridge now installs `zos.bifrost_broadcast`, a thread-safe rail onto its own
  loop, at server start — plugin zfuncs run via asyncio.to_thread, where
  `get_running_loop()` raises and the old send_event path silently dropped
  every frame (comm_websocket also now remembers its loop for the same
  reason).
- Client relevance filter: scoped repaint when the target's container is in
  the DOM, unscoped only when the target IS the current walked block,
  otherwise the broadcast frame is ignored — stale subscriptions and
  multi-window pages stay safe.

## What zJack is (one sentence)

A block re-renders itself over the live WS when the data it reads changes —
no user click, no page reload; the missing piece that makes a zolo page feel
alive (board counts tick, a feed grows, a dashboard breathes).

## The rail already exists — zJack is a trigger, not a renderer

The client can already repaint one block in place: `zDeltaScoped` streams a
scoped `execute_walker` into the block's container (and the #19/#23 fixes made
that rail honest). Today the ONLY trigger is a user action's `onSuccess`.
zJack adds the second trigger: the SERVER pushes the same scoped-delta frame
when a write touches what the block reads. New protocol surface is one frame
(`zjack_invalidate` → client re-fires the scoped walk it already knows how to
do); no new render machinery on either side.

## Grammar (proposed)

Declared where the data is declared — on the block, string-first, no plumbing:

```
Feed:
    zJack: true                  # re-render when ANY reel this block reads changes
    zList:
        source: %data.messages
```

Longhand for the two knobs that matter:

```
Feed:
    zJack: {on: [Messages], every: 30s}
```

- `on:` — table list to watch. DEFAULT (and the whole point of `true`): derived
  automatically from the block's zSpool reels — the engine already knows which
  tables each reel reads. `on:` exists only for the rare block that reads
  computed/joined data whose provenance the engine can't see.
- `every:` — optional heartbeat re-render with NO write trigger (clocks,
  external-DB dashboards). Absent = pure write-triggered, zero idle traffic.

NOT proposed: expressions, conditions, or per-row patching. Invalidation is
table-level for 1.7.4 — a write to `Messages` repaints every subscribed block
reading `Messages`, whole-block, via the existing scoped walk. Row-level diffing
is a 2.x optimization behind the same grammar (declared intent doesn't change).

## Dual zCLI / zBifrost contract (the part that needs your ruling)

### Verified baseline first (zlag rig, zRaven.cli 8/8, 2026-09-06)

Gal asked what zCLI does TODAY when a plugin-action zBtn's `onSuccess:
zDelta($Main)` should repaint content printed ABOVE the button. Pinned on the
rig: the zfunc runs, the onSuccess is **silently dropped**, and the walk
**continues from the button** to its next sibling — no in-place rewrite, no
appended re-print. (The sequential executor's zDelta handling serves
`action: zDelta(...)` nav buttons only.) So onSuccess repaints are
Bifrost-only today; any zCLI liveness is NEW behavior, not parity restoration.

### Why `\r` can't do it

`\r` returns to the start of the CURRENT line only. Content printed before the
button is scrollback — reaching it needs CSI cursor-up (`ESC[nA`) with exact
line accounting (wrapped lines, terminal width, the prompt itself). The
codebase already refuses in-place escapes beyond the single parked progress
bar, deliberately: terminals that don't honor CSI render literal `[1A[2K`
garbage (documented in `timebased_progress.py` and the wizard bar in
`zengine.py`). One live same-line bar while the walker is parked is the safe
ceiling of that trick.

### The honest zCLI options

- **A — inert**: parsed, validated by zLSP/z lint, ignored at render, exactly
  like `_zClass`. The zCLI proof of a zJack'd block is that it renders at all;
  liveness is Bifrost-skin behavior. Zero risk, zero work.
- **B — append re-print**: when an invalidation lands while the walker is
  parked at a prompt, print a marked refresh BELOW (`⟳ Feed (updated)` + the
  block's fresh paint), then re-issue the prompt line. Transcript-honest, no
  cursor magic, works on every terminal — the "log lines land above the
  prompt" pattern. Cost: the CLI walker must accept prints while blocked on
  stdin (a listener thread), which is real machinery.
- **C — alt-screen (curses) runner**: a genuinely live terminal UI. A different
  runner entirely; out of alpha scope, noted only so it's consciously deferred.

Recommendation: **ship 1.7.4 with A**, and spec B as the named zCLI story for
1.7.5 — it's the same server-side invalidation feed, so nothing in the 1.7.4
engine work is throwaway; B is purely a CLI-renderer consumer of it later.

- **zRaven**: Bifrost mode gets a genuine test shape — step A writes a row
  through a plugin, step B `zWait`s for the block to show it WITHOUT any click
  between them. That wait-without-click is the pin that zJack works. The zCLI
  baseline probe (zlag `zRaven.cli.zolo`) stays as the tripwire: it goes red
  the day zCLI gains a repaint story, on purpose.

## Scope guards (alpha-sized on purpose)

- Per-connection subscriptions, only for blocks on the CURRENTLY rendered page.
- Invalidation hooks into the zData write doors we just unified (#13/#15) —
  every write already passes one chokepoint, so the hook is one emit, not a
  scattering of triggers.
- Coalescing: writes within one action collapse to one repaint frame; a
  heartbeat and a write in the same tick collapse to one.
- No cross-user fanout logic in 1.7.4 beyond "same table → all subscribed
  connections" (that IS the multi-user chat/board case, and it's enough).

## Relationship to #12 (no white flash)

Different verbs, same rail: #12 fixes NAVIGATION repaints (zLink swaps the
panel, not the document — no full-page reload), zJack fixes DATA repaints
(no user action at all). They share the scoped-render client machinery; zJack
does not subsume #12 and neither blocks the other.

## The three decisions for Gal

1. **The word and its home**: `zJack: true | {on:, every:}` as a BLOCK key
   (sibling of the event, like `_zClass` / `if:`) — approve, or prefer it on
   the root zMeta (`zJack: [BlockA, BlockB]`, file-wide)? Block-level is my
   recommendation: liveness is a property of a block, and it travels with the
   block when a zPattern reuses it.
2. **Table-level invalidation for 1.7.4** (whole-block repaint on any write to
   a watched table) — approve as the alpha cut, row-level diffing deferred?
3. **zCLI story**: A now, B (append re-print below the prompt) specced for
   1.7.5 — approve, or pull B into 1.7.4? (B needs the CLI walker to accept
   prints while parked on stdin; `\r`/cursor-up rewriting of earlier rows is
   ruled out — see the dual-mode section for the verified baseline and why.)

Answer these three and #11 starts: engine hook at the write chokepoint, one
protocol frame, client subscription + re-fire, `z raven` pin in a rig, then a
golden-demo showcase (zPoll's results page is the natural first zJack'd block).
