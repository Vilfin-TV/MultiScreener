    bench_series = {}
    for k, b in bench.items():
        s = series[b["code"]]
        bench_series[k] = {"d": [C.iso(x) for x in s.d], "v": [float(x) for x in s.v]}
    if "rf" in bench and bench["rf"]["code"] in series:
        s = series[bench["rf"]["code"]]
        bench_series["rf"] = {"d": [C.iso(x) for x in s.d], "v": [float(x) for x in s.v]}
    sample = {"monthEnds": [m.isoformat() for m in month_ends], "rf": [None if not np.isfinite(x) else x for x in rf_vals],
              "rfCode": bench["rf"]["code"] if "rf" in bench else None,
              "riskAsOf": risk_asof.isoformat(), "bench": {k: [None if not np.isfinite(x) else x for x in v] for k, v in bench_me.items()},
              "benchCodes": {k: b["code"] for k, b in bench.items()}, "funds": []}
    sample["benchSeries"] = bench_series
