# -*- coding: utf-8 -*-
"""Nạp dữ liệu hóa chất cho Dashboard từ thư mục data/ do ETL sinh ra.

Dashboard chỉ ĐỌC. Mọi biến đổi số liệu nằm ở etl/; nếu một con số trên màn hình
trông sai thì sửa ở ETL rồi chạy lại `python etl/run_all.py`, không vá tại đây.
"""
import os
import sys
import threading
# `ctypes.wintypes` KHÔNG import được ngoài Windows (ném lỗi ngay), nên nó nằm
# trong nhánh `if _WINDOWS` ở cuối file chứ không ở đây.

import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
sys.path.insert(0, os.path.join(ROOT, 'etl'))

import config  # noqa: E402  (cần ROOT/etl trong sys.path trước)
from i18n import t  # noqa: E402

# --- Bảng màu ---------------------------------------------------------------
# Ba màu phân loại (II / III / IV) là slot 1-2-3 của bảng màu tham chiếu dataviz,
# ĐÃ chạy validator chứ không chọn bằng mắt:
#   sáng, nền #fcfcfb : CVD ΔE 9.2 · thị lực thường ΔE 24.0 · #1baf7a 2.74:1
#   tối,  nền #1a1a19 : CVD ΔE 9.4 · thị lực thường ΔE 20.9 · cả 3 trên 3:1
# #1baf7a dưới 3:1 nên biểu đồ đường BẮT BUỘC kèm bảng số liệu (khối "Xem số
# liệu dạng bảng") — đó là kênh đọc thay cho màu, không phải trang trí.
#
# 'Tổng' cố tình KHÔNG lấy màu phân loại: nó là đường nền bối cảnh nên mặc mực
# xám phụ, để ba phụ lục giữ trọn kênh nhận dạng bằng màu.
# Màu phải khớp với `.streamlit/config.toml`. Đổi thì chạy lại validator.
_LIGHT = {
    'toi': False,   # đang ở chế độ tối? quyết định độ đậm sắc nền của thẻ số
    'surface': '#fcfcfb', 'ink': '#0b0b0b', 'ink2': '#52514e', 'muted': '#898781',
    'grid': '#e1e0d9', 'axis': '#c3c2b7', 'border': 'rgba(11,11,11,.10)',
    'total': '#898781', 'II': '#2a78d6', 'III': '#eb6834', 'IV': '#1baf7a',
    'good': '#006300', 'crit': '#d03b3b',
    'seq': ['#cde2fb', '#86b6ef', '#3987e5', '#256abf', '#104281'],
}
_DARK = {
    'toi': True,
    'surface': '#1a1a19', 'ink': '#ffffff', 'ink2': '#c3c2b7', 'muted': '#898781',
    'grid': '#2c2c2a', 'axis': '#383835', 'border': 'rgba(255,255,255,.10)',
    'total': '#898781', 'II': '#3987e5', 'III': '#d95926', 'IV': '#199e70',
    'good': '#0ca30c', 'crit': '#d03b3b',
    # Thang liên tục lật mỏ neo ở nền tối: giá trị nhỏ là bậc TỐI, gần nền nhất.
    'seq': ['#104281', '#256abf', '#3987e5', '#86b6ef', '#cde2fb'],
}


def palette():
    """Bảng màu theo chế độ sáng/tối người dùng đang xem.

    `st.context.theme` có thể trả sai ngay lần vẽ đầu của phiên hoặc đúng lúc
    người dùng đổi theme (streamlit#11920) — lần rerun kế tiếp là đúng lại.
    Không cache: theme đổi thì giá trị phải đổi theo.
    """
    try:
        mode = st.context.theme.type
    except Exception:
        mode = 'light'
    return _DARK if mode == 'dark' else _LIGHT


def _read(name, **kw):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        st.error(t('d.missing', name))
        st.stop()
    return pd.read_csv(path, **kw)


@st.cache_data(show_spinner=False)
def daily():
    d = _read('daily_by_appendix.csv')
    d['date'] = pd.to_datetime(d['date'])
    return d


@st.cache_data(show_spinner=False)
def stock():
    d = _read('fact_stock_enriched.csv')
    d['date'] = pd.to_datetime(d['date'])
    return d


@st.cache_data(show_spinner=False)
def mo_phong():
    """(ngày đầu, ngày cuối) của quãng tồn kho MÔ PHỎNG, hoặc None nếu không có.

    `etl/sinh_ton_kho_mo_phong.py` đánh dấu mọi record bịa bằng `source='mo_phong'`.

    Dashboard hiện KHÔNG dùng hàm này: người dùng chốt ngày 09/09/2026 là "tạm thời
    coi nó là dữ liệu thật", nên băng cảnh báo và vạch ranh giới trên biểu đồ đã gỡ.
    Cờ trong dữ liệu thì vẫn giữ — đây là cách duy nhất để biết quãng nào là số bịa,
    và là chỗ để bật lại cảnh báo khi cần.
    """
    d = stock()
    m = d[d.source == 'mo_phong']
    return None if m.empty else (m.date.min(), m.date.max())


@st.cache_data(show_spinner=False)
def chemicals():
    """Danh mục + phân loại + dữ liệu GHS, gộp về một bảng."""
    cl = _read('chem_classified.csv').fillna('')
    master = _read('chem_master.csv').fillna('')
    extra = [c for c in master.columns
             if c.endswith('_cat') or c.endswith('_h') or c in ('msds_path', 'cas_raw_goc')]
    out = cl.merge(master[['code'] + extra], on='code', how='left')
    if 'cas_raw_goc' not in out.columns:
        out['cas_raw_goc'] = ''
    return out.fillna('')


@st.cache_data(show_spinner=False)
def dieu33():
    """Tỉ lệ q/Q của từng hóa chất Phụ lục IV — Điều 33 NĐ 25/2026/NĐ-CP.

    Sinh bởi `etl/aggregate.py`. Tổng cột `ty_le` chính là vế trái của công thức
    trong Nghị định; >= 1 là phải lập Kế hoạch phòng ngừa, ứng phó sự cố hóa chất.
    """
    return _read('pl_iv_dieu33.csv')


@st.cache_data(show_spinner=False)
def thresholds():
    return _read('pl_iv_threshold.csv')


@st.cache_data(show_spinner=False)
def composition():
    return _read('msds_composition.csv')


@st.cache_data(show_spinner=False)
def excluded():
    """Mã có tồn kho nhưng không nằm trong danh mục tham chiếu — đã bị loại."""
    return _read('excluded_codes.csv')


@st.cache_data(show_spinner=False)
def issues():
    """Nhật ký lỗi dữ liệu do ETL phát hiện."""
    return _read('stock_issues.csv')


@st.cache_data(show_spinner=False)
def threshold_review():
    return _read('threshold_review.csv')


@st.cache_data(show_spinner=False)
def freshness():
    """Ngày dữ liệu mới nhất và ngày duyệt phân loại, để hiện ở đầu trang."""
    d = daily()
    return {
        'tu': d.date.min(),
        'den': d.date.max(),
        'so_ngay': len(d),
        'ngay_duyet': config.THRESHOLD_REVIEW_APPROVED,
    }


def shutdowns():
    """Các kỳ nghỉ nhà máy, để tô nền biểu đồ."""
    return [(pd.Timestamp(a), pd.Timestamp(b), why) for a, b, why in config.SHUTDOWN_PERIODS]


def msds_file(code):
    """Đường dẫn tuyệt đối tới file MSDS của một mã, hoặc None."""
    for ext in ('.pdf', '.doc', '.docx'):
        p = os.path.join(config.SRC_MSDS_DIR, code + ext)
        if os.path.exists(p):
            return p
    return None


# --- OneDrive Files On-Demand ------------------------------------------------
# File "chỉ có trên đám mây" vẫn hiện trong os.listdir và os.path.exists vẫn True,
# nhưng đọc nội dung thì Windows phải tải về. Nếu OneDrive không tải được, lệnh đọc
# treo 60-120 giây rồi ném OSError(22) — trước đây lỗi này không được bắt nên làm
# sập cả trang. Vì vậy KHÔNG BAO GIỜ mở file mà chưa xem thuộc tính trước.
#
# Riêng cờ RECALL_ON_DATA_ACCESS thì CHƯA đủ để kết luận: nó vẫn bật trên file đã
# ghim "Always keep on this device" nhưng OneDrive chưa tải xong. Bằng chứng đo được
# ngày 09/09/2026 trên máy này: cả 177 file MSDS đều mang cờ RECALL và cờ PINNED,
# 176 file có dung lượng thực trên đĩa = 0. Nên phải hỏi thêm dung lượng THỰC:
# GetCompressedFileSizeW trả 0 với placeholder, trả đúng cỡ với file đã tải. Đây là
# lệnh hỏi metadata, không chạm vào dữ liệu nên không kích hoạt tải về.
#
# TOÀN BỘ khối này CHỈ CÓ NGHĨA TRÊN WINDOWS và phải nằm sau cờ `_WINDOWS`. Trước
# đây nó chạy thẳng ở mức module, nên khi deploy lên Streamlit Community Cloud
# (chạy Linux) thì app chết ngay lúc import: `ctypes.windll` không tồn tại ngoài
# Windows, và ngay cả `from ctypes import wintypes` cũng ném lỗi. Ở nơi không phải
# Windows thì không có OneDrive Files On-Demand, mọi file đều là file thật, nên
# `msds_state` trả 'san_sang' luôn.
_RECALL_ON_DATA_ACCESS = 0x00400000
_RECALL_ON_OPEN = 0x00040000
_PINNED = 0x00080000

_WINDOWS = sys.platform == 'win32'

if _WINDOWS:
    import ctypes
    from ctypes import wintypes

    _GetCompressedFileSizeW = ctypes.windll.kernel32.GetCompressedFileSizeW
    _GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    _GetCompressedFileSizeW.restype = wintypes.DWORD

    def _bytes_tren_dia(path):
        """Dung lượng file thực sự chiếm trên đĩa. 0 nghĩa là placeholder rỗng ruột."""
        hi = wintypes.DWORD(0)
        lo = _GetCompressedFileSizeW(os.path.abspath(path), ctypes.byref(hi))
        if lo == 0xFFFFFFFF:
            return None  # không hỏi được thì coi như không biết, đừng chặn người dùng
        return (hi.value << 32) | lo
else:
    def _bytes_tren_dia(path):
        return None


def msds_state(path):
    """('san_sang' | 'cho_tai' | 'tren_may_chu', mô tả) — chỉ đọc thuộc tính.

    cho_tai      : đã ghim giữ máy nhưng OneDrive chưa tải xong.
    tren_may_chu : chưa ghim, đang chỉ nằm trên đám mây.

    Ngoài Windows luôn trả 'san_sang': không có OneDrive Files On-Demand thì không
    có file vỏ rỗng để đề phòng.
    """
    if not _WINDOWS:
        return 'san_sang', ''
    try:
        stt = os.stat(path)
    except OSError as e:
        return 'san_sang', t('d.attr_fail', e)
    attrs = getattr(stt, 'st_file_attributes', 0)
    if not attrs & (_RECALL_ON_DATA_ACCESS | _RECALL_ON_OPEN):
        return 'san_sang', ''
    tren_dia = _bytes_tren_dia(path)
    if tren_dia is None or tren_dia > 0:
        return 'san_sang', ''
    if attrs & _PINNED:
        return 'cho_tai', t('d.pending')
    return 'tren_may_chu', t('d.cloud_only')


def msds_bytes(path, tai_ve=False, giay_cho=90):
    """(nội dung file, lý do không đọc được). Không bao giờ ném lỗi.

    Mặc định từ chối mở placeholder để trang không bị treo. `tai_ve=True` là khi
    người dùng bấm nút xin tải: lúc đó mới mở, và mở trong luồng riêng có hạn giờ —
    nếu OneDrive treo thì luồng đó bị bỏ lại chứ trang vẫn trả lời bình thường.
    """
    trang_thai, ly_do = msds_state(path)
    if trang_thai != 'san_sang' and not tai_ve:
        return None, ly_do
    if trang_thai == 'san_sang':
        try:
            with open(path, 'rb') as fh:
                return fh.read(), ''
        except OSError as e:
            return None, t('d.read_error', e)

    ket_qua = {}

    def _doc():
        try:
            with open(path, 'rb') as fh:
                ket_qua['data'] = fh.read()
        except OSError as e:
            ket_qua['loi'] = t('d.onedrive_error', e)

    luong = threading.Thread(target=_doc, daemon=True)
    luong.start()
    luong.join(giay_cho)
    if luong.is_alive():
        return None, t('d.timeout', giay_cho)
    if 'loi' in ket_qua:
        return None, ket_qua['loi']
    return ket_qua.get('data'), ''


@st.cache_data(show_spinner=False, ttl=30)
def msds_offline_count():
    """(số file chưa tải về, tổng số file) — cache ngắn vì OneDrive tải ngầm."""
    d = config.SRC_MSDS_DIR
    if not os.path.isdir(d):
        return 0, 0
    files = [os.path.join(d, f) for f in os.listdir(d)
             if f.lower().endswith(('.pdf', '.doc', '.docx'))]
    return sum(1 for f in files if msds_state(f)[0] != 'san_sang'), len(files)
