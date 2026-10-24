"""Publish public simulated statements only from an audited private candidate."""
import argparse
import json
from pathlib import Path
from sim_engine import scoreboard,account_files

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dir',required=True);a=ap.parse_args();root=Path(a.dir)
    store,view,audit=[json.loads((root/(f+'.json')).read_text(encoding='utf-8')) for f in ('ledger','view','audit')]
    if audit['nErrors']!=0: raise SystemExit('Refusing to publish an unaudited correction')
    evs=store['events'];days=store.get('days',[])
    corrections=[e for e in evs if e.get('k')=='restatement']
    if len(corrections)!=1 or corrections[0]['count']!=15: raise SystemExit('Expected exactly the authorised 15-order correction')
    sb=scoreboard(view,True); files=account_files(store,view,sb)
    dest=Path('data/sim');dest.mkdir(parents=True,exist_ok=True)
    for f,body in files.items(): (dest/(f+'.json')).write_text(json.dumps(body,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    Path('data/sim_scoreboard.json').write_text(json.dumps(sb,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    Path('data/sim_meta.json').write_text(json.dumps(dict(v=1,events=len(evs),head=evs[-1]['h'],start=view['start'],days=len(days),daysHead=days[-1]['h'] if days else None),indent=1),encoding='utf-8')
    summaries=[]
    for e in corrections:
        totals={}
        for x in e['orders']:
            k=str(x['toCode']);totals.setdefault(k,{'orders':0,'amount':0});totals[k]['orders']+=1;totals[k]['amount']+=x['amount']
        summaries.append(dict(id=e['correctionId'],restatedAt=e['ts'],orders=e['count'],amount=e['totalAmount'],
            reason=e['reason'],replacementFunds=totals,auditErrors=audit['nErrors'],auditChecks=audit['checks'],
            note='Historical simulated transactions were restated at each replacement fund’s original trade-date official AMFI NAV. Contributions and dates were preserved; this is not a real-world trade.'))
    Path('data/sim_corrections.json').write_text(json.dumps({'v':1,'corrections':summaries},ensure_ascii=False,indent=1),encoding='utf-8')
    print(f'Public correction: {len(files)} account files; 15 corrected orders; audit errors=0')

if __name__=='__main__': main()
