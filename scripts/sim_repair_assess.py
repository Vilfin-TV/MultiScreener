#!/usr/bin/env python3
"""Read-only inspection of restricted historical MF subscriptions.

Never edits the hash-chained private ledger. A verified pre-existing SIP
requires documentary registration evidence, not inferred order frequency.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

RESTRICTIONS = {"118663": {"effective": "2026-10-16", "name": "Nippon India Gold Savings Fund"}}

def inspect(store):
    events = store.get("events", [])
    orders = {e["oid"]: e for e in events if e.get("k") == "order"}
    completed = {e["oid"]: e for e in events if e.get("k") in ("allot", "fill")}
    findings = []
    later_sells = {e.get("oid") for e in events if e.get("k") == "redeem"}
    for oid, order in orders.items():
        rule = RESTRICTIONS.get(str(order.get("code")))
        if not rule or order.get("side") != "buy" or order.get("T", "") < rule["effective"]:
            continue
        done = completed.get(oid)
        findings.append({
            "oid": oid, "acct": order.get("acct"), "date": order.get("T"),
            "code": str(order.get("code")), "scheme": rule["name"],
            "amount": order.get("amount"), "completed": bool(done),
            "allotment": ({"units": done.get("units"), "nav": done.get("nav"), "amount": done.get("amount"), "credit": done.get("credit")} if done else None),
            "action": "requires registration evidence or controlled correction",
        })
    # A reversal is not safe if any affected units were subsequently sold.
    # Flag *all* sales in the affected scheme/account for manual lot matching.
    for finding in findings:
        finding["subsequentRedemptions"] = [o["oid"] for o in orders.values()
            if o.get("acct") == finding["acct"] and str(o.get("code")) == finding["code"]
            and o.get("side") == "sell" and o.get("T", "") >= finding["date"]
            and o.get("oid") in later_sells]
    return {"mode": "READ_ONLY", "eventCount": len(events),
            "ledgerHead": events[-1]["h"] if events else None,
            "affectedOrders": len(findings),
            "totalAmount": round(sum(float(f["allotment"]["amount"] if f["allotment"] else f["amount"] or 0) for f in findings), 2),
            "safeToAutoReverse": False,
            "affectedAccounts": dict(Counter(f["acct"] for f in findings)),
            "findings": findings,
            "warning": "No ledger mutations, NAV changes, reallocations or public publication performed."}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = inspect(json.loads(Path(args.store).read_text()))
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Read-only repair assessment: {report['affectedOrders']} restricted orders across {len(report['affectedAccounts'])} accounts")
    print("Original ledger retained. No automatic historical reversal performed.")

if __name__ == "__main__":
    main()
