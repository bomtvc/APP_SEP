# -*- coding: utf-8 -*-
"""Đọc "STOCK CHEMICAL( dự trữ) P2 2026.xlsx" -> data/stock_daily.csv.

Chuyển ma trận rộng (mã × ngày) thành record theo ngày, áp các chuẩn đã chốt:

  * W06 chỉ đọc đến cột K — L/M/N là công thức VLOOKUP sang W07, không phải dữ liệu
    gốc (config.SHEET_COLUMN_LIMIT).
  * Đơn vị quy về kg: 1 L = 1 kg (config.LIT_TO_KG). Ô Unit chứa giá trị không phải
    đơn vị ("hết", "170", tên sản phẩm) được coi là kg và ghi nhận vào nhật ký lỗi.
  * Chỉ giữ mã có trong danh mục tham chiếu; mã bị loại ghi ra data/excluded_codes.csv.
"""
import csv
import datetime
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl

import config

MONTHS = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
          'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
TEXT_DATE = re.compile(r'^(\d{1,2})-([A-Za-z]{3})$')


def norm_unit(raw):
    """Trả về (đơn vị chuẩn, hệ số sang kg, ô Unit có hợp lệ không)."""
    key = str(raw).strip().lower() if raw is not None else ''
    if key in config.UNIT_ALIASES:
        u = config.UNIT_ALIASES[key]
        return u, config.UNIT_FACTOR_TO_KG[u], True
    return config.UNIT_DEFAULT, config.UNIT_FACTOR_TO_KG[config.UNIT_DEFAULT], key == ''


def read_master_codes():
    ws = openpyxl.load_workbook(config.SRC_CHEM_LIST, data_only=True)[config.SRC_CHEM_LIST_SHEET]
    return {str(ws.cell(r, 2).value).strip()
            for r in range(4, ws.max_row + 1) if ws.cell(r, 2).value}


def read_master_names():
    ws = openpyxl.load_workbook(config.SRC_CHEM_LIST, data_only=True)[config.SRC_CHEM_LIST_SHEET]
    return {str(ws.cell(r, 2).value).strip(): str(ws.cell(r, 3).value or '').strip()
            for r in range(4, ws.max_row + 1) if ws.cell(r, 2).value}


def main(out_path, issues_path):
    master = read_master_codes() if config.RESTRICT_TO_MASTER_LIST else None
    wb = openpyxl.load_workbook(config.SRC_STOCK, data_only=True)

    records, issues = [], []
    excluded = {}
    bad_unit_codes = {}

    for ws in wb.worksheets:
        sheet = ws.title
        last_col = min(ws.max_column, config.SHEET_COLUMN_LIMIT.get(sheet, ws.max_column))
        if sheet in config.SHEET_COLUMN_LIMIT and ws.max_column > last_col:
            issues.append((sheet, 'cot_bi_cat_theo_quy_tac', 'L:%s' % ws.max_column,
                           'VLOOKUP sang sheet khac, khong phai du lieu goc'))

        # cột -> ngày
        colmap, seen = {}, set()
        for c in range(5, last_col + 1):
            v = ws.cell(3, c).value
            d = None
            if isinstance(v, datetime.datetime):
                d = v.date()
            elif isinstance(v, str):
                m = TEXT_DATE.match(v.strip())
                if m:
                    d = datetime.date(2026, MONTHS[m.group(2).title()], int(m.group(1)))
                    issues.append((sheet, 'ngay_luu_dang_text', ws.cell(3, c).coordinate, v))
            if d is None:
                if v is not None:
                    issues.append((sheet, 'header_khong_phai_ngay', ws.cell(3, c).coordinate, str(v)[:40]))
                continue
            if d in seen:
                issues.append((sheet, 'ngay_trung_lap', ws.cell(3, c).coordinate, str(d)))
                continue
            seen.add(d)
            colmap[c] = d

        for r in range(4, ws.max_row + 1):
            code = ws.cell(r, 2).value
            if not code:
                continue
            code = str(code).strip()

            if master is not None and code not in master:
                e = excluded.setdefault(code, {'name': str(ws.cell(r, 3).value or '').strip(), 'n': 0})
                e['n'] += sum(1 for c in colmap if ws.cell(r, c).value is not None)
                continue

            name = str(ws.cell(r, 3).value or '').strip()
            unit_raw = ws.cell(r, 4).value
            unit, factor, ok = norm_unit(unit_raw)
            if not ok:
                bad_unit_codes[code] = unit_raw

            for c, d in colmap.items():
                v = ws.cell(r, c).value
                if v is None:
                    continue
                if isinstance(v, str):
                    if v.startswith('#'):
                        issues.append((sheet, 'loi_cong_thuc', ws.cell(r, c).coordinate, v))
                        continue
                    try:
                        v = float(v.strip().replace(',', ''))
                    except ValueError:
                        issues.append((sheet, 'khong_phai_so', ws.cell(r, c).coordinate, repr(v)[:40]))
                        continue
                records.append({
                    'date': d.isoformat(), 'code': code, 'name': name,
                    'unit_raw': unit_raw, 'unit': unit,
                    'qty': v, 'qty_kg': round(v * factor, 3), 'source': 'sheet',
                    'sheet': sheet, 'cell': ws.cell(r, c).coordinate,
                })

    # --- điền tồn = 0 cho các mã có trong danh mục nhưng không nằm trong file STOCK ---
    all_dates = sorted({r['date'] for r in records})
    tracked = {r['code'] for r in records}
    untracked = sorted((master or set()) - tracked)
    if config.FILL_ZERO_FOR_UNTRACKED:
        names = read_master_names()
        for code in untracked:
            for d in all_dates:
                records.append({
                    'date': d, 'code': code, 'name': names.get(code, ''),
                    'unit_raw': None, 'unit': config.UNIT_DEFAULT,
                    'qty': 0, 'qty_kg': 0.0, 'source': 'khai_bao_ton_0',
                    'sheet': '', 'cell': '',
                })

    with open(out_path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=['date', 'code', 'name', 'unit_raw', 'unit',
                                           'qty', 'qty_kg', 'source', 'sheet', 'cell'])
        w.writeheader()
        w.writerows(records)

    with open(issues_path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['sheet', 'loi', 'o', 'gia_tri'])
        w.writerows(issues)

    excl_path = os.path.join(os.path.dirname(out_path), 'excluded_codes.csv')
    with open(excl_path, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['code', 'ten_trong_file_stock', 'so_record_bi_loai', 'ly_do'])
        for code, info in sorted(excluded.items()):
            w.writerow([code, info['name'], info['n'], 'Khong co trong list hoa chat total 2026'])

    dates = sorted({r['date'] for r in records})
    d0 = datetime.date.fromisoformat(dates[0])
    d1 = datetime.date.fromisoformat(dates[-1])
    span = (d1 - d0).days + 1
    missing = sorted(set((d0 + datetime.timedelta(days=i)).isoformat() for i in range(span)) - set(dates))

    print('Record: %d | Mã: %d | Ngày: %d (%s -> %s)' % (
        len(records), len({r['code'] for r in records}), len(dates), dates[0], dates[-1]))
    if config.FILL_ZERO_FOR_UNTRACKED and untracked:
        print('Điền tồn = 0 cho %d mã không có trong file STOCK (%d record): %s' % (
            len(untracked), len(untracked) * len(all_dates), ', '.join(untracked)))
    for a, b, why in config.SHUTDOWN_PERIODS:
        n = len([d for d in dates if a <= d <= b])
        print('Kỳ nghỉ đã xác nhận: %s -> %s (%d ngày) — %s' % (a, b, n, why))
    print('Ngày thiếu trong khoảng: %d %s' % (len(missing), missing if missing else ''))
    print('Loại khỏi thống kê: %d mã / %d record  -> %s' % (
        len(excluded), sum(i['n'] for i in excluded.values()), os.path.basename(excl_path)))
    if excluded:
        print('  ' + ', '.join(sorted(excluded)))
    if bad_unit_codes:
        print('Ô Unit không phải đơn vị (đã coi là kg): %d mã -> %s' % (
            len(bad_unit_codes), ', '.join('%s=%r' % (k, v) for k, v in sorted(bad_unit_codes.items()))))
    lit = {r['code'] for r in records if r['unit'] == 'L'}
    print('Mã tính bằng lít, quy đổi 1 L = %g kg: %s' % (config.LIT_TO_KG, ', '.join(sorted(lit)) or 'không có'))
    print('Nhật ký lỗi: %d dòng' % len(issues))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
