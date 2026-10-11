TERMINAL_STATES = frozenset({"completed", "completed_with_errors", "failed", "cancelled"})
ACTIVE_STATES = frozenset({"queued", "running"})

TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset({"completed", "completed_with_errors", "failed", "cancelled"}),
    **{state: frozenset() for state in TERMINAL_STATES},
}


class InvalidTransition(ValueError):
    pass


def can_transition(current: str, new: str) -> bool:
    return new in TRANSITIONS.get(current, frozenset())


def assert_transition(current: str, new: str) -> None:
    if not can_transition(current, new):
        raise InvalidTransition(f"cannot move run from '{current}' to '{new}'")
