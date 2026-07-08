# zDemos/zQuiz/plugins/quiz.py
"""Scoring for the branching trivia quiz (11_wizard.md zHat + zGate).

Pure in-memory scoring — no zData involved. The wizard hands back whatever
each step's zHat filed; a Beginner run never asks Q3/Q4, so they arrive here
as None and are simply left out of the tally (zHat "miss" rule: a name never
filed comes back as nothing, never an error).
"""

from zos_plugin import zfunc

# (correct answer, points) — the answer key stays server-side, never in zUI
_ANSWERS = {
    "Q1": ("Paris", 2),
    "Q2": ("4", 1),
    "Q3": ("12", 3),
    "Q4": ("Mars", 2),
}

_BEGINNER_KEYS = ("Q1", "Q2")
_ADVANCED_KEYS = ("Q1", "Q2", "Q3", "Q4")


@zfunc
def score(track, q1, q2, q3=None, q4=None):
    given = {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4}
    keys = _ADVANCED_KEYS if track == "Advanced" else _BEGINNER_KEYS

    earned, total, lines = 0, 0, []
    for key in keys:
        correct, points = _ANSWERS[key]
        total += points
        answer = given.get(key)
        # A numeric-labelled option (e.g. options: [3, 4, 5, 6]) round-trips
        # through the plugin-call argument parser as an int, not the str the
        # zSelect displayed — compare as text so "4" and 4 both count.
        right = answer is not None and str(answer) == correct
        earned += points if right else 0
        mark = "✅" if right else "❌"
        lines.append(f"{mark} {key}: you said **{answer}**, correct was **{correct}**")

    pct = round(100 * earned / total) if total else 0
    verdict = "Nice work!" if pct >= 70 else "Keep practicing!"
    summary = f"### Score: {earned}/{total} ({pct}%) — {verdict}"
    return summary + "\n\n" + "\n\n".join(lines)
