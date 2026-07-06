# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/binding_ops.py
"""zLoom BINDING ops — the named-read registry + binding assembly.

Turns a block's declared bindings (a literal ``_data`` block and/or
``zMeta.zLoom: [name]`` references) into ONE query map consumed by QueryOps.
Owns the ``zLoom/`` folder registry (SSOT for named reads). Mixed into the
``zLoom`` facade. Shared by CLI (zDash panels) and Bifrost (zWizard).
"""

from zOS import Any, Dict
# zPath grammar — Layer-0 SSOT for sigil/segment decomposition.
from zSys import zpath


class BindingOps:
    """Binding-assembly + registry methods for zLoom (expects ``self.zos``)."""

    zos: Any

    def has_bindings(self, block: Dict[str, Any]) -> bool:
        """True if a block declares any binding: a literal ``_data`` block and/or
        a ``zMeta.zSpool`` reference into the zSpool registry (zLoom/spools/)."""
        if not isinstance(block, dict):
            return False
        if isinstance(block.get("_data"), dict):
            return True
        zmeta = block.get("zMeta")
        return bool(isinstance(zmeta, dict) and zmeta.get("zSpool"))

    def prepare_block_render(self, zfile_parsed: Dict[str, Any], block: Dict[str, Any],
                             context: Any = None) -> Any:
        """SSOT pre-render seam — bind + resolve + loop-expand a landed block.

        ONE place every render entry funnels through so a leaf renders identically
        however it is reached — navigated to (navigation_linking), booted directly
        into (zWalker.run), or served over a route (route_dispatcher). Steps:

          1. build the file-root ``zMeta.zSpool`` + ``_data`` binding (the root is the
             binding site; the extracted block drops the root zMeta),
          2. merge the landed block's own literal ``_data`` (block scope),
          3. resolve → ``%data.*`` (stashed in session["_current_block_data"]),
          4. expand any ``zList``/``zShuttle`` in the block into concrete per-row
             blocks (``%item.*`` bound, per-row ``zGate`` filtered) BEFORE dispatch.

        Returns the block_context (``{"_resolved_data": {...}}``) or the passed
        ``context`` unchanged when the block declares no binding. Fails soft — a
        binding/resolve error logs and yields the context (empty render), never raises.
        """
        binding = self.build_binding_block(zfile_parsed)
        literal = block.get("_data") if isinstance(block, dict) else None
        if isinstance(literal, dict):
            binding.update(literal)
        if not binding:
            return context
        block_context = context if isinstance(context, dict) else {}
        try:
            # resolve_block_data (QueryOps) + expand_list_bindings (LoopOps) are
            # sibling mixins composed into the zLoom facade at runtime.
            resolved = self.resolve_block_data(binding, block_context)  # pylint: disable=no-member
            if resolved:
                block_context["_resolved_data"] = resolved
                self.zos.session["_current_block_data"] = resolved
                self.zos.logger.framework.debug(
                    f"[zLoom] prepare_block_render bound: {list(resolved.keys())}")
                # SSOT loop expansion — same structural engine the zDash panel path
                # uses, so a plain leaf and a dashboard weave lists identically.
                self.expand_list_bindings(block, resolved)  # pylint: disable=no-member
                # SSOT knot collapse — after loops (loop-scoped knots already baked
                # per-row by LoopOps), finish any page-scoped zKnot value-dict.
                self.expand_knots(block, block_context)  # pylint: disable=no-member
        except Exception as exc:  # pylint: disable=broad-except
            self.zos.logger.framework.warning(f"[zLoom] prepare_block_render failed: {exc}")
        return block_context

    def build_binding_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Merge a block's ``_data`` literals + ``zMeta.zSpool`` refs into one query
        map (the shape ``resolve_block_data`` consumes), so literal reads and
        spool refs share one resolution path. (Route gates bridge their route-level
        ``zLoom`` field into this same ``zSpool`` key — see route_dispatcher.)"""
        merged: Dict[str, Any] = {}
        if not isinstance(block, dict):
            return merged

        literal = block.get("_data")
        if isinstance(literal, dict):
            merged.update(literal)

        zmeta = block.get("zMeta")
        zspool = zmeta.get("zSpool") if isinstance(zmeta, dict) else None
        if zspool:
            registry = self.load_zloom_registry()
            names = zspool if isinstance(zspool, (list, tuple)) else [zspool]
            for name in names:
                if not isinstance(name, str):
                    continue
                # Style B — full zPath reference (@.zLoom.spools.zUI.account.current_user):
                # resolve the def straight from its file, keyed by the path tail.
                if name.startswith(zpath.SIGIL_WORKSPACE):
                    resolved = self._resolve_zloom_zpath(name)
                    if resolved is not None:
                        key, val = resolved
                        merged[key] = val
                    continue
                # Style A — short alias (registry key = the read's top-level name).
                if name in registry:
                    merged[name] = registry[name]
                else:
                    self.zos.logger.framework.warning(
                        f"[zLoom] Unknown spool '{name}' (not in zLoom/spools/)"
                    )

        return merged

    # zVaFile type-prefix that starts a zLoom artifact filename (spools + patterns
    # are both authored as zUI.* files — see the zUI-prefix decision). Used to split
    # a Style-B ref into its DIRECTORY path vs its dotted FILENAME, so reads can nest
    # under zLoom/spools/ without the ref grammar guessing where the folder ends.
    _ZVAFILE_PREFIXES = ("zUI",)

    def _resolve_zloom_zpath(self, ref: str):
        """Resolve a Style-B zLoom ref (``@.<dir…>.<zUI.file>.<spool>``) → (key, def).

        The ref carries its folder path explicitly, e.g.
        ``@.zLoom.spools.zUI.public.public_user`` → dir ``zLoom/spools``, file
        ``zUI.public``, spool ``public_user``. We split at the ``zUI`` segment: every
        segment BEFORE it is a real directory (path-joined), the ``zUI.<name>`` pair
        is the dotted filename, and the tail is the spool key. Any miss → None so a
        bad ref degrades to "no data" (gate 404 / empty render) rather than raising.
        """
        import os
        try:
            segs = ref[2:].split(".")
            # Find where the filename starts (the zVaFile type-prefix segment).
            idx = next((i for i, s in enumerate(segs) if s in self._ZVAFILE_PREFIXES), None)
            if idx is None or idx + 2 >= len(segs):
                return None
            dir_segs = segs[:idx]                 # e.g. [zLoom, spools]
            filename = ".".join(segs[idx:idx + 2])  # e.g. zUI.public
            key = ".".join(segs[idx + 2:])          # e.g. public_user (spool name)
            base = (self.zos.session.get("zSpace") if hasattr(self.zos, "session") else None) or os.getcwd()
            fbase = os.path.join(base, *dir_segs, filename)
            fpath = next((fbase + ext for ext in (".zolo", ".json", ".yaml", ".yml")
                          if os.path.exists(fbase + ext)), fbase)
            data = self.zos.loader.handle_absolute_path(fpath)
            if isinstance(data, dict) and key in data:
                return key, data[key]
        except Exception as exc:  # pylint: disable=broad-except
            self.zos.logger.framework.warning(f"[zLoom] zPath ref '{ref}' failed: {exc}")
        self.zos.logger.framework.warning(f"[zLoom] zPath ref '{ref}' did not resolve")
        return None

    def load_zloom_registry(self) -> Dict[str, Any]:
        """Load the zSpool registry — the SSOT for named reads.

        ONE source: ``<zSpace>/zLoom/spools/*.{zolo,json,yaml,yml}`` — a zSpool is a
        named reel of data the page draws threads (%data values) from. Each file's
        top-level keys ARE the spool names (zMeta skipped). Not cached here — the
        loader caches per-file parses, so the dir scan is cheap and keeps edits live.
        """
        import os
        registry: Dict[str, Any] = {}
        base = self.zos.session.get("zSpace") if hasattr(self.zos, "session") else None
        base = base or os.getcwd()
        zloom_dir = os.path.join(base, "zLoom", "spools")
        if os.path.isdir(zloom_dir):
            for fname in sorted(os.listdir(zloom_dir)):
                if os.path.splitext(fname)[1].lower() not in (".zolo", ".json", ".yaml", ".yml"):
                    continue
                fpath = os.path.join(zloom_dir, fname)
                try:
                    data = self.zos.loader.handle_absolute_path(fpath)
                except Exception as exc:  # pylint: disable=broad-except
                    self.zos.logger.framework.error(f"[zLoom] Failed to load '{fname}': {exc}")
                    continue
                if isinstance(data, dict):
                    for key, val in data.items():
                        if key == "zMeta":
                            continue
                        registry[key] = val
        return registry
