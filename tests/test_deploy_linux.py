# -*- coding: utf-8 -*-
r"""Kiểm app có nạp được trên Linux không — Streamlit Community Cloud chạy Linux.

    .venv\Scripts\python.exe tests\test_deploy_linux.py

Thoát 0 nếu đạt, 1 nếu có mục không đạt.

Vì sao cần: máy phát triển là Windows nên code Windows-only lọt vào rất êm, chạy
local không sao, đẩy lên Cloud mới chết. Ngày 09/09/2026 `app/loaders.py` gọi
`ctypes.windll.kernel32.GetCompressedFileSizeW` ngay ở mức module (đọc dung lượng
thật của file OneDrive) — trên Linux `ctypes.windll` không tồn tại, app chết ngay
lúc import, deploy hỏng.

Phép giả lập dựng lại đúng hai điều kiện của Linux:
  · `sys.platform` = 'linux'
  · `ctypes.wintypes` và `ctypes.windll` không tồn tại

Rồi nạp từng module của `app/` và đọc thử dữ liệu bằng đường dẫn tương đối.

Hạn chế cần biết: đây KHÔNG phải Linux thật. Nó bắt được lỗi import và lỗi dùng
API riêng của Windows, nhưng không bắt được lỗi phân biệt hoa thường trong tên
file (NTFS không phân biệt, ext4 thì có) — phần đó kiểm bằng cách đối chiếu tên
đã commit trong git ở cuối file.
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace',
                              line_buffering=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL = []


def check(ok, label, detail=''):
    print('  %s  %s%s' % ('PASS' if ok else 'FAIL', label, ('  — ' + detail) if detail else ''))
    if not ok:
        FAIL.append(label)


# Chạy trong tiến trình con: phép giả lập làm bẩn sys.platform và sys.modules,
# không nên để nó dính sang phần kiểm tra còn lại.
GIA_LAP = r'''
import sys, os, ctypes, importlib.abc, json

# Nạp sẵn numpy/pandas/streamlit TRƯỚC khi đổi sys.platform: numpy đọc
# sys.platform lúc import và sẽ gọi os.uname() nếu thấy 'linux' — hàm đó không có
# trên Windows. Đó là tác tạo của phép giả lập, không phải lỗi của app.
import numpy, pandas, streamlit, altair, PIL   # noqa: F401

sys.platform = 'linux'


class ChanWintypes(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'ctypes.wintypes':
            raise ImportError("No module named 'ctypes.wintypes'  [gia lap Linux]")
        return None


sys.meta_path.insert(0, ChanWintypes())
if hasattr(ctypes, 'windll'):
    del ctypes.windll
# numpy/streamlit có thể đã nạp ctypes.wintypes từ trước (lúc còn là win32).
# Xoá đi để biết chính xác module nào của app làm nó xuất hiện trở lại.
sys.modules.pop('ctypes.wintypes', None)

os.chdir(ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'app'))

kq = {'loi': {}, 'wintypes': False}
for mod in ['i18n', 'loaders', 'ghs', 'msds_ui', 'chemical', 'lookup']:
    try:
        __import__(mod)
    except Exception as e:
        kq['loi'][mod] = '%s: %s' % (type(e).__name__, e)

kq['wintypes'] = 'ctypes.wintypes' in sys.modules

if 'loaders' not in kq['loi']:
    import loaders
    kq['windows_flag'] = loaders._WINDOWS
    kq['tren_dia'] = loaders._bytes_tren_dia('bat_ky')
    kq['msds_state'] = list(loaders.msds_state('khong_ton_tai'))

print('___KQ___' + json.dumps(kq))
'''


print('=' * 72)
print('1. Nạp app trong môi trường Linux giả lập')
r = subprocess.run([sys.executable, '-c', "ROOT_DIR = %r\n%s" % (ROOT, GIA_LAP)],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
dong = [x for x in (r.stdout or '').splitlines() if x.startswith('___KQ___')]
if not dong:
    print(((r.stdout or '') + (r.stderr or ''))[-1500:])
    check(False, 'chạy được phép giả lập Linux')
else:
    import json
    kq = json.loads(dong[0][len('___KQ___'):])
    for mod in ['i18n', 'loaders', 'ghs', 'msds_ui', 'chemical', 'lookup']:
        check(mod not in kq['loi'], 'import %s' % mod, kq['loi'].get(mod, ''))
    check(not kq['wintypes'], 'không module nào của app đụng tới ctypes.wintypes')
    if 'windows_flag' in kq:
        check(kq['windows_flag'] is False, 'loaders._WINDOWS = False ngoài Windows')
        check(kq['tren_dia'] is None, '_bytes_tren_dia trả None ngoài Windows')
        check(kq['msds_state'][0] == 'san_sang',
              'msds_state coi mọi file là sẵn sàng ngoài Windows',
              str(kq['msds_state']))

print('=' * 72)
print('2. File Streamlit Cloud cần có')
check(os.path.exists(os.path.join(ROOT, 'requirements.txt')),
      'có requirements.txt (Cloud KHÔNG đọc requirements-app.txt)')
req = ''
if os.path.exists(os.path.join(ROOT, 'requirements.txt')):
    req = io.open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8').read()
for goi in ['streamlit', 'pandas', 'altair', 'pillow']:
    check(goi in req, 'requirements.txt khai báo %s' % goi)
check(os.path.exists(os.path.join(ROOT, 'app', 'main.py')), 'có app/main.py làm điểm vào')

print('=' * 72)
print('3. Dữ liệu và tài nguyên đã commit chưa (Cloud chỉ có những gì trong git)')
try:
    # `-z` là bắt buộc: mặc định git ĐỔI tên có ký tự ngoài ASCII thành dạng thoát
    # bát phân trong nháy kép ("Chemical/MSDS 176 m\303\243 2026"), so chuỗi kiểu
    # đó với đường dẫn tiếng Việt trong config thì không bao giờ khớp.
    ra = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True).stdout
    da_commit = set(ra.decode('utf-8').split('\0')) - {''}
except Exception as e:
    da_commit, _ = set(), print('     (không chạy được git: %s)' % e)

CAN = ['data/daily_by_appendix.csv', 'data/fact_stock_enriched.csv',
       'data/chem_classified.csv', 'data/chem_master.csv', 'data/pl_iv_dieu33.csv',
       'data/pl_iv_threshold.csv', 'data/msds_composition.csv',
       'Logo_Mark.png', '.streamlit/config.toml', 'etl/config.py',
       'requirements.txt'] + ['data/ghs_pictograms/GHS0%d.png' % i for i in range(1, 10)]
if da_commit:
    thieu = [f for f in CAN if f not in da_commit]
    check(not thieu, 'mọi file Dashboard cần đều đã commit',
          'thiếu: %s' % ', '.join(thieu[:4]) if thieu else '%d file' % len(CAN))

print('=' * 72)
print('4. Tên file khớp chính xác từng byte')
# Hai cái bẫy chỉ lộ ra trên Linux:
#   · ext4 phân biệt hoa thường, NTFS thì không — sai hoa thường vẫn chạy trên máy;
#   · dấu tiếng Việt có hai cách mã hóa (NFC "ã" một ký tự, NFD "a" + dấu). Nếu
#     chuỗi trong config.py là NFC mà tên git giữ là NFD thì trên Linux `open()`
#     báo không tìm thấy file, trong khi Windows vẫn mở được.
# Vì vậy so với tên GIT đang giữ chứ không so với đĩa.
sys.path.insert(0, os.path.join(ROOT, 'etl'))
import config  # noqa: E402

for ten, duong_dan in [('thư mục MSDS', config.SRC_MSDS_DIR),
                       ('danh mục hóa chất', config.SRC_CHEM_LIST),
                       ('file STOCK', config.SRC_STOCK),
                       ('file Nghị định 24', config.SRC_DECREE)]:
    tuong_doi = os.path.relpath(duong_dan, ROOT).replace('\\', '/')
    trong_git = (tuong_doi in da_commit
                 or any(f.startswith(tuong_doi + '/') for f in da_commit))
    check(trong_git or not da_commit, 'config trỏ đúng tên đã commit: %s' % ten, tuong_doi)

print('=' * 72)
if FAIL:
    print('KẾT QUẢ: %d mục KHÔNG ĐẠT' % len(FAIL))
    for f in FAIL:
        print('  - %s' % f)
    sys.exit(1)
print('KẾT QUẢ: TẤT CẢ ĐẠT — app nạp được trên Linux')
