# -*- coding: utf-8 -*-
import zipfile, re, sys, io, os
from xml.etree import ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
z=zipfile.ZipFile(config.SRC_DECREE)
root=ET.fromstring(z.read('word/document.xml'))
body=root.find('w:body',NS)
out=[]
def para_text(p):
    return ''.join(t.text or '' for t in p.iter('{%s}t'%NS['w']))
def walk(el, intable=False):
    for ch in el:
        tag=ch.tag.split('}')[1]
        if tag=='p':
            t=para_text(ch).strip()
            if t: out.append(t)
        elif tag=='tbl':
            for tr in ch.findall('w:tr',NS):
                cells=[]
                for tc in tr.findall('w:tc',NS):
                    ct=' '.join(para_text(p).strip() for p in tc.findall('w:p',NS)).strip()
                    cells.append(ct)
                out.append('| '+' | '.join(cells)+' |')
        elif tag in ('sdt','sdtContent'):
            walk(ch)
walk(body)
open(sys.argv[1],'w',encoding='utf-8').write('\n'.join(out))
print('lines',len(out))
