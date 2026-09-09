# -*- coding: utf-8 -*-
r"""Kéo toàn bộ file nguồn từ OneDrive về máy thật.

    python etl\tai_ve_onedrive.py            :: tải những file còn thiếu
    python etl\tai_ve_onedrive.py --kiem-tra :: chỉ đếm, không tải

Vì sao cần: dự án nằm trong OneDrive với Files On-Demand. Chuột phải chọn "Always
keep on this device" chỉ GHIM file (cờ PINNED) chứ không đảm bảo đã tải xong —
OneDrive tải ngầm và có thể chưa chạy tới. File chưa tải vẫn hiện đủ trong
File Explorer, `os.path.exists` vẫn True, `os.path.getsize` vẫn trả đúng cỡ; chỉ
dung lượng THỰC trên đĩa mới lộ ra là vỏ rỗng. ETL đọc phải file như vậy sẽ treo
rồi ném OSError(22).

Cách tải: đọc hết một lượt nội dung file. Đó chính là thứ kích hoạt Windows kéo dữ
liệu về. Không có API nào nhẹ hơn làm được việc này.
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import config  # noqa: E402

_G = ctypes.windll.kernel32.GetCompressedFileSizeW
_G.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
_G.restype = wintypes.DWORD


def bytes_tren_dia(path):
    """Dung lượng thực file chiếm trên đĩa; 0 là placeholder rỗng ruột."""
    hi = wintypes.DWORD(0)
    lo = _G(os.path.abspath(path), ctypes.byref(hi))
    if lo == 0xFFFFFFFF:
        return None
    return (hi.value << 32) | lo


def can_tai(path):
    try:
        co = os.path.getsize(path) > 0
    except OSError:
        return False
    return co and bytes_tren_dia(path) == 0


def nguon():
    """Mọi file ETL cần đọc: hai file Excel, file Nghị định, và thư mục MSDS."""
    ds = [config.SRC_DECREE, config.SRC_CHEM_LIST, config.SRC_STOCK]
    d = config.SRC_MSDS_DIR
    if os.path.isdir(d):
        ds += [os.path.join(d, f) for f in sorted(os.listdir(d))
               if f.lower().endswith(('.pdf', '.doc', '.docx'))]
    return [p for p in ds if p and os.path.exists(p)]


def main():
    chi_kiem_tra = '--kiem-tra' in sys.argv
    ds = nguon()
    thieu = [p for p in ds if can_tai(p)]
    mb = sum(os.path.getsize(p) for p in thieu) / 1e6
    print('%d/%d file còn là vỏ rỗng OneDrive — %.1f MB cần tải.' % (len(thieu), len(ds), mb))
    if chi_kiem_tra or not thieu:
        return 0

    loi, t0 = [], time.time()
    for i, p in enumerate(thieu, 1):
        ten = os.path.basename(p)
        print('  [%3d/%d] %-52s ' % (i, len(thieu), ten[:52]), end='', flush=True)
        t = time.time()
        try:
            with open(p, 'rb') as fh:
                while fh.read(1 << 20):
                    pass
            print('%.1fs' % (time.time() - t))
        except OSError as e:
            loi.append((ten, e))
            print('LỖI: %s' % e)

    print('\nXong sau %.0f giây.' % (time.time() - t0))
    if loi:
        print('%d file không tải được — kiểm tra biểu tượng OneDrive ở khay hệ thống '
              'xem có đang tạm dừng đồng bộ không:' % len(loi))
        for ten, e in loi:
            print('  - %s: %s' % (ten, e))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
