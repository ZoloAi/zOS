# zSys/formatting/colors.py
"""
ANSI color codes for terminal output.

Pure color definitions with no logic or dependencies.
"""

class Colors:
    """ANSI color codes for zCLI terminal output."""

    # ============================================================================
    # SUBSYSTEM COLORS (with background)
    # ============================================================================
    ZDATA      = "\033[97;48;5;94m"         # Brown bg (CRUD operations)
    ZFUNC      = "\033[97;41m"              # Red bg (Function execution)
    ZDIALOG    = "\033[97;45m"              # Magenta bg (Dialogs)
    ZWIZARD    = "\033[38;5;154;48;5;57m"   # Purple bg (Wizards)
    ZDISPLAY   = "\033[30;48;5;99m"         # Magenta bg (Display)
    PARSER     = "\033[38;5;236;48;5;230m"  # Dark text, cream background (Parsing)
    CONFIG     = "\033[97;48;5;65m"         # Green bg (Configuration)
    ZOPEN      = "\033[97;48;5;27m"         # Blue bg (File/URL opening)
    ZCOMM      = "\033[97;48;5;33m"         # Bright blue bg (Communication & services)
    ZAUTH      = "\033[97;48;5;130m"        # Orange-brown bg (Authentication)
    EXTERNAL   = "\033[30;103m"             # Yellow bg (External API)

    # ============================================================================
    # WALKER COLORS (UI/navigation with background)
    # ============================================================================
    MAIN       = "\033[30;48;5;120m"        # Light green bg (Main walker)
    SUB        = "\033[30;48;5;223m"        # Light yellow bg (Sub menus)
    MENU       = "\033[30;48;5;250m"        # Gray bg (Menu rendering)
    DISPATCH   = "\033[30;48;5;215m"        # Peach bg (Dispatch)
    ZLINK      = "\033[30;48;5;99m"         # Purple bg (Link navigation)
    ZCRUMB     = "\033[38;5;154m"           # Bright green text (Breadcrumbs)
    LOADER     = "\033[30;106m"             # Cyan bg (File loading)
    SUBLOADER  = "\033[38;5;214m"           # Orange text (Sub-loading)

    # ============================================================================
    # STANDARD COLORS (foreground only)
    # ============================================================================
    GREEN      = "\033[92m"                 # Bright green (Success)
    YELLOW     = "\033[93m"                 # Bright yellow (Highlights)
    MAGENTA    = "\033[95m"                 # Bright magenta (Special data)
    CYAN       = "\033[96m"                 # Bright cyan (Info)
    RED        = "\033[91m"                 # Bright red (Errors)
    PEACH      = "\033[38;5;223m"           # Peach (Debug)
    RESET      = "\033[0m"                  # Reset to default

    # ============================================================================
    # STATUS COLORS (with background)
    # ============================================================================
    ERROR      = "\033[97;48;5;124m"        # Dark red bg (Error states)
    WARNING    = "\033[31;48;5;178m"        # Orange bg (Warnings)
    RETURN     = "\033[38;5;214m"           # Orange text (Return values)

    # ============================================================================
    # CSS-ALIGNED SEMANTIC COLORS (foreground only)
    # ============================================================================
    # Mirrors CSS variables:
    #   --color-info:    #5CA9FF
    #   --color-success: #52B788
    #   --color-warning: #FFB347
    #   --color-error:   #E63946
    #
    # 256-color codes for broad terminal compatibility (macOS Terminal-safe)
    # NOTE: Truecolor 38;2;R;G;B may be flattened depending on terminal/theme

    zInfo      = "\033[38;5;75m"            # Light blue / info
    zSuccess   = "\033[38;5;78m"            # Green
    zWarning   = "\033[38;5;215m"           # Orange/yellow
    zError     = "\033[38;5;203m"           # Red

    # ============================================================================
    # CSS-ALIGNED BRAND COLORS (foreground only)
    # ============================================================================
    # Mirrors CSS variables:
    #   --color-primary:   #A2D46E (Intention - the heart of zCLI)
    #   --color-secondary: #9370DB (Validation - structure & elegance)

    PRIMARY    = "\033[38;5;150m"           # Light green (intention)
    SECONDARY  = "\033[38;5;98m"            # Medium purple (validation)

    # ============================================================================
    # TEXT ATTRIBUTES + EXTRA FG/BG  (SSOT for the zTheme→ANSI mapper)
    # ============================================================================
    # Consumed by ztheme_to_ansi.py so it never hardcodes raw escapes.
    BOLD          = "\033[1m"                # Bold weight
    NORMAL_WEIGHT = "\033[22m"               # Cancel bold (normal weight)
    ITALIC        = "\033[3m"                # Italic (not all terminals)
    NORMAL_STYLE  = "\033[23m"               # Cancel italic (normal style)
    DIM           = "\033[2m"                # Dim / muted

    BRIGHT_WHITE  = "\033[97m"               # Bright white text
    DARK_GRAY     = "\033[90m"               # Dark gray text

    BG_SUCCESS    = "\033[42m"               # Green background
    BG_INFO       = "\033[44m"               # Blue background
    BG_LIGHT      = "\033[47m"               # Light/white background
    BG_DARK       = "\033[40m"               # Dark/black background

    # ============================================================================
    # ALIASES (for backward compatibility and naming consistency)
    # ============================================================================
    ZINFO      = zInfo
    ZSUCCESS   = zSuccess
    ZWARNING   = zWarning
    ZERROR     = zError
    INFO       = zInfo
    SUCCESS    = zSuccess
    DEFAULT    = RESET

    primary    = PRIMARY
    secondary  = SECONDARY
    default    = DEFAULT
