# -*- coding: utf-8 -*-
"""Kiểm thử Dashboard bằng streamlit.testing — chạy app thật, không mở trình duyệt.

    .venv\\Scripts\\python.exe tests\\test_dashboard.py

Thoát 0 nếu tất cả đạt, 1 nếu có mục không đạt. Kiểm tra:

  1. App khởi động không exception, sidebar đúng 2 màn hình (đã bỏ Tổng quan EHS và
     Chất thải khi thu hẹp phạm vi ngày 09/09/2026). Khóa màn hình là mã bất biến
     ('chemical', 'lookup'), tên hiển thị mới đổi theo ngôn ngữ.
  2. Mỗi màn hình render hết mà không sinh exception hay st.error.
  3. Màn hình Hóa chất còn đủ các khối: đối chiếu ngưỡng Phụ lục IV, ma trận GHS,
     và bảng số liệu kèm biểu đồ đường (khối "Cảnh báo đang mở" đã gỡ 09/09/2026).
     Bảng số liệu là kênh đọc thay cho màu — màu Phụ lục IV dưới 3:1 nên bắt buộc
     phải có, xem mục bảng màu trong CLAUDE.md.
  4. Số hiển thị khớp với data/*.csv — bắt trường hợp ETL và app lệch nhau.
  5. Cả hai màn hình render được ở bản tiếng Anh, và chữ đổi thật chứ không chỉ
     đổi cái nút.

Lưu ý khi đọc kết quả: biểu đồ Altair hiện ra dưới dạng `UnknownElement` vì
streamlit.testing 1.63 chưa có accessor riêng cho vega-lite. Đó là bình thường.
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace',
                              line_buffering=True)

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'app', 'main.py')

FAIL = []


def check(ok, label, detail=''):
    print('  %s  %s%s' % ('PASS' if ok else 'FAIL', label, ('  — ' + detail) if detail else ''))
    if not ok:
        FAIL.append(label)


def no_exception(at, where):
    for e in at.exception:
        print('     !! %s: %s' % (where, str(e.message)[:400]))
    return len(at.exception) == 0


def open_page(page=None, lang='vi'):
    """Dựng app thẳng ở màn hình và ngôn ngữ cần kiểm, chỉ một lượt run.

    Cả hai đều đặt qua session_state chứ không bấm widget: `set_value` trên radio
    khiến AppTest gọi `format_func` NGOÀI ngữ cảnh phiên, lúc đó `i18n.lang()`
    không đọc được session_state nên trả tên tiếng Việt và không khớp danh sách
    lựa chọn tiếng Anh.
    """
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state['_lang_pick'] = lang   # khóa widget chọn ngôn ngữ, xem app/i18n.py
    if page:
        at.session_state['nav'] = page      # khóa radio chọn màn hình trong main.py
    at.run()
    return at


print('=' * 72)
print('1. Khởi động app')
at = open_page()
check(no_exception(at, 'khởi động'), 'app khởi động không exception')

# `.options` trả TÊN HIỂN THỊ đã qua format_func; muốn chuyển màn hình thì
# set_value bằng MÃ màn hình ('chemical' / 'lookup') mà main.py dùng làm khóa.
pages = ['chemical', 'lookup']
ten = list(at.sidebar.radio[0].options) if len(at.sidebar.radio) else []
print('     màn hình trong sidebar: %s' % ten)
check(len(ten) == 2, 'sidebar có đúng 2 màn hình', '%d màn hình' % len(ten))
check(not any('Tổng quan' in x for x in ten), 'không còn màn hình Tổng quan EHS')
check(not any('Chất thải' in x for x in ten), 'không còn màn hình Chất thải')

for page in pages:
    print('=' * 72)
    print('2. Màn hình: %s' % page)
    a = open_page(page)
    check(no_exception(a, page), 'render không exception')

    errs = [str(e.value) for e in a.error]
    check(not errs, 'không có st.error trên trang', '; '.join(x[:120] for x in errs))

    md = ' '.join(str(m.value) for m in a.markdown)
    print('     %d markdown · %d dataframe · %d download_button · %d cảnh báo'
          % (len(a.markdown), len(a.dataframe), len(a.get('download_button')), len(a.warning)))

    if page == 'chemical':
        check('Cảnh báo đang mở' not in md, 'đã gỡ khối "Cảnh báo đang mở"')
        check('Đối chiếu ngưỡng Phụ lục IV' in md, 'có bảng đối chiếu ngưỡng Phụ lục IV')
        check('Ma trận GHS' in md, 'có ma trận GHS')
        nhan = [str(getattr(e, 'label', '')) for e in a.get('expander')]
        check(any('Xem số liệu dạng bảng' in x for x in nhan),
              'có bảng số liệu kèm biểu đồ đường (kênh đọc thay cho màu)')
        check(len(a.dataframe) >= 2, 'render được các bảng dữ liệu',
              '%d dataframe' % len(a.dataframe))

    if page == 'lookup':
        check('Nhãn hóa chất' in md, 'có khối sinh nhãn hóa chất')
        check('Không tìm thấy file MSDS' not in ' '.join(errs),
              'tìm thấy file MSDS (đường dẫn nguồn đúng)')

print('=' * 72)
print('3. Đối chiếu số hiển thị với data/*.csv')
d = pd.read_csv(os.path.join(ROOT, 'data', 'daily_by_appendix.csv'))
a = open_page('chemical')
md = ' '.join(str(m.value) for m in a.markdown)
dinh = f'{d.total.max():,.0f}'.replace(',', '.')
check(dinh in md, 'thẻ "Đỉnh trong kỳ" khớp daily_by_appendix.csv', '%s kg' % dinh)

print('=' * 72)
print('4. Bản tiếng Anh')
# Mỗi màn hình một mốc chữ chỉ có ở bản tiếng Anh, và một mốc chữ tiếng Việt phải
# BIẾN MẤT — nếu chỉ kiểm mốc tiếng Anh thì một trang dịch nửa vời vẫn lọt.
MOC = {'chemical': ('Appendix IV threshold check', 'Đối chiếu ngưỡng Phụ lục IV'),
       'lookup': ('SDS lookup', 'Tra cứu MSDS')}
for page, (en, vi) in MOC.items():
    a = open_page(page, lang='en')
    check(no_exception(a, page + ' EN'), '%s render tiếng Anh không exception' % page)
    md = ' '.join(str(m.value) for m in a.markdown)
    check(en in md, '%s hiện chữ tiếng Anh' % page, en)
    check(vi not in md, '%s không còn sót chữ tiếng Việt' % page, vi)

# Dấu phân cách số phải đảo theo ngôn ngữ: 43.475 kg tiếng Việt -> 43,475 kg tiếng Anh.
a = open_page('chemical', lang='en')
md = ' '.join(str(m.value) for m in a.markdown)
check(f'{d.total.max():,.0f}' in md, 'số dùng dấu phân cách tiếng Anh',
      f'{d.total.max():,.0f} kg')

# session_state trống sạch sau mỗi lần F5, nên ngôn ngữ còn được neo vào URL —
# link `?lang=en` phải mở thẳng ra bản tiếng Anh.
a = AppTest.from_file(APP, default_timeout=180)
a.query_params['lang'] = 'en'
a.run()
md = ' '.join(str(m.value) for m in a.markdown)
check('Chemicals — storage &amp; compliance' in md, 'link ?lang=en mở thẳng bản tiếng Anh')

print('=' * 72)
print('5. Hình đồ GHS chuẩn')
# Nhãn phải dùng bộ ảnh chuẩn trích từ file danh mục, KHÔNG phải bộ vẽ tay dự
# phòng trong app/ghs.py. Thiếu file thì `_anh_chuan()` trả rỗng và nhãn lặng lẽ
# quay về hình vẽ tay — đúng là không sập, nhưng in ra thì sai hình đồ.
sys.path.insert(0, os.path.join(ROOT, 'app'))
import ghs  # noqa: E402

anh = ghs._anh_chuan()
check(len(anh) == 9, 'nạp đủ 9 hình đồ chuẩn từ data/ghs_pictograms', '%d hình' % len(anh))
check(ghs.picto_css().startswith('<style>'), 'sinh được khối CSS hình đồ dùng chung')

# Một mã có 3 hình đồ: nhãn phải tham chiếu class ảnh, không nhúng <svg> vẽ tay.
ch = pd.read_csv(os.path.join(ROOT, 'data', 'chem_classified.csv')).fillna('')
mas = pd.read_csv(os.path.join(ROOT, 'data', 'chem_master.csv')).fillna('')
ch = ch.merge(mas[['code'] + [c for c in mas.columns if c.endswith('_h')]],
              on='code', how='left').fillna('')
r = ch[ch.code == 'CH-06-630'].iloc[0]
hc = ghs.h_codes(r)
nhan = ghs.label_html(r, ghs.pictograms(hc), ghs.signal_word(hc), ghs.statements(hc))
check('class="gp gp-GHS02"' in nhan, 'nhãn dùng ảnh chuẩn chứ không phải hình vẽ tay')
check('<svg viewBox="0 0 64 64"' not in nhan, 'không còn hình đồ vẽ tay trên nhãn')
# Dữ liệu ảnh nằm ở khối CSS dùng chung, nên bản thân nhãn phải rất nhẹ — đây là
# thứ giữ cho file in 176 nhãn ở mức ~0,6 MB thay vì hàng chục MB.
check(len(nhan.encode()) < 6000, 'nhãn không nhúng lại dữ liệu ảnh',
      '%d bytes' % len(nhan.encode()))

print('=' * 72)
if FAIL:
    print('KẾT QUẢ: %d mục KHÔNG ĐẠT' % len(FAIL))
    for f in FAIL:
        print('  - %s' % f)
    sys.exit(1)
print('KẾT QUẢ: TẤT CẢ ĐẠT')
