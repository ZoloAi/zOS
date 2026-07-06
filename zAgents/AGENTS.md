# zOS — Agent Instructions (zAgents v2)

> Canonical authoring guide for zolo apps. Do not edit per-project — source lives in zCloud.

---

## syntax

```zolo
parser:   string-first — NOT YAML, NOT JSON
strings:  never quote — the parser handles everything
  exception: value starts with [ or contains leading : with no context
arrays:   inline [a, b, c] only — never dash lists
booleans: true / false / null (lowercase only)
zlsp:
  error:   zFunc line with outer quotes
  warning: any other needlessly quoted key

    comments:
        whole-line:  # comment on its own line — stripped at parse time
        inline:      key: value  #> stripped comment <#
        CRITICAL:    bare # mid-line IS NOT stripped — it becomes part of the value string
                     key: zBack  # nav    →  value is "zBack  # nav"    ← WRONG
                     key: zBack  #> nav <#  →  value is "zBack"         ← RIGHT
    zCapture_patterns:
        write patterns WITHOUT backslash sequences — use . and character classes
        TRAP: "row .([0-9]+)." does NOT match "(row 6)":
              leading . consumes the digit, leaving ) for capture group → NO MATCH
        RIGHT: "table contacts .row ([0-9]+)." anchors to main table, matches "(row 6)"
        use:  [0-9]+ not \d+,  [a-z]+ not \w+,  [ \t]+ not \s+
```

```zui
# ✅ correct
label: Hello World
zFunc: &plugin.fn(zHat[Step])
fields: [name, email]

# ❌ wrong — quotes are noise and break zFunc
label: "Hello World"
zFunc: "&plugin.fn(zHat[Step])"
```

---

## mode_detection

```zolo
check: target folder only — not the workspace
navigator:
  trigger: zSpark.*.zolo exists in target folder
  rule:    read it, surgical edits only, match existing style
author:
  trigger: new or empty folder
  rule:    use Phase_CLI workflow below
```

---

## workflow

Two hard-gated phases. CLI is internal scaffolding — the default deliverable is always a GUI.

### Phase_CLI

```zolo
entry:     always
exit_gate: [zRaven_all_green, real_csv_data, no_mocks, no_plugin_crud]
wall:      focus on CLI only — do NOT write templates, selectors, or browser tests yet
on_exit:   auto-proceed to Phase_Bifrost — do NOT stop, do NOT ask for confirmation
default:   unless user explicitly says "CLI only" or "terminal only", GUI is the target
```

**Step 0 — scaffold the app structure**

```zolo
command: zolo scaffold <appname> [--title "App Title"]
rule:    ALWAYS run this first — never write zSpark/routes/zVaF.html by hand
output:  confirmed files: zSpark, routes/zServer.routes.zolo, templates/zVaF.html,
         UI stub, models stub, zRaven stub, Data/, plugins/, static/
trust:   copy scaffold output EXACTLY — never rename generated keys, never rewrite routes or zVaF.html
         only fill in: zSpark title/zVaFile/zBlock values, routes zVaFile/title values, zUI content
routes:  ONE file only — routes/zServer.routes.zolo — never create a .yaml alongside it
zBlock:  use the scaffold-generated block name verbatim (e.g. Crm_Menu) in zSpark AND routes AND zUI root key
```

**Step 1 — design the mechanism (no files yet)**

```zolo
do:     prove one function in pure Python
verify: python3 -c "from plugins.myapp import fn; print(fn('arg'))"
gate:   can describe return value as concrete dict/list/scalar
do_not: create additional files, plan menus, design multiple flows at once
```

**Steps 2–N — one flow, one proof, repeat**

```zolo
intent_lookup:  # STOP — check this before writing ANY UI flow
  insert:  zDialog + model: + fields: + onSubmit: zData: action: insert, table: t, data: {field: zConv.field}
  read:    zData: action: read, model: → auto-renders via zTable (no wiring, no zHat source)
  delete:  zDialog + model: + fields: [id] + onSubmit: zData: action: delete, model:, where: id = zConv.id
  update:  zDialog + onSubmit: zData: action: update, where:
  custom:  zFunc: &plugin.fn(...) — only when no native event covers the need

zWizard_gate:   zWizard is for multi-step input flows ONLY — never for data ops
                before writing zWizard: confirm it is NOT an insert/read/delete/update → use intent_lookup
zPlugin_needed: only when zFunc appears in zUI — skip for pure zDialog/zData apps
zTable_rule:    pure renderer — never a data source — source: zHat[...] does NOT exist
```

```zolo
iteration:
  1: write models/zSchema.<app>.zolo (Data_Type: csv)
  2: write zSpark.*.zolo (zMode: zCLI, zRaven: <flow_name>)
  3: write zUI — one flow only, no zMenu, no second zWizard
  4: write zRaven/zRaven.<name>.zolo — one-to-one with zUI:
       zInput/zDialog step: zAssert: contains: <prompt text>
       display step:        zAssert: contains: <result text>
       zData step:          zAssert: success: true
  5: run: cd app && printf "input\n" | z <sparkname>
       on_fail: STOP — fix this step only — do not write next step
       on_pass: confirm [zRaven] All tests passed
  6: add next flow → repeat from 3
```

**Menu-first, develop-one rule**

```zolo
declare:   all keys as stubs upfront
implement: one key at a time
gate:      zRaven pass required before implementing next key
violation: writing key N+1 before key N passes
zMenu:     always last — navigation over flows that already work independently
```

```zui
# ✅ correct — declare all stubs, implement one
~Client_Actions*: [^Add_Client, ^List_Clients, ^Remove_Client]
^Add_Client:
    zDialog:         # fully implemented
        ...
^List_Clients:       # stub — implement after Add_Client zRaven passes
^Remove_Client:      # stub
```

**Self-test**

```zolo
cmd:       cd path/to/app && printf "input1\ninput2\n" | z <sparkname>
sparkname: * in zSpark.*.zolo → zSpark.crm.zolo = z crm
menu_pick: 0-indexed
zInput:    one line per prompt
zBtn:      y or n
on_error:  fix ERROR: lines in stdout, re-run
docs:      zCloud/UI/zProducts/zOS/Concepts/zUI.zFundamentals.zolo
do_not:    [z zApp (runs zCloud), dig into zOS Python source]
```

---

### Phase_Bifrost

```zolo
entry:     Phase_CLI exit_gate satisfied — no confirmation needed, proceed immediately
rationale: zCLI is a debug/build tool for the agent — no user ships a terminal app
do_not:    change zUI logic / plugin functions / zSchema during this phase
```

```zolo
1_flip:    set zMode: zBifrost + zServer: {enabled: true} in zSpark
2_routes:  write routes/zServer.routes.yaml — wires / to the walker (must be .yaml, server ignores .zolo)
3_dress:   write templates/zVaF.html — layout/CSS only, no logic
4_verify:  run z <app> — confirm all flows render at http://127.0.0.1:8080
5_zraven:  write browser block — zClick each flow, zWait result, zShot
6_confirm: all browser assertions pass
7_last:    swap Data_Type: csv → sqlite or postgres
```

Routes file template:

```yaml
# routes/zServer.routes.yaml
meta:
  default_route: /
  zNavBar: false

routes:
  /:
    type:                zWalker
    zVaFolder:           "@.UI"
    zVaFile:             "zUI.<appname>"
    zBlock:              "<BlockName>"
    auto_discover_blocks: true
    context:
      title: <App Title>
```

**Bifrost selectors** — confirmed from live zRaven screenshots:

```zolo
zMenu button:   button:has-text('Label')      # NOT [data-key=...] — that attr does not exist in DOM
zDialog input:  input[name="fieldname"]
zDialog submit: button[type="submit"]
zDialog form:   [data-dialog-id]
wait_rule:      always zWait after submit before asserting or taking a screenshot
zShot_folder:   shots save to zRaven/zShots/<raven-name>/<step>.png automatically
```

**`zBoot.url` rule** — the URL must target the app's specific route, not `/`:

```zolo
wrong: url: http://127.0.0.1:8080            # loads homepage (zVaF), not your app
right: url: http://127.0.0.1:8080/<app-route> # e.g. /crm  or  /zProducts/zOS/Events/zNavigation
route_source: auto-discovered from directory structure — UI/zProducts/zOS/.../zUI.Name.zolo → /zProducts/zOS/.../Name
```

**WS block required before browser block** — the WS connection keeps the server session alive while Playwright runs. Without it the server exits before the browser can connect.

```zraven
# MANDATORY structure for any Bifrost zRaven file
App_Boot:                              # ← WS block FIRST (no explicit zBoot needed — auto-injected from spark)
    Warmup:
        zAssert:
            result: completed         # minimal WS step to establish the session

Browser_Tests:                        # ← browser block SECOND
    Open:
        zBoot:
            url: http://127.0.0.1:8080/<app-route>
    Click_Add:
        zClick:
            selector: "button:has-text('Add')"
    Type_Name:
        zType:
            selector: input[name="name"]
            value:    Alice Berg
    Submit:
        zClick:
            selector: button[type="submit"]
    Wait_Back:
        zWait:
            selector: "button:has-text('Add')"
            state:    visible
            timeout:  8000
    Shot:
        zShot: add_result
```

---

## zSchema

```zolo
start_with:  Data_Type: csv — always, no exceptions until final ship step
progression: csv (full dev) → sqlite (last step, local) → postgres (production only)
Data_Path:   @.Data             # canonical — directory only, dot notation, no filename, no extension
             zOS derives: @.Data/<table>.csv automatically from the table key name
Data_Source: MY_ENV_VAR         # production only — env var holding connection string
zPath_rule:  always dot notation — never / slashes, never append filename or extension to Data_Path
reference:   zCloud/models/ — for real examples
```

```zschema
# models/zSchema.<appname>.zolo
zMeta:
    Data_Type:     csv
    Data_Path:     @.Data
    Data_Label:    <table>
    Data_Paradigm: classical
    Schema_Name:   zSchema.<appname>

<table>:
    id:    {type: int, pk: true, auto_increment: true}
    name:  {type: str, required: true}
    email: {type: str, required: true}
```

---

## zSpark

```zspark
required:
    title:     app name
    zMode:     zCLI | zBifrost
    zVaFolder: @.UI
    zVaFile:   zUI.MyApp  # no extension
    zBlock:    root-level key in zUI file (zVaF for single-block apps)
optional:
    zScrap:    INFO | DEBUG | WARNING | ERROR
    zState:    DEVELOPMENT | PRODUCTION
    zSwap:     true = live reload
    zLogPath:  @.logs
    zRaven:    <name> — auto-runs zRaven/zRaven.<name>.zolo on EVERY z <spark> invocation
zRaven_behavior:
    zCLI:       spawns z <spark> subprocess, drives stdin, reads stdout, then exits + signals done
    zBifrost:   connects via WebSocket to running Bifrost session, then exits + signals done
    on_finish:  process exits cleanly — do NOT expect the app to stay running after zRaven
    manual_run: to run app without zRaven, comment out zRaven: line in zSpark
deprecated: zRaven: true — use name string
```

---

## zUI

```zolo
root_rule:     root level = zBlock names + zMeta only — no events at root
do_not_invent: event key names
events:
    dispatch: [zFunc, zWizard, zData, zDialog]
    display:  [zText, zMD, zH1-zH6, zTable, zURL, zCrumbs, zTerminal]
    io:       [zInput, zCheckbox, zBtn]
    config:   [zMeta]
```

```zui
zMeta:            # optional page config
    zNavBar: true
zVaF:             # ← zBlock — zSpark.zBlock points here
    Section:      # ← zKey (container)
        zWizard:  # ← zEvent
            ...
```

**Navigation**

```zolo
~Name*:
    meaning:     named menu — renders options from inline list, anchored
    naming_rule: name after contents — not generically
    good:        [~CRM_Actions*, ~Stock_Options*, ~Admin_Panel*]
    bad:         [~menu*, ~nav*, ~options*]
^Key:
    meaning: bounce — run key, return to parent menu after
    rule:    prefix every flow key under a menu with ^
```

**zWizard + zHat**

```zolo
zHat[StepName]: works in any string property — content/prompt/label/href
if_placement:   step-level sibling inside zWizard only
if_syntax:      [zHat[Step], not zHat[Step], zHat[A] and zHat[B] == 'done']
```

```zui
Flow:
    zWizard:
        Step_One:
            zInput:
                prompt: Enter value:
        Step_Two:
            zFunc: &plugin.fn(zHat[Step_One])
        Step_Three:
            zText:
                content: Result: zHat[Step_Two]
```

**zDialog — the insert entry point**

```zolo
role:      every insert flow uses zDialog — not chains of zInput
model:     @.models.zSchema.<app>.<table> — enables validation + direct insert
zConv:     form field value inside onSubmit only — all strings
zHat:      wizard step result — do not mix with zConv
reference: zCloud/UI/zProducts/zOS/Events/zUI.zData.zolo
```

```zui
Form:
    zDialog:
        fields: [name, email]
        model:  @.models.zSchema.crm.clients
        onSubmit:
            zData:
                action: insert
                table:  clients
                data:
                    name:  zConv.name
                    email: zConv.email
```

**zData — declarative read / update / delete**

```zolo
role:        read/update/delete — together with zDialog covers full CRUD declaratively
syntax:      string syntax only — not dict
operators:   [>, <, =, >=, <=, zAND, zOR, zNOT, "zIN (v1, v2)", "zBETWEEN v1 zAND v2", "zLIKE %pat%"]
reference:   zCloud/UI/zProducts/zOS/Events/zUI.zData.zolo — read before writing any zData block
do_not_read: zOS/Documentation/zData_GUIDE.md
```

```zui
Load_Contacts:
    zData:
        action:   read
        table:    contacts
        zFilters: active = true zAND score > 80
Show_Contacts:
    zTable:
        source:  zHat[Load_Contacts]
        columns: [id, name, email]
```

**Presentation gate**

```zolo
rule:   do NOT add _zClass, _zStyle, _zDelegate, _id until zCLI flow passes
reason: _zClass is CSS-only — no effect in terminal mode
```

---

## plugins

```zolo
rule:   plain types in, plain types out — plugins must not know about zolo
state:  travels through zHat — never Python module-level variables
@zfunc:
    use:     last resort — only when function needs zos.display for complex rendering
    do_not:  use for data operations — those belong in zData blocks in zUI
bad:
    - plugin imports zolo
    - plugin owns while True loop or calls input()
    - plugin calls print() for display    # all display through zEvents
    - _contacts = [] module-level storage  # Phase A mock only — never into zUI
    - zFunc: &plugin.create(...) for CRUD  # use zDialog/zData
return_shapes:
    str/scalar: zText: content: zHat[Step]
    dict:       zText: content: zHat[Step].field
    list[dict]: zTable with source: zHat[Step]
    list[str]:  zText: content: zHat[Step]
never: format return as display string — return raw data, let zEvents render
```

---

## zRaven

```zolo
location:  zRaven/zRaven.<name>.zolo relative to zSpark
structure:
    root_key:   test block name
    nested_key: test step
    each_step:  one primitive + optional zAssert sibling
engine_injects: [--ws, --http, --vaFolder, --vaFile, --block] — do NOT add to file
mode_detection:
    CLI_block:     zMenu/zPick/zSubmit/zMarker → CLIRunner
    WS_block:      zExecute/zSubmit/zBoot.zVaFile → WebSocket
    browser_block: zBoot.url/zType/zClick/zWait → Playwright
order:     WS blocks run first, browser blocks run after
```

**CLI primitives**

```zraven
Menu_Step:
    zMenu:
        zPick: New_Contact           # menu key name without ^
^New_Contact:
    zWizard:
        Enter_Name:
            zAssert:
                contains: Full name  # assert prompt rendered
            zSubmit: Eve Nakamura    # send to stdin
        Do_Create:
            zAssert:
                success: true        # no ERROR: in stdout
        Show_Result:
            zAssert:
                contains: Created
        End:
            zMarker: done            # closes stdin — subprocess exits at ^ bounce
```

```zolo
zMarker:
    placement:  last step of the flow being tested
    next_flow:  change zPick + move zMarker to last step of that flow
one_to_one:     every zWizard gate in zUI → one zSubmit in zRaven, same key names
seed_rule:      wrap seed steps in zWizard: even if zUI uses zDialog — tells runner to recurse
run_direct: |
    python3 zOS/zRaven/zraven.py <AppDir>/zRaven/zRaven.<name>.zolo \
        --mode cli --spark <name> --appdir <AppDir>
```

**WS primitives**

```zraven
Boot_Step:
    zBoot:
        zVaFile:   zUI.myapp
        zVaFolder: @.UI
        zBlock:    MyBlock
Func_Step:
    zExecute:
        fn: "&myplugin.my_function('arg')"
Gate_Step:
    zSubmit:
        gate:  GateKey
        value: some_value
```

**Browser primitives**

```zraven
Open_Step:
    zBoot:
        url: http://127.0.0.1:8080/<app-route>   # must be app-specific path, not /
Type_Step:
    zType:
        selector: "#my-input"
        value:    hello
Click_Step:
    zClick:
        selector: "#my-button"
Wait_Step:
    zWait:
        selector: "#my-element"
        state:    visible         # visible | hidden | attached | detached | enabled
        timeout:  5000
Shot_Step:
    zShot: true                   # shorthand — saves to zRaven/zShots/<raven-name>/<step>.png
Drag_Step:
    zDrag:
        selector: "#main-canvas"
        from: {x: 100, y: 100}
        to:   {x: 300, y: 200}
```

**Assertions**

```zraven
Step:
    zExecute:
        fn: "&plugin.get_data()"
    zAssert:
        success:  true
        event:    completed
        contains: some_string
        json:
            field: status
            eq:    playing
            gte:   0
            lte:   6
            in:    [a, b, c]
        dom:
            selector: "#el"
            property: disabled    # disabled | text | innerText | any HTML attribute
            eq:       false
            count:    6
        style:
            selector: "#Drawing"
            property: background-image
            contains: gradient
```

**Failure map**

```zolo
Timeout_Ns on zWait(enabled):     input never re-enabled → client-side JS bug
result is not valid JSON:          plugin returned plain string → remove json: assert
expected event=completed got None: wrong block/file name → check zVaFile/zBlock spelling
DOM assert error:                  selector not found → check element IDs in template HTML
update_discipline:                 update zRaven.*.zolo to cover new UI elements before closing task
```

---

## naming

```zolo
app_folders:   PascalCase — ConnectFour, BalloonSort
spark_ui:      zSpark.appname.zolo / zUI.appname.zolo
zBlock:        zVaF for single-block apps, descriptive name for multi-block
plugins:       appname.py
zRaven_blocks: PascalCase or Snake_Case — App_Boot, Browser_Interaction
zVaFolder:     @.UI — no quotes needed, parser is string-first
```
