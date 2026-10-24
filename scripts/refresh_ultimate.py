"""Refresh independent sources; retain prior verified inputs on network outage.

Freshness gates remain mandatory. A failed refresh cannot turn a missing datum
into a pass; the prospective strategy will hold cash when evidence expires.
"""
import logging
from build_fund_earnings import build as earnings
from build_ultimate_folio import build as folio
from download_ultimate_history import run as histories

def run():
    try:earnings()
    except Exception as exc:logging.warning('Earnings refresh unavailable; freshness gates still apply: %s',exc)
    folio(False)
    try:histories()
    except Exception as exc:logging.warning('NAV history refresh unavailable; no history is invented: %s',exc)
    try:folio(True)
    except Exception as exc:
        logging.warning('ETF history refresh unavailable; retain available historical coverage: %s',exc)
        folio(False)
if __name__=='__main__':run()
