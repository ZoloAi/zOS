"""
z raven --gen step-level preservation (zOS#69).

Old behaviour: only zFill/zSubmit VALUES survived a regen — every hand-added
step (zClick navigation, zAssert, zShot) was replaced by the fresh skeleton,
silently. The contract now under test, at the pure-merge level
(_split_steps / _merge_hand_steps):

  • a step absent from the regenerated structure is spliced back VERBATIM
    (attached comments included), after its nearest surviving predecessor
  • a hand step before any surviving step lands right after the preamble
  • generated steps that were hand-edited IN PLACE are reported (regen wins,
    but the caller warns) — untouched generated steps are not
  • no hand steps → merged output is byte-identical to the generated text
"""

import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from zSys.cli.raven_generator import _merge_hand_steps, _split_steps  # noqa: E402


GEN = """# .zolo — NOT YAML
# zRavenVersion: v1.0.0

Tests:

    # ── Bifrost: open page ──────────────────────────────────────────────
    Open_App:
        zOpen: zSpark
        zWait:
            selector: body

    # ── Contacts ──────────────────────────────────────────────
    Pick_Contacts:
        zPick: Contacts

    Fill_Add_Contact_Form:
        zFill:
            email: zraven@test.local

    Done:
        zMarker: done
"""

# The same file after an author added: a comment+assert after Pick_Contacts,
# a zShot step after the fill, and edited Open_App's wait selector in place.
EDITED = """# .zolo — NOT YAML
# zRavenVersion: v1.0.0

Tests:

    # ── Bifrost: open page ──────────────────────────────────────────────
    Open_App:
        zOpen: zSpark
        zWait:
            selector: .app-root

    # ── Contacts ──────────────────────────────────────────────
    Pick_Contacts:
        zPick: Contacts

    # hand: the list must show the seeded row
    Assert_Seeded_Row:
        zAssert:
            contains: Alice

    Fill_Add_Contact_Form:
        zFill:
            email: real@customer.com

    Shot_Contacts_Mobile:
        zViewport: mobile
        zShot:
            full_page: true

    Done:
        zMarker: done
"""


def test_split_covers_file_and_names_steps():
    preamble, steps = _split_steps(GEN)
    assert [n for n, _ in steps] == ["Open_App", "Pick_Contacts",
                                     "Fill_Add_Contact_Form", "Done"]
    rebuilt = "\n".join(preamble + [l for _, seg in steps for l in seg]) + "\n"
    assert rebuilt == GEN  # raw slices cover the input exactly


def test_hand_steps_spliced_at_anchor_with_comment():
    merged, kept, edited = _merge_hand_steps(GEN, EDITED)
    assert kept == ["Assert_Seeded_Row", "Shot_Contacts_Mobile"]
    # verbatim, attached comment included
    assert "# hand: the list must show the seeded row" in merged
    assert "contains: Alice" in merged
    # anchored: assert lands after Pick_Contacts and BEFORE the fill step
    assert merged.index("Assert_Seeded_Row") > merged.index("Pick_Contacts:")
    assert merged.index("Assert_Seeded_Row") < merged.index("Fill_Add_Contact_Form")
    # shot lands after the fill, before Done
    assert merged.index("Shot_Contacts_Mobile") > merged.index("Fill_Add_Contact_Form")
    assert merged.index("Shot_Contacts_Mobile") < merged.index("Done:")


def test_in_place_edit_of_generated_step_is_reported():
    _, _, edited = _merge_hand_steps(GEN, EDITED)
    # Open_App's selector was hand-edited; Fill's VALUE change is also a body
    # diff from the fresh gen (values are preserved upstream by _extract_preserved
    # — at merge level the report is simply "this body differs").
    assert "Open_App" in edited
    assert "Pick_Contacts" not in edited
    assert "Done" not in edited


def test_no_hand_steps_is_identity():
    merged, kept, edited = _merge_hand_steps(GEN, GEN)
    assert merged == GEN
    assert kept == [] and edited == []


def test_empty_or_stepless_old_file_is_identity():
    assert _merge_hand_steps(GEN, "")[0] == GEN
    assert _merge_hand_steps(GEN, "# just a comment\n")[0] == GEN


def test_hand_step_before_first_generated_step_prepends():
    old = GEN.replace(
        "Tests:\n",
        "Tests:\n\n    Warmup_Probe:\n        zAssert:\n            contains: boot\n",
        1,
    )
    merged, kept, _ = _merge_hand_steps(GEN, old)
    assert kept == ["Warmup_Probe"]
    assert merged.index("Warmup_Probe") < merged.index("Open_App:")


def test_section_banner_not_duplicated_into_splice():
    # The Contacts banner trails Open_App's raw slice in EDITED; the spliced
    # hand steps must not drag a second copy of any banner along.
    merged, _, _ = _merge_hand_steps(GEN, EDITED)
    assert merged.count("# ── Contacts ") == 1
    assert merged.count("# ── Bifrost: open page ") == 1
