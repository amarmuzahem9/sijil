"""Request status transitions (docs/system.md §7.2, specs/012 research R4). No database.

Every (from, to) pair is listed: the six allowed ones pass, every other one is refused.
`None` stands for the submission of a draft (a draft is not a request status).
"""

import itertools

import pytest

from app.core import request_status
from app.errors import AppError
from app.models.request import REQUEST_STATUSES

ALLOWED = {
    (None, "approved"),
    (None, "pending_review"),
    ("pending_review", "approved"),
    ("pending_review", "rejected"),
    ("approved", "linked"),
    ("linked", "approved"),
}

SOURCES = (None, *REQUEST_STATUSES)
PAIRS = list(itertools.product(SOURCES, REQUEST_STATUSES))


def test_the_table_is_exactly_system_md_7_2() -> None:
    table = {(old, new) for old, targets in request_status.TRANSITIONS.items() for new in targets}
    assert table == ALLOWED


@pytest.mark.parametrize(("old", "new"), sorted(ALLOWED, key=str))
def test_allowed_transitions_pass(old, new) -> None:
    request_status.check(old, new)


@pytest.mark.parametrize(
    ("old", "new"), [p for p in PAIRS if p not in ALLOWED], ids=lambda v: str(v)
)
def test_every_other_transition_is_refused(old, new) -> None:
    with pytest.raises(AppError) as err:
        request_status.check(old, new)
    assert (err.value.code, err.value.status) == ("invalid_transition", 409)
