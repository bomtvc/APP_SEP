# -*- coding: utf-8 -*-
"""Đối chiếu danh mục hóa chất với Phụ lục I-IV của NĐ 24/2026/NĐ-CP theo số CAS.

Đầu ra: data/chem_classified.csv — mỗi mã kèm cờ phụ lục và chuỗi bằng chứng
(chất nào, CAS nào, ngưỡng bao nhiêu) để người đọc kiểm chứng lại được.

Lưu ý phạm vi: đây mới là bước 1 "có chứa thành phần thuộc phụ lục".
Bước 2 — áp ngưỡng hàm lượng (PL II > 5%, PL III nhóm 1 > 1%) — chưa chạy được vì
danh mục mới ghi % cho một phần nhỏ số dòng CAS.
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd

CONC = re.compile(r'(\d{2,7}-\d{2}-\d)\s*\(([^)]*)\)')


def main(data_dir):
    chem = pd.read_csv(os.path.join(data_dir, 'chem_master.csv')).fillna('')
    dec = pd.read_csv(os.path.join(data_dir, 'decree_chemicals.csv'), dtype=str).fillna('')

    index = {}
    for _, r in dec.iterrows():
        for c in r['cas'].split(';'):
            c = c.strip()
            if c:
                index.setdefault(c, []).append(r)

    out = []
    for _, r in chem.iterrows():
        conc = {m.group(1): m.group(2) for m in CONC.finditer(str(r['cas_raw']))}
        appendices, hits = set(), []
        for c in str(r['cas']).split(';'):
            c = c.strip()
            if not c:
                continue
            for d in index.get(c, []):
                appendices.add(d['appendix'])
                hits.append('%s%s:%s(%s)%s' % (
                    d['appendix'],
                    '/' + d['subgroup'] if d['subgroup'] else '',
                    d['name_vn'] or d['name_sci'], c,
                    ' thr=' + d['threshold_kg'] if d['threshold_kg'] else ''))
        out.append({
            'code': r['code'], 'name': r['name'], 'state': r['state'],
            'max_stock_kg': r['max_stock_kg'], 'cas_raw': r['cas_raw'],
            'pl_I': 'I' in appendices, 'pl_II': 'II' in appendices,
            'pl_III': 'III' in appendices, 'pl_IV': 'IV' in appendices,
            'appendices': ','.join(sorted(appendices, key=['I', 'II', 'III', 'IV'].index)),
            'matches': ' | '.join(sorted(set(hits))),
            'conc': ';'.join('%s=%s' % kv for kv in conc.items()),
        })

    df = pd.DataFrame(out)
    df.to_csv(os.path.join(data_dir, 'chem_classified.csv'), index=False, encoding='utf-8-sig')

    print('Phân loại %d mã:' % len(df))
    for k in ['pl_I', 'pl_II', 'pl_III', 'pl_IV']:
        print('  %-7s %d mã' % (k.replace('pl_', 'Phụ lục '), int(df[k].sum())))
    print('  Không thuộc phụ lục nào: %d mã' % int((df.appendices == '').sum()))


if __name__ == '__main__':
    main(sys.argv[1])
