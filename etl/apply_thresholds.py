# -*- coding: utf-8 -*-
"""Áp kết quả rà soát ngưỡng hàm lượng đã được duyệt vào phân loại chính thức.

Trước bước này, phân loại ở mức BAO TRÙM: một mã bị xếp vào phụ lục chỉ vì "có
chứa" thành phần thuộc phụ lục đó, bất kể hàm lượng. Nghị định 24/2026 phân loại
hỗn hợp theo NGƯỠNG hàm lượng (Phụ lục II > 5%, Phụ lục III > 1%), nên sau khi
có đủ dữ liệu hàm lượng và có chữ ký duyệt, phân loại được siết lại cho đúng.

Chỉ chạy khi config.THRESHOLD_REVIEW_APPROVED có ngày duyệt. Cột cũ được giữ
nguyên để đối chiếu, cột mới có hậu tố _chot:

    pl_II      -> pl_II_chot        (kèm can_cu_II ghi lý do)
    pl_III     -> pl_III_chot       (kèm can_cu_III)
    appendices -> appendices_chot

Phụ lục I và IV không đổi: chúng không phân loại theo ngưỡng hàm lượng.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

import config


def main(data_dir):
    p = lambda n: os.path.join(data_dir, n)
    cl = pd.read_csv(p('chem_classified.csv')).fillna('')

    if not config.THRESHOLD_REVIEW_APPROVED:
        cl['pl_II_chot'] = cl.pl_II
        cl['pl_III_chot'] = cl.pl_III
        cl['appendices_chot'] = cl.appendices
        cl['can_cu_II'] = cl['can_cu_III'] = 'chua duyet - giu muc bao trum'
        cl.to_csv(p('chem_classified.csv'), index=False, encoding='utf-8-sig')
        print('Chưa có ngày duyệt trong config.THRESHOLD_REVIEW_APPROVED — giữ mức bao trùm.')
        return

    rv = pd.read_csv(p('threshold_review.csv'))
    pending = rv[rv.trang_thai == 'chua_quyet_duoc']
    if len(pending):
        print('  ! %d dòng còn "chua_quyet_duoc" — vẫn giữ trong phụ lục theo hướng thận trọng:'
              % len(pending))
        for r in pending.itertuples():
            print('      %s / %s' % (r.code, r.phu_luc))

    # loại khỏi phụ lục chỉ khi rà soát kết luận rõ ràng là dưới ngưỡng
    drop = {('II', r.code) if r.phu_luc.endswith('II') and not r.phu_luc.endswith('III')
            else ('III', r.code): r.bang_chung
            for r in rv[rv.trang_thai == 'loai_duoc'].itertuples()}

    def decide(row, pl):
        flag = row['pl_' + pl]
        if not flag:
            return False, ''
        if (pl, row['code']) in drop:
            return False, 'loai theo nguong: ' + str(drop[(pl, row['code'])])[:150]
        return True, 'giu theo nguong'

    out2, out3, cc2, cc3, apx = [], [], [], [], []
    for _, r in cl.iterrows():
        keep2, why2 = decide(r, 'II')
        keep3, why3 = decide(r, 'III')
        out2.append(keep2)
        out3.append(keep3)
        cc2.append(why2)
        cc3.append(why3)
        kept = [a for a, ok in [('I', r['pl_I']), ('II', keep2), ('III', keep3), ('IV', r['pl_IV'])] if ok]
        apx.append(','.join(kept))

    cl['pl_II_chot'], cl['pl_III_chot'] = out2, out3
    cl['can_cu_II'], cl['can_cu_III'] = cc2, cc3
    cl['appendices_chot'] = apx
    cl.to_csv(p('chem_classified.csv'), index=False, encoding='utf-8-sig')

    print('Đã áp rà soát ngưỡng (duyệt ngày %s):' % config.THRESHOLD_REVIEW_APPROVED)
    print('  Phụ lục II : %d -> %d mã (loại %d)' % (
        int(cl.pl_II.sum()), int(cl.pl_II_chot.sum()), int(cl.pl_II.sum() - cl.pl_II_chot.sum())))
    print('  Phụ lục III: %d -> %d mã (loại %d)' % (
        int(cl.pl_III.sum()), int(cl.pl_III_chot.sum()), int(cl.pl_III.sum() - cl.pl_III_chot.sum())))
    gone = cl[(cl.appendices != '') & (cl.appendices_chot == '')]
    print('  Rời khỏi toàn bộ phụ lục: %d mã' % len(gone))
    print('  Phụ lục I và IV không đổi (không phân loại theo ngưỡng hàm lượng).')


if __name__ == '__main__':
    main(sys.argv[1])
