# -*- coding: utf-8 -*-
"""Hằng số chuẩn hóa của ETL hóa chất, chốt ở bước "Làm sạch và chốt chuẩn".

Mọi quy đổi đơn vị trong hệ thống PHẢI đọc từ file này, không hard-code ở nơi khác.
Khi một hệ số thay đổi, sửa ở đây rồi chạy lại `python etl/run_all.py`.
"""
import os

# --- Quy đổi đơn vị hóa chất -------------------------------------------------
# Chốt ngày 08/09/2026: coi khối lượng riêng trung bình của dung môi/sơn ~ 1 kg/L.
LIT_TO_KG = 1.0

# Các cách viết đơn vị được chấp nhận, ánh xạ về đơn vị chuẩn.
# Giá trị None = ô Unit không chứa đơn vị hợp lệ (bị dùng sai mục đích) -> coi là kg.
UNIT_ALIASES = {
    'kilo': 'kg', 'killo': 'kg', 'kg': 'kg', 'kgm': 'kg', 'kgs': 'kg',
    'lit': 'L', 'liter': 'L', 'litre': 'L', 'l': 'L',
}
UNIT_DEFAULT = 'kg'          # dùng khi ô Unit trống hoặc không phải đơn vị
UNIT_FACTOR_TO_KG = {'kg': 1.0, 'L': LIT_TO_KG}

# --- Quy tắc đọc sheet W06 của STOCK CHEMICAL --------------------------------
# W06 chỉ có 7 cột ngày thật (E:K = 02/02 -> 08/02/2026).
# L và M là công thức VLOOKUP trỏ sang sheet W07 (=VLOOKUP(B,'W07'!$B$4:$E$155,4,0)),
# nên L trùng khớp 100% với W07!E (09/02) và M trả về #REF! do tham chiếu cột 5
# nằm ngoài vùng B:E. N là một ô VLOOKUP lạc. Cả ba KHÔNG chứa dữ liệu gốc.
# => Chỉ đọc E:K. Kiểm chứng: 152/152 mã của W06!L bằng đúng W07!E.
SHEET_COLUMN_LIMIT = {
    'W06': 11,   # cột K
}

# --- Lịch nghỉ nhà máy -------------------------------------------------------
# Xác nhận ngày 08/09/2026: đoạn 10/02 -> 01/03/2026 tồn kho đứng im là do NGHỈ TẾT,
# không phải lỗi copy sheet. Dữ liệu hợp lệ; Dashboard nên tô nền đoạn này để người
# đọc không hiểu nhầm là mất số liệu.
SHUTDOWN_PERIODS = [
    ('2026-02-10', '2026-03-01', 'Nghỉ Tết Bính Ngọ 2026'),
]

# --- Mã không theo dõi tồn hàng ngày ----------------------------------------
# 21 mã có trong danh mục nhưng không nằm trong file STOCK. Xác nhận ngày 08/09/2026:
# tồn kho của chúng bằng 0. ETL sinh đủ 0 cho mọi ngày để danh mục và chuỗi tồn kho
# khớp nhau, đánh dấu source='khai_bao_ton_0' để phân biệt với số liệu đọc từ sheet.
# LƯU Ý: các mã này vẫn khai báo "khối lượng tồn trữ lớn nhất" > 0 trong danh mục;
# khi đối chiếu ngưỡng Phụ lục IV phải dùng con số khai báo đó, không dùng số 0 này.
FILL_ZERO_FOR_UNTRACKED = True

# --- Duyệt rà soát ngưỡng hàm lượng -----------------------------------------
# Đặt ngày duyệt để apply_thresholds.py siết phân loại từ mức "có chứa thành phần"
# xuống mức "đạt ngưỡng hàm lượng" theo đúng Nghị định (PL II > 5%, PL III > 1%).
# Để rỗng thì hệ thống giữ nguyên mức bao trùm, an toàn khi hồ sơ chưa đủ.
# Căn cứ: data/threshold_review.csv, mỗi dòng có cột bằng chứng.
THRESHOLD_REVIEW_APPROVED = '2026-09-08'

# --- Phạm vi thống kê --------------------------------------------------------
# "list hóa chất total 2026.xlsx" là danh mục tham chiếu duy nhất.
# Mã nào không có trong đó thì KHÔNG được đưa vào bất kỳ thống kê nào;
# ETL vẫn ghi lại các mã bị loại vào data/excluded_codes.csv để rà soát.
RESTRICT_TO_MASTER_LIST = True

# --- Dữ liệu mô phỏng — KHÔNG PHẢI SỐ LIỆU THẬT ------------------------------
# File STOCK của bộ phận vận hành dừng ở 07/04/2026. Bật cờ này thì
# `sinh_ton_kho_mo_phong.py` bịa thêm record cho quãng từ đó tới ngày chạy, để
# Dashboard có dữ liệu tới hôm nay. Mọi dòng bịa mang `source='mo_phong'`;
# Dashboard đọc cờ đó và hiện cảnh báo trên đầu màn hình lẫn trên biểu đồ.
#
# ĐẶT `None` LÀ TẮT: chạy lại `python etl/run_all.py` thì `parse_stock.py` ghi đè
# stock_daily.csv từ Excel gốc và dữ liệu bịa biến mất sạch.
# Đặt một chuỗi ngày ('2026-09-09') để dừng ở đúng ngày đó thay vì "hôm nay".
MO_PHONG_DEN_NGAY = 'hom_nay'

# Seed cố định để chạy lại ETL cho ra ĐÚNG dữ liệu cũ. Không có nó thì mỗi lần
# chạy, số trên Dashboard lại nhảy và không ai đối chiếu được với lần trước.
MO_PHONG_SEED = 20260909

# Trần tổng tỉ lệ q/Q (Điều 33) tính trên RIÊNG quãng mô phỏng. Script hạ mức các
# mã Phụ lục IV cho tới khi đạt trần này.
# Lưu ý: q/Q hiển thị trên Dashboard là đỉnh TOÀN KỲ nên vẫn giữ đỉnh lịch sử thật
# (0,98 ngày 14/01/2026); trần ở đây chỉ đảm bảo quãng bịa không đẩy nó lên.
MO_PHONG_TY_LE_QQ_TOI_DA = 0.75

# --- Đường dẫn nguồn ---------------------------------------------------------
# Suy từ vị trí file này, KHÔNG hard-code ổ đĩa: dự án từng được copy sang máy khác
# và mọi đường dẫn 'D:/Code/APP_SEP/...' chết hàng loạt. ROOT = thư mục chứa etl/.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC_CHEM_LIST = os.path.join(ROOT, 'Chemical', 'list hóa chất total 2026.xlsx')
SRC_CHEM_LIST_SHEET = 'Total-GHS'
SRC_STOCK = os.path.join(ROOT, 'Chemical', 'STOCK CHEMICAL( dự trữ) P2 2026.xlsx')
SRC_MSDS_DIR = os.path.join(ROOT, 'Chemical', 'MSDS 176 mã 2026')
SRC_DECREE = os.path.join(ROOT, '24_2026_ND-CP_682556.docx')
