"""Fetch actual selected-scheme daily histories, keeping unavailable periods null."""
import gzip,json
from pathlib import Path
from datetime import datetime
import requests
ROOT=Path(__file__).resolve().parents[1]
def run():
    s=json.loads((ROOT/'data/ultimate_folio.json').read_text())
    dest=ROOT/'.mfcache/hist.json.gz';hist={}
    if dest.exists():
        with gzip.open(dest,'rt') as f:hist=json.load(f)
    for c in s['mf']['selected']:
        k=c['key']
        if len(hist.get(k,[]))>500:continue
        r=requests.get('https://api.mfapi.in/mf/'+k,timeout=90);r.raise_for_status();v=r.json()
        if str(v.get('meta',{}).get('scheme_code'))!=k:raise ValueError('Scheme identity mismatch')
        rows=[(datetime.strptime(x['date'],'%d-%m-%Y').date().toordinal(),float(x['nav'])) for x in v['data']]
        if len(rows)<500:raise ValueError('Insufficient daily history '+k)
        hist[k]=sorted(rows)
    dest.parent.mkdir(exist_ok=True)
    with gzip.open(dest,'wt') as f:json.dump(hist,f)
if __name__=='__main__':run()
