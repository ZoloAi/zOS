**[← Back to zOpen Guide](../L2_Handling/zOpen_GUIDE.md) | [Home](../../README.md) | [Next: zData Guide →](zData_GUIDE.md)**

---

# zWizard

**zWizard** is the **core loop engine** of **zOS** (Layer 3 — Abstraction).
> See [**zArchitecture**](../../README.md#the-zarchitecture) for full context.

In one sentence: you hand zWizard a block of declared steps, and it runs them in
order, remembers what each one produced, and lets later steps use those earlier
answers — the same declaration whether you're in a terminal or a browser.

You never write the loop, the result-tracking, the templating, or the
"who's allowed to see this" checks. You declare *what should happen*, and zWizard
handles *how* it happens.

---

## What zWizard is in charge of

- **Running a workflow step by step** — a `.zolo` page or any block of keyed
  steps is walked top to bottom.
- **Remembering results** — every step's output is kept so later steps (and your
  code) can read it back by name, by position, or as an attribute.
- **Passing answers forward** — a step can quote an earlier answer inline with
  `{{ zHat.step_name }}`.
- **Branching** — a step can carry an `if:` condition and only run when it's true.
- **Asking permission first** — a step can be gated by role/login, and is quietly
  skipped (or redirected to login) when the viewer isn't allowed.
- **Keeping things all-or-nothing** — steps that touch data can run inside a
  transaction that commits together or rolls back together.
- **Pausing for the human** — menus and prompts stop the flow and wait for input,
  then pick up where they left off.

---

## The behavior to expect

zWizard adapts to *where* it's running, from **one** declaration:

- **In the terminal (zCLI):** steps run **sequentially** — one finishes, the next
  begins, and a prompt or menu blocks until you answer. Linear and immediate.
- **On the web (zBifrost):** the same steps run **progressively in chunks** — the
  page streams out as it's built, and the flow *pauses* at a menu or a gate
  (e.g. a form) and resumes when the browser sends the answer back. Nothing
  blocks the server.

That dual behavior — one source of truth, two runtimes — is the whole point: you
author once and it simply behaves correctly in both places. You should expect the
*same results and ordering*; only the timing (blocking vs. streaming) differs.

A few signals you can return from a step to steer the flow:

| You want to… | The flow… |
|--------------|-----------|
| Go back one step | returns to the previous step |
| Bounce to a specific place | jumps there and continues |
| Stop / exit | ends the workflow cleanly |
| Raise an error | is reported consistently (logged + shown), then handled |

---

## Writing a wizard (the short version)

Declare steps as keyed entries. Each step says what *type* of thing it is and
carries its own fields:

```yaml
get_name:
  type: zDialog
  prompt: "Enter your name:"
  validate: required

greet:
  type: zDisplay
  event: text
  content: "Hello, {{ zHat.get_name }}!"   # reuse an earlier answer
  color: MAIN
```

Run it and read the results three equivalent ways:

```python
zHat = z.wizard.handle(workflow)   # or z.wizard.execute_loop(items)

zHat.get_name        # attribute access
zHat["get_name"]     # key access
zHat[0]              # position access
```

- **Conditions:** add `if:` to a step to make it run only when an earlier answer
  satisfies it.
- **Menus & modifiers:** keys can carry small marker characters that turn a step
  into a menu (`*`), an anchor (`~`), or a crumbs-rewind (`<key>^`) — this is how a
  single page becomes interactive navigation. *(Gating is an **event** — a submit
  button or a dialog — not a marker; the retired `!` gate is gone.)*
- **Access control:** wrap a step with a role/login requirement and it renders
  only for permitted viewers; everyone else is skipped or sent to log in.
- **Transactions:** group data steps so they all succeed or all undo together.

That's the authoring contract. You declare intent; the behavior above is what you
get, in both runtimes, with no extra wiring.

---

## Under the hood

zWizard's execution engine — the sequential/chunked machinery, the result
container, interpolation, conditionals, access-control enforcement, and
transaction handling — is a **sealed ZoloMedia component shipped as part of
zGuard**. It cannot be replicated, forked, or impersonated, and it installs with
every zOS runtime (`z patch`). The open-core repository carries the seam that
connects to it, not the engine itself.

That sealed engine is what lets zOS promise the same behavior everywhere while
staying a single, verifiable product rather than something that can be copy-pasted
into a look-alike.

**For implementation details, integration questions, or commercial use, email
[gal@zolo.media](mailto:gal@zolo.media).**

---

**[← Back to zOpen Guide](../L2_Handling/zOpen_GUIDE.md) | [Home](../../README.md) | [Next: zData Guide →](zData_GUIDE.md)**
