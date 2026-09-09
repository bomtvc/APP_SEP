# -*- coding: utf-8 -*-
"""Chạy toàn bộ pipeline ETL hóa chất: Excel/Word thô -> CSV record theo ngày trong ../data.

    python etl/run_all.py
"""
import os, subprocess, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ETL  = os.path.join(ROOT, 'etl')
DATA = os.path.join(ROOT, 'data')
RAW  = os.path.join(DATA, 'raw_reports')
os.makedirs(RAW, exist_ok=True)

sys.path.insert(0, ETL)
import config  # noqa: E402

STEPS = [
    ('docx2txt.py',    [os.path.join(RAW, 'nd24_text.txt')]),
    ('parse_decree.py',[os.path.join(RAW, 'nd24_text.txt'), os.path.join(DATA, 'decree_chemicals.csv')]),
    ('parse_chem.py',  [os.path.join(DATA, 'chem_master.csv')]),
    # 9 hình đồ GHS chuẩn nằm sẵn trong chính file danh mục (xlsx là zip).
    ('trich_hinh_ghs.py', [DATA]),
    ('parse_stock.py', [os.path.join(DATA, 'stock_daily.csv'), os.path.join(DATA, 'stock_issues.csv')]),
    ('classify.py',    [DATA]),
    ('extract_conc.py',[DATA]),
    ('apply_thresholds.py', [DATA]),
]

# Nối tồn kho MÔ PHỎNG cho quãng sau ngày cuối của file STOCK. Phải chen vào giữa
# `parse_stock.py` (ghi đè stock_daily.csv từ Excel, xóa sạch dòng mô phỏng cũ) và
# `aggregate.py` (tổng hợp). Đặt `config.MO_PHONG_DEN_NGAY = None` là tắt hẳn.
if config.MO_PHONG_DEN_NGAY:
    den = [] if config.MO_PHONG_DEN_NGAY == 'hom_nay' else [config.MO_PHONG_DEN_NGAY]
    STEPS.append(('sinh_ton_kho_mo_phong.py', [DATA] + den))

STEPS.append(('aggregate.py', [DATA]))

for script, args in STEPS:
    print('\n' + '=' * 70 + '\n>>> ' + script)
    rc = subprocess.call([sys.executable, os.path.join(ETL, script)] + args)
    if rc:
        sys.exit('FAILED: %s (exit %d)' % (script, rc))
print('\nHoàn tất. Kết quả trong', DATA)
