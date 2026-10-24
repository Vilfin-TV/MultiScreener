"""Refresh only dip checks/candidates against published inputs; preserve regular plans."""
import json
import sys
from datetime import date
import build_smart_sip as b
import dip_rules as d
from mf_dip_candidates import build
from sim_engine import exit_rule

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    scr=b.load(b.MF/'screener.json'); sip=b.load(b.OUT)
    macro=b.load(b.MF/'macro.json',{}); fpe=b.load(b.MF/'fund_pe.json',{})
    u=b.Universe(scr,date.fromisoformat(scr['asOf']))
    rows=[{k:u.g(c,k) for k in u.cols} for c in u.rows]
    bycode={f['code']:f for f in rows}
    dip=d.mf_block(sip['plans'],bycode.get,lambda c:[f for f in rows if f['sub']==bycode[c]['sub']],
        lambda c:exit_rule(u.info(c).get('exitLoad'),u.g(c,'exitNil')),
        lambda c:b.fund_pe_info(u,c,fpe.get('funds') or {}),macro,sip['market']['gates'],sip['metal']['applied'],scr['asOf'],rows)
    dip['extra']=build(sip['plans'],rows,macro,fpe,u.detail,scr['asOf'])
    sip['dip']=dip
    b.OUT.write_text(json.dumps(sip,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    for seg,e in dip['extra']['plans']['h10a'].items():
        c=dip['extra']['cands'][e['c']]
        print(seg,c['code'],c['name'],str(e['passed'])+'/37', 'fail:', [x[0] for x in dip['extra']['segments'][seg]['checks']+c['checks'] if not x[1]])

if __name__=='__main__': main()
