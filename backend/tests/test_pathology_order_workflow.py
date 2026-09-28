"""Tests for the pathology order workflow status helper.

One bill/order is shared by the billing counter and the lab/report counter;
there are only two statuses: Billed -> Report Ready (set explicitly once
every result is entered, via the authorize action).
"""
from app.repositories.pathology_masters import can_authorize


def test_can_authorize_requires_no_pending_results() -> None:
    assert can_authorize(0) is True
    assert can_authorize(1) is False
    assert can_authorize(5) is False
