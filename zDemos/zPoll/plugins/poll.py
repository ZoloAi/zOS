"""poll — real-time vote aggregation over a denormalized counter.

Unlike a logged-vote table + group_by aggregate (zShop's cart pattern), each
Option row carries its own `votes` counter — cast_vote bumps it with a
computed `{$inc: 1}` update (18_data_advanced.md "computed"), the one golden
app to dogfood that op. The counter itself IS the aggregate; zLoom/spools
reads it straight back for the live bar + percentage, no join required.

No double-vote guard by design — this is a one-off engagement widget (think
a public site poll), not an authenticated ballot.
"""

from zos_plugin import zfunc

_POLLS = "Polls"
_OPTIONS = "Options"
_MIN_OPTIONS = 2


@zfunc
def create_poll(question, option_1, option_2, option_3, option_4, data):
    """New poll + 2-4 options in one step (Options 3/4 are optional)."""
    question = (question or "").strip()
    if not question:
        return "error"

    labels = [
        label.strip()
        for label in (option_1, option_2, option_3, option_4)
        if label and label.strip()
    ]
    if len(labels) < _MIN_OPTIONS:
        return "error"

    poll = data.insert(_POLLS, {"question": question})
    for label in labels:
        data.insert(_OPTIONS, {"poll_id": poll.id, "label": label, "votes": 0})

    return f"Poll created: {question} ({len(labels)} options)"


@zfunc
def cast_vote(option_id, data):
    """Per-row vote (08_data_crud.md `per_row`) — bumps the option's counter."""
    row = data.first(_OPTIONS, where={"id": option_id})
    if row is None:
        return "error"

    data.update(_OPTIONS, {"votes": {"$inc": 1}}, where={"id": option_id})
    return f"Vote recorded for {row.get('label')}"
