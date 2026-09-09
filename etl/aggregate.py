# -*- coding: utf-8 -*-
"""Ghép tồn kho với phân loại phụ lục và tổng hợp theo ngày.

Đầu ra:
  fact_stock_enriched.csv  - từng dòng tồn kho + cờ phụ lục
  daily_by_appendix.csv    - tổng tồn trữ mỗi ngày, tách theo phụ lục (kg)
  pl_iv_threshold.csv      - 33 mã Phụ lục IV kèm ngưỡng Bảng A áp dụng
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd

CAS_RE = re.compile(r'(\d{2,7}-\d{2}-\d)')
FLAGS = ['pl_I', 'pl_II', 'pl_III', 'pl_IV', 'pl_II_chot', 'pl_III_chot']


def main(data_dir):
    p = lambda n: os.path.join(data_dir, n)
    cl = pd.read_csv(p('chem_classified.csv')).fillna('')
    st = pd.read_csv(p('stock_daily.csv'))
    st['code'] = st.code.str.strip()

    assert not cl.code.duplicated().any(), 'chem_classified.csv có mã trùng lặp'
    df = st.merge(cl[['code'] + FLAGS + ['appendices', 'appendices_chot']], on='code', how='left')
    assert len(df) == len(st), 'join làm thay đổi số dòng — kiểm tra mã trùng lặp'
    assert df.appendices.notna().all(), 'còn mã tồn kho không có trong danh mục tham chiếu'
    df.to_csv(p('fact_stock_enriched.csv'), index=False, encoding='utf-8-sig')

    # pl_II/pl_III là phân loại CHÍNH THỨC (đã áp ngưỡng hàm lượng, đã duyệt);
    # hai cột _bao_trum giữ lại con số trước khi áp ngưỡng để đối chiếu.
    daily = df.groupby('date').apply(lambda s: pd.Series({
        'total': s.qty_kg.sum(),
        'pl_II': s.loc[s.pl_II_chot, 'qty_kg'].sum(),
        'pl_III': s.loc[s.pl_III_chot, 'qty_kg'].sum(),
        'pl_IV': s.loc[s.pl_IV, 'qty_kg'].sum(),
        'pl_II_bao_trum': s.loc[s.pl_II, 'qty_kg'].sum(),
        'pl_III_bao_trum': s.loc[s.pl_III, 'qty_kg'].sum(),
    }), include_groups=False).round(1)
    daily.to_csv(p('daily_by_appendix.csv'), encoding='utf-8-sig')

    print('TỒN TRỮ HÓA CHẤT (kg, đã quy đổi)')
    print('  %d ngày %s -> %s' % (len(daily), daily.index[0], daily.index[-1]))
    for col, label in [('total', 'Tổng'), ('pl_II', 'Phụ lục II'), ('pl_III', 'Phụ lục III'), ('pl_IV', 'Phụ lục IV')]:
        s = daily[col]
        print('  %-12s max %9s (%s) | min %9s | TB %9s' % (
            label, format(round(s.max()), ',d'), s.idxmax(),
            format(round(s.min()), ',d'), format(round(s.mean()), ',d')))

    # --- Phụ lục IV: ngưỡng Bảng A thấp nhất áp dụng cho mỗi mã ---
    dec = pd.read_csv(p('decree_chemicals.csv'), dtype=str).fillna('')
    thr = {}
    for _, r in dec[dec.appendix == 'IV'].iterrows():
        t = r['threshold_kg'].replace('.', '').replace(' ', '')
        if not t.isdigit():
            continue
        for c in r['cas'].split(';'):
            if c:
                thr[c] = min(thr.get(c, float('inf')), float(t))

    peak = df.groupby('code').qty_kg.max()
    tracked = set(df.loc[df.source == 'sheet', 'code'])
    rows = []
    for _, r in cl[cl.pl_IV].iterrows():
        cs = [c for c in CAS_RE.findall(str(r['cas_raw'])) if c in thr]
        code = r['code']
        khai_bao = r['max_stock_kg']
        # Mã không có trong file STOCK được điền tồn = 0; khi so ngưỡng phải dùng
        # khối lượng tồn trữ lớn nhất KHAI BÁO trong danh mục, không dùng số 0 đó.
        co_theo_doi = code in tracked
        rows.append({
            'code': code, 'name': r['name'][:60], 'cas_IV': ','.join(cs),
            'nguong_kg': min(thr[c] for c in cs),
            'ton_dinh_kg': peak.get(code),
            'co_theo_doi_hang_ngay': co_theo_doi,
            'max_khai_bao_kg': khai_bao,
            'ton_de_so_nguong': peak.get(code) if co_theo_doi else khai_bao,
        })
    iv = pd.DataFrame(rows).sort_values('nguong_kg')
    iv['vuot_nguong'] = iv.ton_de_so_nguong.fillna(0) > iv.nguong_kg
    iv.to_csv(p('pl_iv_threshold.csv'), index=False, encoding='utf-8-sig')
    _dieu_33(p, df, iv, thr)
    print('  Phụ lục IV: %d mã | %d mã theo dõi hàng ngày | %d mã vượt ngưỡng' % (
        len(iv), int(iv.co_theo_doi_hang_ngay.sum()), int(iv.vuot_nguong.sum())))
    z = iv[~iv.co_theo_doi_hang_ngay]
    if len(z):
        print('    dùng max khai báo (không theo dõi hàng ngày): %s' % ', '.join(
            '%s=%g kg/ngưỡng %g' % (r.code, r.max_khai_bao_kg, r.nguong_kg) for r in z.itertuples()))


def _dieu_33(p, df, iv, thr):
    """Tổng tỉ lệ khối lượng tồn trữ trên ngưỡng — Điều 33 khoản 2 NĐ 25/2026/NĐ-CP.

        qx1/QUX1 + qx2/QUX2 + ... + qxi/QUXi  >= 1  thì phải lập Kế hoạch
        phòng ngừa, ứng phó sự cố hóa chất.

    Nghị định viết `qxi` là "khối lượng tồn trữ lớn nhất **tại một thời điểm** hóa
    chất nguy hiểm i". Hai chữ "một thời điểm" quyết định con số:

      · gộp theo HÓA CHẤT rồi mới lấy đỉnh (làm ở đây) — đúng câu chữ: với mỗi
        chất, cộng lượng của mọi mã chứa nó theo TỪNG NGÀY rồi mới lấy ngày cao
        nhất;
      · cộng đỉnh riêng của từng mã — sai, vì các mã đạt đỉnh vào những ngày khác
        nhau nên tổng đó mô tả một trạng thái chưa từng tồn tại. Số này vẫn được
        in ra làm cận trên để đối chiếu.

    Vẫn giữ giả định thiên về an toàn của cả dự án: lấy trọn khối lượng sản phẩm,
    không nhân với hàm lượng %. Sản phẩm chứa nhiều chất trong Phụ lục IV thì khối
    lượng đó được tính cho từng chất.
    """
    ngay_q = df[df.code.isin(set(iv.code))][['date', 'code', 'qty_kg']]
    theo_cas = {}
    for r in iv.itertuples():
        for c in str(r.cas_IV).split(','):
            if not c:
                continue
            v = theo_cas.setdefault(c, {'ma': [], 'hang_so': 0.0, 'so_ma': 0})
            v['so_ma'] += 1
            if r.co_theo_doi_hang_ngay:
                v['ma'].append(r.code)
            else:
                # Mã không theo dõi hàng ngày: coi như luôn giữ mức khai báo lớn nhất.
                v['hang_so'] += float(r.max_khai_bao_kg or 0)

    rows = []
    for c, v in sorted(theo_cas.items()):
        s = ngay_q[ngay_q.code.isin(v['ma'])].groupby('date').qty_kg.sum()
        q = (float(s.max()) if len(s) else 0.0) + v['hang_so']
        rows.append({'cas': c, 'so_ma': v['so_ma'], 'q_kg': round(q, 1),
                     'ngay_dinh': s.idxmax() if len(s) else '',
                     'nguong_kg': thr[c], 'ty_le': q / thr[c]})
    d33 = pd.DataFrame(rows).sort_values('ty_le', ascending=False)
    d33.to_csv(p('pl_iv_dieu33.csv'), index=False, encoding='utf-8-sig')

    tong = d33.ty_le.sum()
    can_tren = (iv.ton_de_so_nguong.fillna(0) / iv.nguong_kg).sum()
    print('  Điều 33 NĐ 25/2026 — tổng tỉ lệ q/Q = %.4f (%s 1) trên %d hóa chất'
          % (tong, '>=' if tong >= 1 else '<', len(d33)))
    print('    -> %s lập Kế hoạch phòng ngừa, ứng phó sự cố hóa chất'
          % ('PHẢI' if tong >= 1 else 'chưa phải'))
    print('    cận trên khi cộng đỉnh riêng từng mã (không cùng thời điểm): %.4f' % can_tren)
    cao = d33.iloc[0]
    print('    chất cao nhất: %s = %.0f/%.0f kg (%.0f%% ngưỡng) ngày %s'
          % (cao.cas, cao.q_kg, cao.nguong_kg, cao.ty_le * 100, cao.ngay_dinh))


if __name__ == '__main__':
    main(sys.argv[1])
