from datetime import date

from app.utils.financial_year import financial_year_start


def test_financial_year_start_on_or_after_april() -> None:
    assert financial_year_start(date(2026, 4, 1)) == 2026
    assert financial_year_start(date(2026, 6, 13)) == 2026
    assert financial_year_start(date(2026, 12, 31)) == 2026


def test_financial_year_start_before_april() -> None:
    assert financial_year_start(date(2026, 1, 15)) == 2025
    assert financial_year_start(date(2026, 3, 31)) == 2025
