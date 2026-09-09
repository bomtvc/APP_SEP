# -*- coding: utf-8 -*-
"""Sinh tồn kho MÔ PHỎNG nối tiếp dữ liệu thật, từ ngày cuối của file STOCK tới nay.

    python etl/sinh_ton_kho_mo_phong.py data [den_ngay]

File STOCK của bộ phận vận hành dừng ở 07/04/2026. Script này bịa thêm record cho
quãng còn lại để Dashboard có dữ liệu chạy tới hôm nay.

*** SỐ LIỆU SINH RA KHÔNG PHẢI SỐ LIỆU THẬT. ***
Mọi dòng đều mang `source='mo_phong'` để phân biệt, Dashboard đọc cờ đó và hiện
cảnh báo. Đừng dùng quãng này cho bất kỳ báo cáo nào nộp ra ngoài.

Xóa dữ liệu mô phỏng: đặt `config.MO_PHONG_DEN_NGAY = None` rồi chạy lại
`python etl/run_all.py` — `parse_stock.py` ghi đè `stock_daily.csv` từ Excel gốc
nên dữ liệu bịa biến mất hoàn toàn.

Ba ràng buộc khi sinh:

1. **Không vượt mức đang có.** Mỗi mã bị chặn trên bằng đúng đỉnh lịch sử của
   chính nó, và kéo về mức trung bình 30 ngày gần nhất — quãng mô phỏng vì vậy
   ngang hoặc thấp hơn quãng thật, không bao giờ cao hơn.
2. **Tổng tỉ lệ q/Q của riêng quãng mô phỏng dưới ngưỡng** đặt ở
   `config.MO_PHONG_TY_LE_QQ_TOI_DA`. Xem `_siet_pl_iv`.
3. **Chạy lại cho ra đúng dữ liệu cũ** — seed cố định ở `config.MO_PHONG_SEED`.
   Không có seed thì mỗi lần chạy ETL số trên Dashboard lại nhảy.

LƯU Ý về q/Q toàn kỳ: Điều 33 lấy `q` là đỉnh **trên toàn bộ dữ liệu**, nên thêm
ngày mới chỉ có thể làm tỉ lệ tăng hoặc giữ nguyên, không bao giờ giảm. Ràng buộc
số 2 chỉ đảm bảo quãng mô phỏng KHÔNG đẩy tỉ lệ lên; con số hiển thị trên Dashboard
vẫn là đỉnh lịch sử thật (0,98 ngày 14/01/2026).
"""
import io
import os
import re
import sys
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

CAS_RE = re.compile(r'(\d{2,7}-\d{2}-\d)')

# Dữ liệu thật có nhiều ngày liên tiếp giữ nguyên số (kiểm kê không đổi, cuối tuần).
# Đo trên stock_daily.csv: khoảng 40% cặp ngày liền nhau không đổi giá trị.
P_DUNG_YEN = 0.40
# Lực kéo về mức trung bình gần đây. Thấp quá thì chuỗi trôi tự do rồi đụng trần,
# cao quá thì thành đường thẳng.
LUC_KEO = 0.18


def _ngay(s):
    return pd.Timestamp(s).date()


def _cac_ngay(tu, den):
    n, out = tu, []
    while n <= den:
        out.append(n)
        n += timedelta(days=1)
    return out


def _sinh_mot_ma(lich_su, so_ngay, rng):
    """Bước ngẫu nhiên có kéo về trung bình, chặn trong [0, đỉnh lịch sử]."""
    h = np.asarray(lich_su, dtype=float)
    tran = float(h.max())
    if tran <= 0:
        return [0.0] * so_ngay          # mã tồn 0 suốt kỳ thì giữ nguyên 0

    muc_nham = float(h[-30:].mean())    # mức gần đây, không phải trung bình cả kỳ
    dao_dong = float(np.diff(h).std()) if len(h) > 1 else tran * 0.05
    if dao_dong <= 0:
        dao_dong = tran * 0.05

    x = float(h[-1])
    out = []
    for _ in range(so_ngay):
        if rng.random() >= P_DUNG_YEN:
            x += LUC_KEO * (muc_nham - x) + rng.normal(0, dao_dong)
            x = min(max(x, 0.0), tran)
        out.append(x)
    return out


def _siet_pl_iv(gia_tri, ma_cua_cas, nguong, hang_so, tran_tong):
    """Hạ mức các mã Phụ lục IV cho tới khi q/Q của riêng quãng mô phỏng đạt trần.

    `gia_tri[code]` là list giá trị theo ngày, sửa tại chỗ. `hang_so` là phần đóng
    góp cố định của các mã KHÔNG theo dõi hàng ngày (luôn tính ở mức khai báo lớn
    nhất) — phần này không hạ được nên phải trừ ra khỏi hạn mức trước.

    Một mã có thể chứa nhiều chất Phụ lục IV; khi đó lấy hệ số NHỎ NHẤT trong các
    chất nó thuộc về, để siết chất nào cũng đạt.
    """
    def dinh(cas):
        ma = [c for c in ma_cua_cas[cas] if c in gia_tri]
        if not ma:
            return 0.0
        return float(max(sum(gia_tri[c][i] for c in ma)
                         for i in range(len(gia_tri[ma[0]]))))

    tu_nhien = {c: dinh(c) / nguong[c] for c in ma_cua_cas}
    tong = sum(tu_nhien.values()) + hang_so
    if tong <= tran_tong:
        return tong, {}

    han_muc = tran_tong - hang_so
    tong_tu_nhien = sum(tu_nhien.values())
    he_so_chung = han_muc / tong_tu_nhien if tong_tu_nhien else 1.0

    he_so_ma = {}
    for cas, ma in ma_cua_cas.items():
        for c in ma:
            if c in gia_tri:
                he_so_ma[c] = min(he_so_ma.get(c, 1.0), he_so_chung)
    for c, f in he_so_ma.items():
        gia_tri[c] = [v * f for v in gia_tri[c]]

    tong_moi = sum(dinh(c) / nguong[c] for c in ma_cua_cas) + hang_so
    return tong_moi, he_so_ma


def main(data_dir, den_ngay=None):
    p = lambda n: os.path.join(data_dir, n)
    st = pd.read_csv(p('stock_daily.csv'))
    st['code'] = st.code.str.strip()

    that = st[st.source != 'mo_phong']
    if len(that) != len(st):
        print('  (bỏ %d dòng mô phỏng của lần chạy trước)' % (len(st) - len(that)))
    st = that

    ngay_cuoi = _ngay(st.date.max())
    den = _ngay(den_ngay) if den_ngay else date.today()
    if den <= ngay_cuoi:
        print('Không có gì để sinh: dữ liệu thật đã tới %s.' % ngay_cuoi)
        st.to_csv(p('stock_daily.csv'), index=False, encoding='utf-8-sig')
        return
    ngay_moi = _cac_ngay(ngay_cuoi + timedelta(days=1), den)

    # Chỉ nối tiếp những mã CÓ MẶT ở ngày thật cuối cùng. Mã đã biến khỏi sheet
    # trước đó thì để yên — làm chúng sống lại là bịa thêm một chuyện nữa.
    dong_cuoi = st[st.date == st.date.max()].set_index('code')
    ma_nt = list(dong_cuoi.index)
    lich_su = {c: g.sort_values('date').qty_kg.tolist()
               for c, g in st[st.code.isin(ma_nt)].groupby('code')}

    rng = np.random.default_rng(config.MO_PHONG_SEED)
    gia_tri = {c: _sinh_mot_ma(lich_su[c], len(ngay_moi), rng) for c in sorted(ma_nt)}

    # --- ràng buộc Điều 33 trên riêng quãng mô phỏng ---
    # Dựng lại từ chem_classified.csv chứ KHÔNG đọc pl_iv_threshold.csv: file đó do
    # aggregate.py sinh ra, mà aggregate lại chạy SAU script này — đọc nó thì lần
    # chạy đầu trên máy sạch sẽ chết vì file chưa tồn tại. Logic dưới đây trùng
    # đúng phần đầu `aggregate.main`, nếu sửa bên đó thì sửa cả ở đây.
    dec = pd.read_csv(p('decree_chemicals.csv'), dtype=str).fillna('')
    nguong = {}
    for _, r in dec[dec.appendix == 'IV'].iterrows():
        t = r['threshold_kg'].replace('.', '').replace(' ', '')
        if not t.isdigit():
            continue
        for c in r['cas'].split(';'):
            if c:
                nguong[c] = min(nguong.get(c, float('inf')), float(t))

    cl = pd.read_csv(p('chem_classified.csv')).fillna('')
    theo_doi = set(st.loc[st.source == 'sheet', 'code'])
    ma_cua_cas, hang_so = {}, 0.0
    for _, r in cl[cl.pl_IV].iterrows():
        cs = [c for c in CAS_RE.findall(str(r['cas_raw'])) if c in nguong]
        if not cs:
            continue
        for c in cs:
            if r['code'] in theo_doi:
                ma_cua_cas.setdefault(c, []).append(r['code'])
            else:
                # Mã không theo dõi hàng ngày luôn được tính ở mức khai báo lớn nhất,
                # bất kể ngày nào — phần cố định này không siết được.
                hang_so += float(r['max_stock_kg'] or 0) / nguong[c]

    tong, he_so = _siet_pl_iv(gia_tri, ma_cua_cas, nguong, hang_so,
                              config.MO_PHONG_TY_LE_QQ_TOI_DA)

    # --- dựng record ---
    don_vi = config.UNIT_FACTOR_TO_KG
    rows = []
    for c in sorted(ma_nt):
        mau = dong_cuoi.loc[c]
        nguyen = all(float(v).is_integer() for v in lich_su[c])
        he = don_vi.get(mau['unit'], 1.0) or 1.0
        for ngay, v in zip(ngay_moi, gia_tri[c]):
            kg = round(v) if nguyen else round(v, 1)
            rows.append({
                'date': ngay.isoformat(), 'code': c, 'name': mau['name'],
                'unit_raw': mau['unit_raw'], 'unit': mau['unit'],
                'qty': round(kg / he, 1), 'qty_kg': float(kg),
                # Mọi dòng bịa mang cờ này. aggregate.py chỉ coi source='sheet' là
                # "theo dõi hàng ngày" nên cờ mới không làm lệch phép so ngưỡng.
                'source': 'mo_phong', 'sheet': '', 'cell': '',
            })

    ra = pd.concat([st, pd.DataFrame(rows)], ignore_index=True)
    ra.to_csv(p('stock_daily.csv'), index=False, encoding='utf-8-sig')

    print('DỮ LIỆU MÔ PHỎNG — KHÔNG PHẢI SỐ LIỆU THẬT')
    print('  %d ngày %s -> %s trên %d mã (%d record)'
          % (len(ngay_moi), ngay_moi[0], ngay_moi[-1], len(ma_nt), len(rows)))
    m = pd.DataFrame(rows).groupby('date').qty_kg.sum()
    t = that.groupby('date').qty_kg.sum()
    print('  tổng tồn/ngày: mô phỏng TB %s, đỉnh %s | thật TB %s, đỉnh %s'
          % tuple(format(round(x), ',d') for x in (m.mean(), m.max(), t.mean(), t.max())))
    print('  q/Q của riêng quãng mô phỏng = %.4f (trần %.2f)'
          % (tong, config.MO_PHONG_TY_LE_QQ_TOI_DA))
    if he_so:
        f = min(he_so.values())
        print('    đã hạ %d mã Phụ lục IV còn %.0f%% để đạt trần' % (len(he_so), f * 100))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
