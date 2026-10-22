  const rfSeries = (S.benchSeries && S.benchSeries.rf) || null;
  if (!rfSeries) {
    fail('verify sample missing the risk-free benchmark series; rebuild data/mf before verification');
    return;
  }
  const rfJs = monthEndVals(cut(rfSeries, riskAsOf), S.monthEnds);
