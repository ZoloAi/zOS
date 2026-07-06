"""
Accessibility data loader (internal).

Single source of truth for:
- the on-disk location of accessibility data (accessibility/data/)
- the data filenames consumed by this package
- the graceful "load JSON or fall back to {}" boilerplate

Keeping this here means emoji_descriptions.py and icon_mapper.py never
duplicate the path-walk or the try/except — they just name the file.
"""

import json
from pathlib import Path
from typing import Dict

# Data is co-located with its sole consumer (this package) so it packages cleanly
# via setup.py package_data={"zSys.accessibility": ["data/*.json"]}.
_DATA_DIR = Path(__file__).resolve().parent / "data"

EMOJI_A11Y_FILE = "emoji-a11y.en.json"
BOOTSTRAP_ICONS_FILE = "bootstrap-icons.json"


def data_file_path(filename: str) -> Path:
    """
    Absolute on-disk path of an accessibility data file.

    Exposes the canonical location so out-of-package consumers (e.g. zServer
    serving the emoji a11y JSON to the browser) reference the SAME file zCLI
    loads — one SSOT, no copies.
    """
    return _DATA_DIR / filename


def load_data_json(filename: str) -> Dict:
    """
    Load a JSON data file from zSys/data, degrading gracefully to {}.

    Never raises: a missing file, invalid JSON, or any unexpected read
    error all resolve to an empty dict so callers stay functional
    (emoji/text fallbacks) without a hard dependency on the data files.
    """
    try:
        with open(_DATA_DIR / filename, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    except Exception:  # pylint: disable=broad-except
        return {}
