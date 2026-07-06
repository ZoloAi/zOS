# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/display_event_media.py

"""
MediaEvents - Media Display Event Package for zDisplay
=====================================================

This event package provides structured media display (images) with
comprehensive formatting options, building on the BasicOutputs foundation.

Composition Architecture
------------------------
MediaEvents builds on BasicOutputs:

Layer 3: display_delegates.py (PRIMARY API)
    ↓
Layer 2: display_events.py (ORCHESTRATOR)
    ↓
Layer 2: events/display_event_media.py (MediaEvents) ← THIS MODULE
    ↓
Layer 2: events/display_event_outputs.py (BasicOutputs) ← FOUNDATION
    ↓
Layer 1: display_primitives.py (FOUNDATION I/O)

Composition Flow:
1. MediaEvents.image() method called
2. If GUI mode (Bifrost):
   a. Send clean JSON event with essential image data (src, alt_text, caption)
   b. Returns immediately (GUI handles async)
3. If terminal mode:
   a. Format image metadata (path, alt text, caption)
   b. Apply styling (indentation, color)
   c. Display via BasicOutputs.text() for consistent I/O
   d. Display button with action="#" (placeholder for future zOpen integration)
4. Return control to caller

Dual-Mode I/O Pattern
----------------------
All methods implement the same dual-mode pattern:

1. **GUI Mode (Bifrost):** Try send_gui_event() first
   - Send clean JSON event with data (src, alt_text, caption)
   - Returns immediately (GUI handles async)
   - GUI frontend will display data

2. **zCLI Mode (Fallback):** Format and display locally
   - Format image metadata (path, alt, caption)
   - Apply styling (indentation, colors)
   - Display via BasicOutputs.text() for consistent I/O
   - Show button with action="#" as placeholder

Terminal-First Philosophy
--------------------------
In terminal mode, images display as:
- 📷 Icon + alt text header
- Path display
- Caption (if provided)
- Button with action="#" (if open_prompt=True)

This ensures terminal users get full metadata even if they can't view the image inline.
"""

from zOS import Any, Dict, Optional

# Import constants from centralized module
from ...display_constants import (
    _EVENT_IMAGE,
    _EVENT_VIDEO,
    _EVENT_AUDIO,
    _EVENT_PICTURE,
    _EVENT_ICON,
    _EVENT_EMBED,
    _DEFAULT_IMAGE_ICON,
    _DEFAULT_VIDEO_ICON,
    _DEFAULT_AUDIO_ICON,
    _DEFAULT_PICTURE_ICON,
    _DEFAULT_EMBED_ICON,
    MODE_BIFROST,
)
from ...utils.confirm_gate import confirm_gate, is_flat

class MediaEvents:
    """Event package for displaying media (e.g., images)."""

    display: Any  # Parent zDisplay instance
    zPrimitives: Any  # Primitives instance for I/O operations
    zColors: Any  # Colors instance for terminal styling
    BasicOutputs: Any # BasicOutputs instance for consistent text output
    InteractiveInputs: Any # InteractiveInputs instance for button logic

    def __init__(self, display_instance: Any) -> None:
        """Initialize MediaEvents with parent display reference.

        Args:
            display_instance: Parent zDisplay instance providing primitives and colors.
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors
        self.logger = display_instance.logger # Access logger from display instance

    # ── Shared media seam (SSOT for image/video/audio) ───────────────────────
    # image/video/audio are siblings: same inputs (src, alt_text, caption), same
    # resolution rules, same terminal block, same y/n open-gate. These helpers are
    # the single source for all of it — methods below just plug in their icon,
    # event name, default label, gate kind and opener.

    def _resolve_media_fields(
        self,
        src: str,
        alt_text: str,
        caption: str,
        _context: Optional[dict] = None,
    ) -> tuple:
        """Resolve %vars then @/~ zPaths (extension-aware) for any media event.

        zPath becomes a web URL in Bifrost, an absolute filesystem path in zCLI.
        Same rules for image, video and audio (audio previously skipped this).
        """
        from .....d_zParser.parser_modules.parser_functions import resolve_variables

        if "%" in src:
            src = resolve_variables(src, self.display.zos, _context)
        if "%" in alt_text:
            alt_text = resolve_variables(alt_text, self.display.zos, _context)
        if "%" in caption:
            caption = resolve_variables(caption, self.display.zos, _context)

        src = self._resolve_media_path(src, _context)

        return src, alt_text, caption

    def _resolve_media_path(
        self,
        value: str,
        _context: Optional[dict] = None,
    ) -> str:
        """Resolve %vars then a @/~ zPath for a single media path (src or poster).

        zPath → web URL in Bifrost, absolute filesystem path in zCLI. Same rules
        as the primary src so secondary paths (e.g. a video poster) don't leak a
        raw zPath to the client and 404. No-op for plain URLs / empty values.
        """
        if not value or not isinstance(value, str):
            return value

        from .....d_zParser.parser_modules.parser_functions import resolve_variables

        if "%" in value:
            value = resolve_variables(value, self.display.zos, _context)

        if value.startswith(("@", "~")):
            # Extension-aware resolve (resolve_zfile, NOT resolve_data_path).
            resolved_path = self.display.zos.zparser.resolve_zfile(value)
            self.logger.debug(f"[MediaEvents] Resolved zPath: {value} → {resolved_path}")
            if self.display.mode == MODE_BIFROST:
                value = self.display.zos.zparser.absolute_path_to_web_path(resolved_path)
                self.logger.debug(f"[MediaEvents] Bifrost web path: {value}")
            else:
                value = resolved_path
                self.logger.debug(f"[MediaEvents] zCLI absolute path: {value}")

        return value

    def _emit_terminal_meta(
        self,
        icon: str,
        alt_text: str,
        default_label: str,
        src: str,
        caption: str,
        indent: int,
        color: Optional[str],
    ) -> None:
        """Print the shared terminal block: icon+alt header, Path, optional Caption."""
        indent_str = "  " * indent
        display_color = color if color else self.display.mycolor

        header = (
            f"{indent_str}{icon} {alt_text}" if alt_text
            else f"{indent_str}{icon} {default_label}"
        )
        self.BasicOutputs.text(header, indent=0, color=display_color, break_after=False)
        self.BasicOutputs.text(f"{indent_str}   Path: {src}", indent=0, color="muted", break_after=False)
        if caption:
            self.BasicOutputs.text(f"{indent_str}   Caption: {caption}", indent=0, color="muted", break_after=False)

    def _open_gate(self, kind: str, label: str, opener: Any, src: str) -> None:
        """SSOT y/n open-gate for media (confirm_gate → opener). zFlat-aware."""
        self.zPrimitives.write_line("")  # spacing before the gate
        confirmed = confirm_gate(self.display, kind, label=label)
        if confirmed:
            self.logger.info(f"[MediaEvents] User confirmed open for: {src}")
            result = opener(src)
            if result == "zBack":
                self.logger.info(f"[MediaEvents] Successfully opened: {src}")
            else:
                self.logger.warning(f"[MediaEvents] Failed to open: {src}")
        elif not is_flat(self.display):
            # zFlat already rendered the inert affordance — no decline line.
            self.BasicOutputs.text(f"  Open {label} cancelled.", indent=0, break_after=False)

    def image(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        _context: Optional[dict] = None,  # NEW v1.5.12: Context for %data.* resolution
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Display an image event.

        In Bifrost mode, sends a clean event with src, alt_text, and caption.
        In zCLI mode, displays formatted text with path, alt_text, caption,
        and a button with action="#" (placeholder for future zOpen integration).

        Args:
            src: The source URL or path of the image.
            alt_text: Alternative text for the image (accessibility).
            caption: An optional caption for the image.
            open_prompt: If True (default), displays a button in terminal mode (with action="#").
                        Set to False to disable the prompt.
            indent: Indentation level for terminal output.
            color: Color for terminal output text.
            **kwargs: Additional parameters to pass through to the event.

        Returns:
            Optional[Dict[str, Any]]: The event dictionary if sent to GUI,
                                     or None for terminal mode.
        """
        if not src:
            self.logger.error("[MediaEvents] image() requires 'src' parameter")
            return None

        src, alt_text, caption = self._resolve_media_fields(src, alt_text, caption, _context)

        base_event = {"src": src, "alt_text": alt_text, "caption": caption, **kwargs}

        if self.display.mode == MODE_BIFROST:
            return self.zPrimitives.send_gui_event(_EVENT_IMAGE, base_event)

        # zCLI mode: shared terminal block + SSOT open-gate
        self._emit_terminal_meta(_DEFAULT_IMAGE_ICON, alt_text, "Image", src, caption, indent, color)
        if open_prompt:
            self._open_gate("image", "image file", self.display.zos.open.open_image, src)
        else:
            self.zPrimitives.write_line("")
        return None

    def video(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        _context: Optional[dict] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Display a video event.

        In Bifrost mode, sends a clean event with src, alt_text, and caption.
        In zCLI mode, displays formatted text with path, alt_text, caption,
        and a button (calls zOpen.open_video()).

        Args:
            src: The source URL or path of the video.
            alt_text: Alternative text for the video (accessibility).
            caption: An optional caption for the video.
            open_prompt: If True (default), displays a button in terminal mode.
                        Set to False to disable the prompt.
            indent: Indentation level for terminal output.
            color: Color for terminal output text.
            **kwargs: Additional parameters to pass through to the event.

        Returns:
            Optional[Dict[str, Any]]: The event dictionary if sent to GUI,
                                     or None for terminal mode.
        """
        if not src:
            self.logger.error("[MediaEvents] video() requires 'src' parameter")
            return None

        src, alt_text, caption = self._resolve_media_fields(src, alt_text, caption, _context)

        # poster is a second media path — resolve its zPath too, or it leaks raw
        # to the client and 404s (black player). loop/muted/autoplay pass through.
        if kwargs.get("poster"):
            kwargs["poster"] = self._resolve_media_path(kwargs["poster"], _context)

        base_event = {"src": src, "alt_text": alt_text, "caption": caption, **kwargs}

        if self.display.mode == MODE_BIFROST:
            return self.zPrimitives.send_gui_event(_EVENT_VIDEO, base_event)

        # zCLI mode: shared terminal block + SSOT open-gate
        self._emit_terminal_meta(_DEFAULT_VIDEO_ICON, alt_text, "Video", src, caption, indent, color)
        if open_prompt:
            self._open_gate("video", "video file", self.display.zos.open.open_video, src)
        else:
            self.zPrimitives.write_line("")
        return None

    def audio(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        _context: Optional[dict] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Display an audio event.

        In Bifrost mode, sends a clean event with src, alt_text, and caption.
        In zCLI mode, displays formatted text with path, alt_text, caption,
        and a button (calls zOpen.open_audio()).

        Args:
            src: The source URL or path of the audio file.
            alt_text: Alternative text for the audio (accessibility).
            caption: An optional caption for the audio.
            open_prompt: If True (default), displays a button in terminal mode.
                        Set to False to disable the prompt.
            indent: Indentation level for terminal output.
            color: Color for terminal output text.
            **kwargs: Additional parameters to pass through to the event.

        Returns:
            Optional[Dict[str, Any]]: The event dictionary if sent to GUI,
                                     or None for terminal mode.
        """
        if not src:
            self.logger.error("[MediaEvents] audio() requires 'src' parameter")
            return None

        src, alt_text, caption = self._resolve_media_fields(src, alt_text, caption, _context)

        base_event = {"src": src, "alt_text": alt_text, "caption": caption, **kwargs}

        if self.display.mode == MODE_BIFROST:
            return self.zPrimitives.send_gui_event(_EVENT_AUDIO, base_event)

        # zCLI mode: shared terminal block + SSOT open-gate
        self._emit_terminal_meta(_DEFAULT_AUDIO_ICON, alt_text, "Audio", src, caption, indent, color)
        if open_prompt:
            self._open_gate("audio", "audio file", self.display.zos.open.open_audio, src)
        else:
            self.zPrimitives.write_line("")
        return None

    def embed(
        self,
        src: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        _context: Optional[dict] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Display an embed event — external URL-type content rendered in place.

        zEmbed is a media sibling (image/video/audio): same src/alt/caption seam,
        same dual-mode contract. It covers URL-type embeds (video providers,
        maps, payment/scheduling widgets, generic iframes) that the browser — not
        zOS — renders.

        zCLI degrades to the shared media block (icon + URL + caption) and the
        zOpen open-gate, exactly like an image can't render inline.

        BIFROST TRUST BOUNDARY (Phase 1): every embed is vetted SERVER-side here
        before anything reaches the public client. ``resolve_embed`` normalizes
        the URL (e.g. youtube watch → embed) and checks it against the fail-closed
        provider allow-list; ``verify_embed`` is the zGuard attestation seam on
        top. An allowed embed emits a vetted payload (normalized src + the exact
        sandbox/allow envelope) the client renders inside a sandboxed iframe
        (Phase 4). A denied embed degrades to a plain link — never an iframe — so
        an untrusted URL can never execute in a visitor's browser. The CSP
        ``frame-src`` backstop (Phase 3) and operator ``ZEMBED_MODE`` tier
        (Phase 2) harden this further; the boundary itself lives here.

        Args:
            src: The embed source URL (http/https). zPaths/%vars are resolved.
            alt_text: Accessibility / fallback label.
            caption: Optional caption.
            open_prompt: If True (default), zCLI shows the open-in-browser gate.
            indent: Indentation level for terminal output.
            color: Color for terminal output text.

        Returns:
            Optional[Dict[str, Any]]: vetted event dict (Bifrost), or None (zCLI).
        """
        if not src:
            self.logger.error("[MediaEvents] embed() requires 'src' parameter")
            return None

        src, alt_text, caption = self._resolve_media_fields(src, alt_text, caption, _context)

        if self.display.mode == MODE_BIFROST:
            return self._embed_bifrost(src, alt_text, caption, **kwargs)

        # zCLI mode: shared terminal block + SSOT open-gate (open URL in browser)
        self._emit_terminal_meta(_DEFAULT_EMBED_ICON, alt_text, "Embed", src, caption, indent, color)
        if open_prompt:
            self._open_gate("embed", "embedded content", self.display.zos.open.open_embed, src)
        else:
            self.zPrimitives.write_line("")
        return None

    def _embed_mode(self) -> str:
        """Resolve the active embed trust tier from zEnv ``ZEMBED_MODE``.

        The single read-point for the off/safe/trust tier. zEnv is owned by
        zConfig — reach it via ``config.environment.get_env_var`` (the SSOT
        accessor, same path zTerminal uses); never read ``os.environ`` here.
        Fail-closed: unset / empty / unknown → ``safe`` (allow-listed only).
        """
        from ...embed.embed_policy import normalize_mode, ZEMBED_MODE_KEY
        value = None
        try:
            cfg = getattr(self.display.zos, "config", None)
            env_cfg = getattr(cfg, "environment", None)
            if env_cfg is not None and hasattr(env_cfg, "get_env_var"):
                value = env_cfg.get_env_var(ZEMBED_MODE_KEY)
        except Exception:
            value = None
        return normalize_mode(value)

    def _embed_bifrost(
        self,
        src: str,
        alt_text: str,
        caption: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Vet an embed server-side and emit a trusted payload (or link fallback).

        The single Bifrost trust boundary for zEmbed: normalize + allow-list
        (``resolve_embed``) then zGuard attestation (``verify_embed``). Allowed →
        emit the vetted iframe payload; denied → degrade to a plain ``zURL`` link
        so an untrusted URL is never handed to the client as a frame.
        """
        from ...embed.embed_policy import resolve_embed
        from ...embed.embed_trust import verify_embed, EmbedTrustError

        mode = self._embed_mode()
        decision = resolve_embed(src, mode)

        if decision["allowed"]:
            try:
                trusted = verify_embed(src, decision["provider"], mode,
                                       self.display.zos, self.logger)
            except EmbedTrustError as exc:
                self.logger.warning(f"[MediaEvents] embed attestation denied: {exc}")
                trusted = False
            if trusted:
                event_data = {
                    "src": decision["src"],
                    "alt_text": alt_text,
                    "caption": caption,
                    "provider": decision["provider"],
                    "sandbox": decision["sandbox"],
                    "allow": decision["allow"],
                    "aspect": decision["aspect"],
                    **kwargs,
                }
                return self.zPrimitives.send_gui_event(_EVENT_EMBED, event_data)

        # Denied (unknown provider / off tier / attestation) → safe link fallback.
        self.logger.warning(
            f"[MediaEvents] embed denied, degrading to link "
            f"({decision.get('reason', 'attestation')}): {src}"
        )
        return self.zPrimitives.send_gui_event(
            "zURL", {"label": alt_text or caption or src, "href": src, **kwargs}
        )

    def picture(
        self,
        sources: list,
        fallback: str,
        alt_text: str = "",
        caption: str = "",
        open_prompt: bool = True,
        indent: int = 0,
        color: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Display a picture element (responsive image with source selection).

        In Bifrost mode, sends a clean event with sources, fallback, alt_text, and caption.
        In zCLI mode, displays formatted list of sources with interactive selection.

        Args:
            sources: List of source dicts with 'srcset' and 'media' keys
                    e.g., [{"srcset": "large.jpg", "media": "(min-width: 1024px)"}]
            fallback: Fallback image path (required, used as default)
            alt_text: Alternative text for the picture (accessibility).
            caption: An optional caption for the picture.
            open_prompt: If True (default), displays interactive selection in terminal mode.
                        Set to False to disable the prompt.
            indent: Indentation level for terminal output.
            color: Color for terminal output text.
            **kwargs: Additional parameters to pass through to the event.

        Returns:
            Optional[Dict[str, Any]]: The event dictionary if sent to GUI,
                                     or None for terminal mode.
                                     
        Terminal Interaction:
            User can:
            - Enter number (1-N) + Enter: Opens that source
            - Just Enter: Opens fallback (default)
            - 'done' + Enter: Skips, no open
        """
        if not sources and not fallback:
            self.logger.error("[MediaEvents] picture() requires 'sources' or 'fallback' parameter")
            return None

        # Base event for both modes
        base_event = {
            "type": _EVENT_PICTURE,
            "sources": sources,
            "fallback": fallback,
            "alt_text": alt_text,
            "caption": caption,
            **kwargs
        }

        if self.display.mode == MODE_BIFROST:
            # Bifrost gets clean picture data with all sources
            return self.zPrimitives.send_gui_event(base_event)
        else:
            # zCLI mode: format and display with interactive selection
            indent_str = "  " * indent
            display_color = color if color else self.display.mycolor

            # Display icon + alt text header with "Responsive Image" indicator
            header = (
                f"{indent_str}{_DEFAULT_PICTURE_ICON} {alt_text} (Responsive Image)" if alt_text
                else f"{indent_str}{_DEFAULT_PICTURE_ICON} Responsive Image"
            )
            self.BasicOutputs.text(header, indent=0, color=display_color, break_after=False)

            # Build complete list of all sources including fallback
            all_sources = list(sources) if sources else []

            # Display numbered sources
            self.BasicOutputs.text(f"{indent_str}   Sources:", indent=0, color="muted", break_after=False)
            for idx, src in enumerate(all_sources, 1):
                media = src.get('media', 'default')
                srcset = src.get('srcset')
                self.BasicOutputs.text(
                    f"{indent_str}   {idx}. {media}: {srcset}",
                    indent=0,
                    color="muted",
                    break_after=False
                )

            # Display fallback as the default option (last in list)
            fallback_idx = len(all_sources) + 1
            self.BasicOutputs.text(
                f"{indent_str}   {fallback_idx}. Fallback: {fallback} [default]",
                indent=0,
                color="muted",
                break_after=False
            )

            # Display caption (if provided)
            if caption:
                caption_line = f"{indent_str}   Caption: {caption}"
                self.BasicOutputs.text(caption_line, indent=0, color="muted", break_after=False)

            # Interactive selection
            if open_prompt:
                # Add spacing before prompt
                self.zPrimitives.write_line("")

                # Custom input prompt
                prompt = f"Select source (1-{fallback_idx}, Enter=fallback, 'done'=skip): "

                try:
                    # Use read_string primitive directly (like button does)
                    choice = self.zPrimitives.read_string(prompt).strip().lower()

                    # Parse and handle input
                    selected_src = None

                    if choice == 'done':
                        # User chose to skip
                        self.logger.info("[MediaEvents] User skipped picture")
                        return None
                    elif choice == '':
                        # Default to fallback
                        selected_src = fallback
                        self.logger.info(f"[MediaEvents] User selected fallback (default): {fallback}")
                    elif choice.isdigit():
                        # User selected a specific source
                        idx = int(choice) - 1
                        if 0 <= idx < len(all_sources):
                            # Selected a source from the list
                            selected_src = all_sources[idx].get('srcset')
                            media = all_sources[idx].get('media', 'unknown')
                            self.logger.info(f"[MediaEvents] User selected {media}: {selected_src}")
                        elif idx == len(all_sources):
                            # Selected fallback explicitly
                            selected_src = fallback
                            self.logger.info(f"[MediaEvents] User selected fallback: {fallback}")
                        else:
                            # Invalid index
                            self.logger.warning(f"[MediaEvents] Invalid choice: {choice} (out of range)")
                            self.BasicOutputs.text(
                                f"{indent_str}   Invalid choice. Please enter 1-{fallback_idx}.",
                                indent=0,
                                color="warning",
                                break_after=False
                            )
                            return None
                    else:
                        # Invalid input
                        self.logger.warning(f"[MediaEvents] Invalid input: {choice}")
                        self.BasicOutputs.text(
                            f"{indent_str}   Invalid input. Please enter a number, press Enter, or type 'done'.",
                            indent=0,
                            color="warning",
                            break_after=False
                        )
                        return None

                    # Open selected source
                    if selected_src:
                        result = self.display.zos.open.open_image(selected_src)
                        if result == "zBack":
                            self.logger.info(f"[MediaEvents] Successfully opened: {selected_src}")
                        else:
                            self.logger.warning(f"[MediaEvents] Failed to open: {selected_src}")

                except KeyboardInterrupt:
                    # User cancelled
                    self.logger.info("[MediaEvents] User cancelled picture selection")
                    return None
            else:
                # Add break after last line if no prompt
                self.zPrimitives.write_line("")

            return None

    def icon(
        self,
        name: str,
        color: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Display Bootstrap Icon (mode-aware rendering).
        
        Renders appropriately based on mode:
        - zBifrost (web): HTML <i> tag with Bootstrap Icons classes
        - zCLI (terminal): Emoji fallback or Unicode character
        
        Args:
            name: Icon name (with or without 'bi-' prefix)
                 Examples: "tools", "bi-tools", "compass", "bi-compass"
            color: Color class (Bifrost only) - e.g., "zText-primary"
            **kwargs: Additional properties (e.g., _zClass for Bifrost)
        
        Examples:
            # Simple icon
            display.icon(name="tools")
            
            # With color
            display.icon(name="compass", color="zText-primary")
            
            # Shorthand in .zolo file
            zIcon: bi-tools
            
            # Full form in .zolo file
            zIcon:
                name: bi-tools
                color: zText-primary
        """
        from ...basic.outputs.icon_renderer import render_icon_event
        
        # Build event data
        event_data = {
            'name': name,
        }
        if color:
            event_data['color'] = color
        
        # Merge additional kwargs (e.g., _zClass). Drop any legacy 'size' — sizing
        # is governed by _zClass like every other event (size is no longer a zIcon prop).
        kwargs.pop('size', None)
        event_data.update(kwargs)
        
        # Try GUI mode first — dispatch the dedicated 'icon' event so the client
        # routes to IconRenderer (a 'image' event would hit ImageRenderer, which
        # requires src and would error on an icon payload).
        if hasattr(self.display, 'try_gui_event'):
            gui_result = self.display.try_gui_event(_EVENT_ICON, event_data)
            if gui_result:
                return
        
        # Terminal mode - render icon
        rendered = render_icon_event(self.display, event_data)
        
        if rendered:
            # Display rendered icon
            self.zPrimitives.raw(rendered)
            
        else:
            # Fallback if rendering failed
            self.logger.warning(f"[MediaEvents] Failed to render icon: {name}")
