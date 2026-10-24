"""Official comparisons require the same NAV date used by the return series.

An absent official snapshot is missing coverage, not evidence of a holiday.
Using an earlier cached NAV would compare different holding periods.
"""
def official_base_return(code, base_date, end_nav, years, snapshots):
    base = snapshots.get(base_date, {}).get(str(code))
    if base is None or base <= 0 or end_nav <= 0:
        return None
    ratio = end_nav / base
    return ((ratio ** (1 / years) - 1) if years else (ratio - 1)) * 100
