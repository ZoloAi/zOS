# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/display_event_links.py

"""
LinkEvents - Semantic Link Rendering for zDisplay
==================================================

Handles semantic link rendering with support for:
- Internal navigation (delta $ and zPath @)
- External URLs (http/https)
- Anchor links (#section)
- Target behavior (_blank, _self, etc.)
- Window features (width, height, etc.)

zCLI Mode:
- Internal links: Auto-navigate or prompt based on link type
- External links: Show URL, prompt to open in browser
- Anchor links: Display with icon (no scroll in Terminal)
- Target: Limited support (new terminal window if possible)

Bifrost Mode:
- Internal links: Client-side routing via BifrostClient
- External links: Native <a> tag behavior with proper security
- Anchor links: Smooth scroll to target element
- Target: Full HTML5 support including window.open()

Architecture Position:
    Layer 2: Event Handlers (this module)
    Uses: display_primitives for output, zOpen for external links
    Called by: display_events.py orchestrator

Version: v1.6.0 (Link Event Support)
"""

# Centralized imports from zCLI
from zOS import Dict, Any, Optional

# Import constants from centralized module
from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_LINK,
    TARGET_BLANK,
    DEFAULT_TARGET,
    _LINK_TYPE_INTERNAL_DELTA,
    _LINK_TYPE_INTERNAL_ZPATH,
    _LINK_TYPE_EXTERNAL,
    _LINK_TYPE_ANCHOR,
    _LINK_TYPE_PLACEHOLDER,
    _LOG_PREFIX,
    MODE_ZCLI,
)
from zOS.zVocabulary import SESSION_KEY_ZMODE

# ZLinkResolver: Python SSOT for href classification, RBAC, and the nav IR
# (compile_intent). zURL is the navigation "compiler": it classifies an href into
# a NavIntent and dispatches the matching primitive — shared with zLink/zDelta.
from zOS.L2_Handling.h_zNavigation.navigation_modules.resolvers.resolver_zlink import (
    ZLinkResolver,
    NAV_VERB_ZLINK,
    NAV_VERB_ZDELTA,
    NAV_VERB_ANCHOR,
    NAV_VERB_EXTERNAL,
    NAV_VERB_PLACEHOLDER,
)


class LinkEvents:
    """
    Handle link event rendering for Terminal and Bifrost modes.
    
    Provides semantic link rendering with mode-aware behavior, supporting
    internal navigation, external URLs, and anchor links with full target
    and window feature control.
    
    Attributes:
        display: Parent zDisplay instance
        zos: Root zOS instance
        logger: Logger instance
    
    Methods:
        handle_link(): Main entry point for link rendering
    """

    def __init__(self, display: Any) -> None:
        """
        Initialize LinkEvents handler.
        
        Args:
            display: Parent zDisplay instance
        """
        self.display = display
        self.zos = display.zos
        self.logger = display.logger
        self.primitives = display.zPrimitives
        self.zColors = display.zColors  # For Terminal color support
        # Cross-references (set by zEvents)
        self.BasicOutputs = None  # Will be wired by zEvents.__init__
        self.BasicInputs = None   # Will be wired by zEvents.__init__

    def handle_link(self, link_data: Dict[str, Any]) -> Optional[Any]:
        """
        Main entry point for link event handling.
        
        Renders links based on mode (zCLI vs Bifrost) and link type
        (internal, external, anchor). Handles target behavior and window
        features for advanced use cases.
        
        Args:
            link_data: Dict with keys:
                - label: Link text (required)
                - href: Link destination (required)
                - target: Target behavior (_self, _blank, etc.)
                - rel: Link relationship (security)
                - window: Window features for window.open()
                - _zClass: CSS classes for styling
                - color: Color theme
        
        Returns:
            Navigation result (for internal links) or None
        
        Examples:
            # Internal link
            handle_link({"label": "About", "href": "$zAbout"})
            
            # External link with new tab
            handle_link({
                "label": "GitHub",
                "href": "https://github.com",
                "target": "_blank"
            })
            
            # Anchor link
            handle_link({"label": "Features", "href": "#features"})
        """
        href = link_data.get('href', '#')
        _label = link_data.get('label', href)
        _target = link_data.get('target', DEFAULT_TARGET)

        # Detect link type
        link_type = self._detect_link_type(href)

        # Route to mode-specific handler
        mode = self.zos.session.get(SESSION_KEY_ZMODE, MODE_ZCLI)

        if mode == MODE_ZCLI:
            return self._render_terminal(link_data, link_type)
        else:  # zBifrost
            return self._render_bifrost(link_data, link_type)

    def _detect_link_type(self, href: str) -> str:
        """
        Classify href into a link type constant.

        Delegates to ZLinkResolver.classify_href — the Python SSOT for
        href classification shared between zNavigation (zLink) and
        zDisplay (zURL).
        """
        return ZLinkResolver.classify_href(href)

    def _render_terminal(self, link_data: Dict[str, Any], link_type: str) -> Optional[Any]:
        """Render link in zCLI mode with interactive y/n prompt.
        
        Displays link with button-style interaction, prompting user with (y/n).
        Default behavior is 'n' (no action) if user just presses Enter.
        
        Args:
            link_data: Link configuration dict
            link_type: Detected link type
        
        Returns:
            Navigation dict (for internal links) or action result
        """
        href = link_data.get('href', '#')
        label = link_data.get('label', href)
        target = link_data.get('target', DEFAULT_TARGET)
        color = link_data.get('color', 'PRIMARY')

        # Display link label
        self._display_link_label(label)

        # SSOT confirm gate — prompt wording (per link type), colour, validation
        # and zFlat all live in confirm_gate / CONFIRM_TEMPLATES.
        from ...utils.confirm_gate import confirm_gate
        flat = f"{label} → {href}" if href and href != '#' else label
        confirmed = confirm_gate(
            self.display,
            self._link_confirm_kind(link_type),
            label=label,
            color=color,
            flat_text=flat,
        )
        if not confirmed:
            return self._handle_link_cancel(label)
        # zPsi rides along as a property (forward-compatible with zURL + zPsi):
        # an authored {href: …, zPsi: Section} lands on that section.
        zpsi = link_data.get('zPsi')
        return self._execute_link_action(link_type, href, label, target, zpsi)

    def _display_link_label(self, label: str) -> None:
        """Display the link label in button-style format."""
        self.BasicOutputs.text(f"[{label}]", break_after=False)

    def _link_confirm_kind(self, link_type: str) -> str:
        """Map a link type to its confirm_gate template key (CONFIRM_TEMPLATES).

        - internal (delta/zPath) → "Navigate to: {label}? (y/n)"
        - external              → "Open {label} in browser? (y/n)"
        - placeholder           → "Click {label}? (y/n)"
        - anchor                → "{label}? (y/n)"
        """
        if link_type == _LINK_TYPE_EXTERNAL:
            return "link_external"
        if link_type == _LINK_TYPE_PLACEHOLDER:
            return "link_placeholder"
        if link_type == _LINK_TYPE_ANCHOR:
            return "link_anchor"
        # internal delta/zPath and any unknown fall back to internal wording
        return "link_internal"

    def _handle_link_cancel(self, label: str) -> None:
        """Handle link cancellation (user declined or interrupted)."""
        self.BasicOutputs.text(f"{label} cancelled.", break_after=False)
        self.logger.debug(f"{_LOG_PREFIX} Link cancelled: {label}")
        # Return None instead of "stop" to continue with remaining wizard steps
        return None

    def _execute_link_action(
        self,
        link_type: str,
        href: str,
        label: str,
        target: str,
        zpsi: Optional[str] = None,
    ) -> Optional[Any]:
        """Compile the href (+ optional zPsi) into a NavIntent and dispatch.

        This is the zCLI half of **zURL-as-compiler**: the href's shape selects
        the verb via the SSOT (``compile_intent`` — the SAME compiler zLink and
        zDelta use), so one element routes four ways:

        - ``@.…`` → ``zLink`` (cross-file)        → ``{"zLink": <target>}``
        - ``$Block`` → ``zDelta`` (same-file hop) → ``{"zDelta": <target>}``
        - ``#section`` → in-page ``zPsi``          → ``{"zLink": {"zPsi": …}}``
        - ``http(s)://…`` → external               → zOpen (handled in place)
        - ``#`` / ``""`` → placeholder             → no-op

        The returned nav dict is re-dispatched by the wizard's
        ``_handle_navigation_result`` (which routes both ``zLink`` and
        ``zDelta``). external/placeholder act in place and return None so the
        wizard continues.
        """
        value = {'target': href, 'zPsi': zpsi} if zpsi else href
        intent = ZLinkResolver(self.logger).compile_intent(value)

        if intent.verb == NAV_VERB_EXTERNAL:
            return self._handle_external_link(href, label, target)
        if intent.verb == NAV_VERB_PLACEHOLDER:
            return self._handle_placeholder_link(label)

        self.BasicOutputs.text(f"Navigating to {label}...", break_after=False)
        self.logger.info(
            f"{_LOG_PREFIX} zURL → {intent.verb}: {href} (zPsi={intent.zpsi})"
        )

        # In-page jump within the CURRENT block (bare #section): no file change.
        if intent.verb == NAV_VERB_ANCHOR:
            return {"zLink": {"zPsi": intent.zpsi}}

        payload: Any = (
            {"target": intent.target, "zPsi": intent.zpsi}
            if intent.zpsi else intent.target
        )
        if intent.verb == NAV_VERB_ZDELTA:
            return {"zDelta": payload}
        return {"zLink": payload}

    def _handle_placeholder_link(self, label: str) -> None:
        """Handle placeholder link (no action)."""
        self.BasicOutputs.text(f"{label} is a placeholder (no action).", break_after=False)
        self.logger.debug(f"{_LOG_PREFIX} Placeholder link clicked (no action): {label}")
        return None

    def _handle_external_link(self, href: str, label: str, target: str) -> None:
        """Handle external URL link and continue wizard."""
        self.BasicOutputs.text(f"→ {href}", color="MUTED")
        self.BasicOutputs.text(f"Opening {label} in browser...", break_after=False)
        self.logger.info(f"{_LOG_PREFIX} External link confirmed: {href}")

        if target == TARGET_BLANK:
            self.logger.info(f"{_LOG_PREFIX} Opening in new window/tab (target: _blank)")

        # Open in browser but return None to continue wizard
        self.zos.open.handle(f"zOpen({href})")
        return None

    def _render_bifrost(self, link_data: Dict[str, Any], link_type: str) -> None:
        """
        Render link in Bifrost mode (send to frontend).

        Sends structured link event to frontend for semantic HTML rendering
        with proper <a> tags, target behavior, and security attributes.

        For internal links (delta/zpath), performs an RBAC check via
        ZLinkResolver before emitting the event — the same gate used by
        zLink in zNavigation — ensuring zURL cannot silently bypass
        permission requirements set on protected routes.

        If RBAC is denied the event is sent with disabled=True so Bifrost
        renders a non-clickable element rather than hiding it entirely,
        keeping the layout intact.

        Args:
            link_data: Link configuration dict
            link_type: Detected link type

        Notes:
            - Frontend handles client-side routing for internal links
            - Security: rel="noopener noreferrer" auto-added for _blank
            - Window features: Supports custom width, height, and features
        """
        # RBAC gate for internal links — mirrors zNavigation.handle_zLink behavior
        disabled = False
        if link_type in (_LINK_TYPE_INTERNAL_DELTA, _LINK_TYPE_INTERNAL_ZPATH):
            required_perms = link_data.get('permissions', {})
            resolver = ZLinkResolver(self.logger)
            session = self.zos.session if hasattr(self.zos, 'session') else {}
            if not resolver.check_permissions(session, required_perms):
                self.logger.warning(
                    f"{_LOG_PREFIX} RBAC denied for internal link '{link_data.get('href')}' — rendering disabled"
                )
                disabled = True

        # zPath → smart route via the single SSOT authority. Authors target
        # pages by zPath, exactly like zCLI navigation
        # (@.zViews.zProducts.zUI.zOS.zOS). In Bifrost the client addresses pages
        # by URL, so resolve the zPath to its canonical route HERE through
        # ZLinkResolver.resolve_href_to_route — the ONE place that maps a nav
        # href to a URL (reverse_route SSOT inverse, shared with zBifrost chunk
        # expansion and form onSuccess). Idempotent: a raw href is returned
        # untouched when no route serves it, so nothing regresses.
        href = link_data.get('href', '#')
        if link_type == _LINK_TYPE_INTERNAL_ZPATH:
            href = ZLinkResolver(self.logger).resolve_href_to_route(self.zos, href)

        # Emit link event to frontend with all metadata
        event_data = {
            'event': _EVENT_LINK,
            'label': link_data.get('label', ''),
            'href': href,
            'target': link_data.get('target', DEFAULT_TARGET),
            'rel': link_data.get('rel', ''),
            'link_type': link_type,
            '_zClass': link_data.get('_zClass', ''),
            'color': link_data.get('color', ''),
            'window': link_data.get('window', {}),
            'disabled': disabled,
        }

        # Auto-add security for external _blank links
        if (link_type == _LINK_TYPE_EXTERNAL and
            event_data['target'] == TARGET_BLANK and
            not event_data['rel']):
            event_data['rel'] = 'noopener noreferrer'
            self.logger.debug(f"{_LOG_PREFIX} Auto-added rel='noopener noreferrer' for external _blank link")

        # Send to frontend via primitives
        self.primitives.send_gui_event('link', event_data)
        self.logger.info(f"{_LOG_PREFIX} Link event sent to Bifrost: {link_data.get('label')}")
