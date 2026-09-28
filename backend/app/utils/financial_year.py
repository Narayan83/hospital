from datetime import date

FY_START_MONTH = 4  # April 1 (Indian financial year)


def financial_year_start(value: date | None = None) -> int:
    """Calendar year in which the FY containing *value* begins (1 Apr – 31 Mar)."""
    target = value or date.today()
    if target.month >= FY_START_MONTH:
        return target.year
    return target.year - 1
