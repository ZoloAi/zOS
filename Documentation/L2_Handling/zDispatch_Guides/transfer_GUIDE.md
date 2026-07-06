**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**

---

# Transfer (zTransfer / zExport / zImport)

The **transfer** module is zDispatch's **single source of truth for moving data
in and out of zOS**. Every I/O grammar — `zTransfer`, `zExport`, `zImport`,
upload, download — is one shape:

```
source ──(read)──▶ payload ──(codec bridge)──▶ target ──(write)──▶ result
```

A *source* produces a payload, an optional *codec* bridges its nature, and a
*target* consumes it. The engine is deliberately decoupled from zData and zComm —
it only reaches them through the `model` and `storage` adapters, so any subsystem
can reuse it.

## Overview

| Module | Class / role | Purpose |
|--------|--------------|---------|
| `transfer_engine.py` | `TransferEngine` | Orchestrates source → (codec) → target; the SSOT primitive |
| `transfer_adapters.py` | `*Adapter` + `ADAPTER_REGISTRY` | Backend-agnostic endpoints |
| `transfer_codec.py` | `decode` / `encode` | Format boundary (csv/tsv/json/txt) between blob ⇄ rows |
| `transfer_payload.py` | `TransferPayload` | The unit that flows source → target (rows or blob nature) |
| `transfer_paths.py` | `resolve_file_path` / `resolve_output_dir` | Path / output-dir resolution for file endpoints |
| `transfer_handler.py` | `TransferHandler` | Dispatch entry point for the `zTransfer` grammar |

The grammars route to the same engine:

| Grammar | Entry point | Builds spec |
|---------|-------------|-------------|
| `zTransfer` | `transfer/transfer_handler.TransferHandler` | author the `source`/`target` directly |
| `zExport` | `handlers/handler_export.ExportHandler` | `model`\|`inline` source → `response` target (encode) |
| `zImport` | `handlers/handler_import.ImportHandler` | `file` source → `model` target (decode) |

`zExport`/`zImport` are **thin sugar** that build a spec and delegate; `zTransfer`
is the direct grammar.

---

## Payload natures

A `TransferPayload` carries data in **one of two natures**:

- **`rows`** — `List[Dict]` (tabular: model rows, parsed csv/json)
- **`blob`** — `bytes` / `text` (opaque: files, images, encoded text)

The codec is inserted **only when source and target natures disagree**. When both
ends are blob-nature (e.g. storage → response for an image), bytes pass straight
through and never touch the codec.

`payload.meta` carries side-band info (filename, mime type, source key/path).

---

## Adapters (`ADAPTER_REGISTRY`)

Each endpoint kind is an adapter that can act as a **source** (`read`) and/or a
**target** (`write`). A target declares `WANTS` — the nature it consumes — so the
engine knows whether to bridge.

| Kind | Source (`from`) | Target (`to`) |
|------|-----------------|---------------|
| `file` | read file bytes/text from a zPath | write text to a file |
| `model` | silent zData read → rows | insert rows via zData (`append`/`replace`) |
| `storage` | read object from zComm storage | write object to zComm storage |
| `bytes` | inline `data:` bytes/str | — |
| `inline` | inline `content:` (any) | — |
| `response` | — | CLI: write to `@.Data/exports/…`; Bifrost: push a download event |

---

## zTransfer (the explicit grammar)

A transfer spec is a plain zUI dict — file-type agnostic:

```yaml
zTransfer:
    format:  csv            # codec format when natures differ (default: csv)
    mode:    append         # model target write mode (append | replace)
    source:  {from: file,  path: @.Data.imports.contacts.csv}
    target:  {to:   model, model: @.models.zSchema.crm.contacts}
```

`TransferEngine.run(spec, context, walker)` returns a structured result dict
(`{"success": bool, ...}`). It validates that `source` and `target` are dicts,
resolves the adapters from `from`/`to`, reads → bridges → writes, and converts
any exception into `{"success": False, "error": ...}` (fails closed, never raises
to the dispatch loop).

---

## zImport (file → model sugar)

```yaml
^Import_Contacts:
    zImport:
        format:  csv
        source:  @.Data.imports.contacts_import.csv
        target:  @.models.zSchema.crm.contacts
        mode:    append          # append (default) | replace
```

`zImport` builds `{source: {from: file}, target: {to: model}}`, runs the engine,
then renders a mode-correct result message (row count on success, error on
failure). It also substitutes `zConv.<key>` tokens in `source` from the dialog
context, so it composes with a `zDialog.onSubmit`:

```yaml
^Import_Contacts:
    zDialog:
        title:  Import Contacts
        fields: [filename]
        onSubmit:
            zImport:
                format:  csv
                source:  @.Data.imports.zConv.filename
                target:  @.models.zSchema.crm.contacts
```

---

## zExport (model|inline → response sugar)

```yaml
^Export_Contacts:
    zExport:
        format:   csv
        filename: contacts_export      # no extension — added by the handler
        zData:                          # silent read = the data source
            action:  read
            model:   @.models.zSchema.crm.contacts
            columns: [id, name, email, phone, company, status]
```

Raw-content variant (no `zData` sub-block):

```yaml
^Export_Note:
    zExport:
        format:   txt
        filename: my_note
        content:  Some plain text to export.
```

`zExport` delivers mode-correctly via the `response` target:
- **zCLI** → writes `@.Data/exports/{filename}.{format}` and prints the path
- **zBifrost** → pushes a download event over WebSocket

---

## Codec (format boundary)

`transfer_codec` is the only place that knows how the row formats serialize, so
adapters stay format-agnostic:

| Direction | Call | Formats |
|-----------|------|---------|
| import | `decode(raw, fmt)` → rows | `csv`, `tsv`, `json` |
| export | `encode(rows, content, fmt)` → text | `csv`, `tsv`, `txt`, `json` |

> **Security note:** the codec uses only `csv.DictReader` and `json.loads` —
> there is **no** `pickle`/`eval`/code-bearing deserialization. Unsupported
> formats raise `TransferCodecError`. Binary payloads bypass the codec entirely.

---

## Design notes

- **SSOT I/O primitive.** `zExport`/`zImport`/upload/download are all sugar; the
  engine is the only place that performs the read→bridge→write. New grammars add
  a handler that builds a spec, never new I/O logic.
- **Backend-agnostic.** The engine never imports zData or zComm directly — only
  the `model`/`storage` adapters do, keeping the engine reusable and testable.
- **Fail-closed result contract.** Every path returns `{"success": ...}`; errors
  are captured, logged, and returned — they do not propagate into dispatch.

---

**[← Back to zDispatch Guide](../zDispatch_GUIDE.md)**
