# -*- coding: utf-8 -*-
import re, sys, io, csv, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
lines=open(sys.argv[1],encoding='utf-8').read().split('\n')

CAS_RE=re.compile(r'\b(\d{2,7}-\d{2}-\d)\b')
def rows(a,b):
    for i in range(a-1,b):
        L=lines[i]
        if L.startswith('|'):
            yield i+1, [c.strip() for c in L.strip('|').split('|')]

def collect(a,b,label,thr_idx=None,subgroup=None):
    out=[]
    for ln,c in rows(a,b):
        if not c or c[0].lower()=='stt': continue
        joined=' '.join(c)
        cas=CAS_RE.findall(joined)
        if not cas and not (len(c)>=3 and c[1]): continue
        name_sci=c[1] if len(c)>1 else ''
        name_vn=c[2] if len(c)>2 else ''
        thr=c[thr_idx] if thr_idx is not None and len(c)>thr_idx else ''
        out.append(dict(appendix=label,subgroup=subgroup or '',stt=c[0],name_sci=name_sci,name_vn=name_vn,
                        cas=';'.join(dict.fromkeys(cas)),formula=c[4] if len(c)>4 else '',threshold_kg=thr,src_line=ln))
    return out

recs=[]
recs+=collect(24,64,'I')
recs+=collect(68,860,'II','',None) if False else collect(68,860,'II')
recs+=collect(867,1041,'III',subgroup='Nhóm 1')
recs+=collect(1043,1139,'III',subgroup='Nhóm 2')
recs+=collect(1152,1429,'IV',thr_idx=5,subgroup='Bảng A')

w=csv.DictWriter(open(sys.argv[2],'w',newline='',encoding='utf-8-sig'),fieldnames=list(recs[0].keys()))
w.writeheader(); w.writerows(recs)
from collections import Counter
c=Counter((r['appendix'],r['subgroup']) for r in recs)
for k,v in sorted(c.items()): print(k,v)
print('total',len(recs))
print('with CAS', sum(1 for r in recs if r['cas']))
allcas=set()
for r in recs:
    for x in r['cas'].split(';'):
        if x: allcas.add(x)
print('uniq CAS', len(allcas))
