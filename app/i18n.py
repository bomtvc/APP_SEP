# -*- coding: utf-8 -*-
"""Song ngữ Việt / Anh cho Dashboard.

Mọi chuỗi hiển thị nằm ở `S` bên dưới, khóa dạng `<màn hình>.<chỗ dùng>`. Gọi
`t('c.title')`; muốn chèn tham số thì truyền thêm như `%`: `t('l.hits', 12)`.

Ngôn ngữ đang chọn nằm ngay trong session_state dưới KHÓA CỦA WIDGET chọn ngôn
ngữ (`_lang_pick`). Đọc thẳng khóa widget chứ không giữ một biến riêng, vì
Streamlit gán giá trị widget vào session_state TRƯỚC khi chạy lại script — nhờ
vậy `st.set_page_config(page_title=...)` ở đầu `main.py` đã lấy đúng ngôn ngữ
mới ngay trong lượt rerun đầu tiên, không phải chờ lượt sau.

Số và ngày:
  · `num()` và bảng locale của Vega đổi dấu phân cách theo ngôn ngữ
    (1.234,5 tiếng Việt · 1,234.5 tiếng Anh).
  · Ngày GIỮ NGUYÊN dd/mm/yyyy ở cả hai ngôn ngữ. Không dùng `%b`: tên tháng do
    Vega sinh sẽ là tiếng Anh kể cả khi đang xem bản tiếng Việt (xem CLAUDE.md).
"""
import streamlit as st

LANGS = {'vi': 'VI', 'en': 'EN'}
_DEFAULT = 'vi'
_WIDGET = '_lang_pick'   # khóa của widget chọn ngôn ngữ
_LAST = '_lang_last'     # ngôn ngữ hợp lệ gần nhất, dùng khi widget bị bỏ chọn


def _tu_url():
    """Ngôn ngữ ghi trong URL (`?lang=en`), hoặc None."""
    try:
        q = st.query_params.get('lang')
    except Exception:
        return None
    return q if q in LANGS else None


def lang():
    """Mã ngôn ngữ đang xem: 'vi' hoặc 'en'."""
    v = st.session_state.get(_WIDGET)
    if v in LANGS:
        st.session_state[_LAST] = v
        return v
    # segmented_control cho phép bấm lại để BỎ chọn, lúc đó trả None. Giữ nguyên
    # ngôn ngữ cũ thay vì lặng lẽ rơi về tiếng Việt.
    if _LAST in st.session_state:
        return st.session_state[_LAST]
    # Chưa có phiên nào — F5 hoặc mở link người khác gửi: lấy theo URL.
    return _tu_url() or _DEFAULT


def picker(box=None):
    """Vẽ nút chuyển VI / EN. Đặt TRƯỚC mọi nội dung phụ thuộc ngôn ngữ."""
    (box or st).segmented_control(
        t('lang.label'), list(LANGS), default=lang(), key=_WIDGET,
        format_func=lambda c: LANGS[c], label_visibility='collapsed',
        help='Tiếng Việt / English')
    # session_state mất sạch mỗi lần F5, nên neo lựa chọn vào URL: refresh vẫn
    # giữ ngôn ngữ, và link `?lang=en` gửi cho người khác thì mở ra đã là tiếng
    # Anh. Gán query_params KHÔNG kích hoạt rerun, và chỉ ghi khi thật sự khác
    # để không đụng vào lịch sử trình duyệt mỗi lượt vẽ.
    hien = lang()
    if _tu_url() != hien:
        try:
            st.query_params['lang'] = hien
        except Exception:
            pass


def t(key, *args):
    """Chuỗi hiển thị theo ngôn ngữ đang chọn. Thiếu bản dịch thì quay về tiếng Việt."""
    row = S.get(key)
    if row is None:
        return key
    s = row.get(lang()) or row[_DEFAULT]
    return (s % args) if args else s


def num(x, dec=0):
    """Số theo quy ước của ngôn ngữ đang chọn."""
    s = '{:,.{d}f}'.format(float(x), d=dec)
    if lang() == 'vi':
        s = s.replace(',', '\x00').replace('.', ',').replace('\x00', '.')
    return s


_VEGA = {
    'vi': {'decimal': ',', 'thousands': '.', 'grouping': [3], 'currency': ['', ' đ']},
    'en': {'decimal': '.', 'thousands': ',', 'grouping': [3], 'currency': ['', ' đ']},
}


def vega_number():
    """Bảng locale số cho Altair — xem `chemical._finish`."""
    return _VEGA[lang()]


# --- Giá trị nằm trong data/*.csv, phải dịch lúc hiển thị ---------------------
_STATE = {'LỎNG': 'Liquid', 'RẮN': 'Solid', 'KHÍ': 'Gas'}
_SOURCE = {'msds_pdf': {'vi': 'MSDS (PDF)', 'en': 'SDS (PDF)'},
           'excel': {'vi': 'Excel', 'en': 'Excel'}}
_CAN_CU = [
    ('giu theo nguong', 'kept — a component reaches the threshold'),
    ('loai theo nguong: tat ca thanh phan <= 5%', 'excluded — every component ≤ 5%'),
    ('loai theo nguong: tat ca thanh phan <= 1%', 'excluded — every component ≤ 1%'),
]


def state(v):
    """Thể của hóa chất (cột `state`)."""
    return _STATE.get(str(v).strip(), v) if lang() == 'en' else v


def appendix(v):
    """Giá trị cột `phu_luc` — 'III/Nhóm 1' -> 'III/Group 1'."""
    return str(v).replace('Nhóm', 'Group') if lang() == 'en' else v


def source(v):
    row = _SOURCE.get(str(v).strip())
    return row[lang()] if row else v


def can_cu(v):
    """Cột `can_cu_II` / `can_cu_III` — ETL ghi tiếng Việt không dấu."""
    if lang() != 'en':
        return v
    s = str(v)
    for vi, en in _CAN_CU:
        if s.startswith(vi):
            return en + s[len(vi):]
    return s


S = {
    # ---------- khung app ----------
    'lang.label': {'vi': 'Ngôn ngữ', 'en': 'Language'},
    'app.title': {'vi': 'Hóa chất — tồn trữ & tuân thủ',
                  'en': 'Chemicals — storage & compliance'},
    'nav.screen': {'vi': 'Màn hình', 'en': 'Screen'},
    'page.chemical': {'vi': 'Hóa chất — tồn trữ & tuân thủ',
                      'en': 'Chemicals — storage & compliance'},
    'page.lookup': {'vi': 'Tra cứu MSDS & nhãn', 'en': 'SDS & label lookup'},

    # ---------- loaders ----------
    'd.missing': {'vi': 'Thiếu %s — chạy `python etl/run_all.py` trước.',
                  'en': 'Missing %s — run `python etl/run_all.py` first.'},
    'd.attr_fail': {'vi': 'không đọc được thuộc tính (%s), cứ thử mở',
                    'en': 'could not read file attributes (%s); opening anyway'},
    'd.pending': {'vi': 'đã ghim "Always keep on this device" nhưng OneDrive chưa tải '
                        'xong — file mới chỉ là vỏ rỗng trên máy',
                  'en': 'pinned with "Always keep on this device" but OneDrive has not '
                        'finished downloading — the local file is still an empty stub'},
    'd.cloud_only': {'vi': 'file chỉ có trên OneDrive, chưa tải về máy — bấm chuột phải '
                           'file trong File Explorer rồi chọn "Always keep on this device"',
                     'en': 'the file lives only on OneDrive — right-click it in File '
                           'Explorer and choose "Always keep on this device"'},
    'd.read_error': {'vi': 'lỗi đọc file: %s', 'en': 'read error: %s'},
    'd.onedrive_error': {'vi': 'OneDrive trả lỗi khi tải: %s',
                         'en': 'OneDrive returned an error while downloading: %s'},
    'd.timeout': {'vi': 'OneDrive chưa tải xong sau %d giây — kiểm tra biểu tượng OneDrive '
                        'ở khay hệ thống xem có đang tạm dừng đồng bộ không',
                  'en': 'OneDrive did not finish downloading within %d seconds — check the '
                        'OneDrive tray icon to see whether syncing is paused'},

    # ---------- nút MSDS ----------
    'm.blocked': {'vi': 'Chưa mở được MSDS (%s) — %s.',
                  'en': 'Cannot open the SDS yet (%s) — %s.'},
    'm.fetch': {'vi': 'Tải file này về máy ngay', 'en': 'Download this file now'},
    'm.fetching': {'vi': 'Đang tải %s từ OneDrive…',
                   'en': 'Downloading %s from OneDrive…'},
    'm.failed': {'vi': 'Không tải được MSDS — %s.', 'en': 'Could not fetch the SDS — %s.'},
    'm.open': {'vi': 'Mở MSDS · %s · %.1f MB', 'en': 'Open SDS · %s · %.1f MB'},

    # ---------- màn hình Hóa chất ----------
    'c.title': {'vi': 'Hóa chất — tồn trữ &amp; tuân thủ',
                'en': 'Chemicals — storage &amp; compliance'},
    'c.filter.range': {'vi': 'Khoảng ngày', 'en': 'Date range'},
    'c.filter.appendix': {'vi': 'Phụ lục', 'en': 'Appendix'},
    'c.filter.instock': {'vi': 'Chỉ mã đang có tồn', 'en': 'Only codes in stock'},
    'c.empty': {'vi': 'Không có ngày nào trong khoảng đã chọn.',
                'en': 'No days fall inside the selected range.'},

    'c.tile.last': {'vi': 'Tồn trữ ngày cuối kỳ', 'en': 'Stock on the last day'},
    'c.tile.delta': {'vi': '%s %s kg so với ngày %s', 'en': '%s %s kg versus %s'},
    'c.tile.peak': {'vi': 'Đỉnh trong kỳ', 'en': 'Peak in the period'},
    'c.tile.codes': {'vi': 'Mã đang có tồn', 'en': 'Codes in stock'},
    'c.tile.of_total': {'vi': '/ %d mã', 'en': '/ %d codes'},
    'c.tile.in_range': {'vi': 'trong khoảng đã chọn', 'en': 'in the selected range'},
    'c.tile.threshold': {'vi': 'Ngưỡng Phụ lục IV', 'en': 'Appendix IV threshold'},
    'c.tile.of_over': {'vi': '/ %d mã vượt ngưỡng', 'en': '/ %d codes over threshold'},
    'c.tile.must_plan': {'vi': '▲ phải lập Kế hoạch ứng phó sự cố',
                         'en': '▲ an incident response plan is required'},
    'c.tile.no_plan': {'vi': '✓ chưa phải lập Kế hoạch (Điều 33)',
                       'en': '✓ no plan required yet (Article 33)'},
    'c.tile.ratio': {'vi': 'Tổng tỉ lệ q/Q = <b>%s</b>', 'en': 'Total q/Q ratio = <b>%s</b>'},
    'c.tile.appendix': {'vi': 'Phụ lục %s', 'en': 'Appendix %s'},
    'c.tile.of_instock': {'vi': '/ %d mã có tồn', 'en': '/ %d codes in stock'},
    'c.tile.closing': {'vi': 'tồn cuối kỳ %s kg', 'en': 'closing stock %s kg'},

    'c.chart.daily': {'vi': 'Tồn trữ theo ngày', 'en': 'Stock by day'},
    'c.series.total': {'vi': 'Tổng', 'en': 'Total'},
    'c.tt.date': {'vi': 'Ngày', 'en': 'Date'},
    'c.tt.note': {'vi': 'Ghi chú', 'en': 'Note'},
    'c.table.expander': {'vi': 'Xem số liệu dạng bảng', 'en': 'Show the underlying figures'},

    'c.iv.heading': {'vi': 'Đối chiếu ngưỡng Phụ lục IV',
                     'en': 'Appendix IV threshold check'},
    'c.iv.code': {'vi': 'Mã', 'en': 'Code'},
    'c.iv.name': {'vi': 'Tên hóa chất', 'en': 'Chemical name'},
    'c.iv.threshold': {'vi': 'Ngưỡng (kg)', 'en': 'Threshold (kg)'},
    'c.iv.stock': {'vi': 'Tồn để so (kg)', 'en': 'Stock compared (kg)'},
    'c.iv.pct': {'vi': '% ngưỡng', 'en': '% of threshold'},
    'c.iv.over': {'vi': 'Vượt', 'en': 'Over'},

    'c.d33.expander': {'vi': 'Tổng tỉ lệ q/Q — Điều 33 khoản 2 NĐ 25/2026/NĐ-CP  ·  hiện %s',
                       'en': 'Total q/Q ratio — Article 33(2), Decree 25/2026/ND-CP  ·  now %s'},
    'c.d33.intro': {'vi': 'Phải lập **Kế hoạch phòng ngừa, ứng phó sự cố hóa chất** nếu rơi'
                          ' vào một trong hai trường hợp:',
                    'en': 'A **chemical incident prevention and response plan** is required'
                          ' in either of two cases:'},
    'c.d33.a': {'vi': '- **điểm a** — có ít nhất một hóa chất Bảng A hoặc hỗn hợp Bảng B đạt'
                      ' ngưỡng khối lượng của riêng nó (bảng ngay trên: cao nhất mới %s%%'
                      ' ngưỡng).',
                'en': '- **point a** — at least one Table A chemical or Table B mixture'
                      ' reaches its own mass threshold (in the table above the highest is'
                      ' only %s%% of its threshold).'},
    'c.d33.b': {'vi': '- **điểm b** — nếu không thuộc điểm a thì xét'
                      ' `qx1/QUX1 + qx2/QUX2 + … + qxi/QUXi ≥ 1`.',
                'en': '- **point b** — if point a does not apply, evaluate'
                      ' `qx1/QUX1 + qx2/QUX2 + … + qxi/QUXi ≥ 1`.'},
    'c.d33.now': {'vi': 'Tổng tỉ lệ hiện tại là **%s** — %s',
                  'en': 'The current total ratio is **%s** — %s'},
    'c.d33.reached': {'vi': 'đã tới ngưỡng 1, **phải lập Kế hoạch**.',
                      'en': 'it has reached 1, so **a plan is required**.'},
    'c.d33.below': {'vi': 'còn dưới 1 nên **chưa phải lập Kế hoạch**, nhưng chỉ còn cách'
                          ' ngưỡng %s%%.',
                    'en': 'still below 1, so **no plan is required yet**, but it sits only'
                          ' %s%% short of the threshold.'},
    'c.d33.cas': {'vi': 'Số CAS', 'en': 'CAS number'},
    'c.d33.codes': {'vi': 'Số mã chứa', 'en': 'Codes containing it'},
    'c.d33.q': {'vi': 'q — tồn lớn nhất cùng thời điểm (kg)',
                'en': 'q — largest stock held at one time (kg)'},
    'c.d33.peak_date': {'vi': 'Ngày đỉnh', 'en': 'Peak date'},
    'c.d33.Q': {'vi': 'Q — ngưỡng (kg)', 'en': 'Q — threshold (kg)'},
    'c.d33.ratio': {'vi': 'q/Q', 'en': 'q/Q'},
    'c.d33.declared': {'vi': 'theo khai báo', 'en': 'as declared'},

    'c.top.heading': {'vi': '15 mã tồn cao nhất trong kỳ',
                      'en': 'Top 15 codes by stock in the period'},
    'c.top.name': {'vi': 'Tên', 'en': 'Name'},
    'c.top.peak': {'vi': 'Tồn đỉnh (kg)', 'en': 'Peak stock (kg)'},

    'c.ghs.heading': {'vi': 'Ma trận GHS', 'en': 'GHS matrix'},
    'c.ghs.explosive': {'vi': 'Chất nổ', 'en': 'Explosive'},
    'c.ghs.flammable': {'vi': 'Chất cháy', 'en': 'Flammable'},
    'c.ghs.oxidizing': {'vi': 'Chất oxy hóa', 'en': 'Oxidizing'},
    'c.ghs.gas_pressure': {'vi': 'Khí nén', 'en': 'Gas under pressure'},
    'c.ghs.corrosive': {'vi': 'Chất ăn mòn', 'en': 'Corrosive'},
    'c.ghs.toxic': {'vi': 'Chất độc', 'en': 'Acutely toxic'},
    'c.ghs.health': {'vi': 'Gây hại sức khỏe', 'en': 'Health hazard'},
    'c.ghs.env': {'vi': 'Nguy hại môi trường', 'en': 'Environmental hazard'},
    'c.ghs.other': {'vi': 'Nguy hại khác', 'en': 'Other hazard'},
    'c.ghs.group': {'vi': 'Nhóm', 'en': 'Group'},
    'c.ghs.state': {'vi': 'Thể', 'en': 'State'},
    'c.ghs.count': {'vi': 'Số mã', 'en': 'Codes'},

    'c.one.heading': {'vi': 'Tra cứu một mã', 'en': 'Look up a single code'},
    'c.one.select': {'vi': 'Chọn mã hóa chất', 'en': 'Choose a chemical code'},
    'c.one.state': {'vi': 'Thể: `%s` · Tồn trữ max khai báo: `%s kg`',
                    'en': 'State: `%s` · Max declared storage: `%s kg`'},
    'c.one.appendix': {'vi': 'Phụ lục: **%s**', 'en': 'Appendix: **%s**'},
    'c.one.none': {'vi': 'không thuộc phụ lục nào', 'en': 'not in any appendix'},
    'c.one.before': {'vi': 'Trước khi áp ngưỡng hàm lượng: %s',
                     'en': 'Before the concentration thresholds were applied: %s'},
    'c.one.cas': {'vi': 'Số CAS: `%s`', 'en': 'CAS number: `%s`'},
    'c.one.corrected': {'vi': 'Đã đính chính theo MSDS. Chuỗi gốc: %s',
                        'en': 'Corrected against the SDS. Original string: %s'},
    'c.one.comp': {'vi': '**Hàm lượng thành phần thuộc Phụ lục II/III**',
                   'en': '**Concentration of components in Appendix II/III**'},
    'c.one.no_stock': {'vi': 'Mã này không có tồn kho trong khoảng đã chọn.',
                       'en': 'This code held no stock during the selected range.'},
    'c.one.chart': {'vi': 'Lịch sử tồn kho — %s', 'en': 'Stock history — %s'},
    'c.one.qty': {'vi': 'Tồn (kg)', 'en': 'Stock (kg)'},

    'c.col.cas': {'vi': 'CAS', 'en': 'CAS'},
    'c.col.appendix': {'vi': 'Phụ lục', 'en': 'Appendix'},
    'c.col.conc': {'vi': 'Hàm lượng', 'en': 'Concentration'},
    'c.col.source': {'vi': 'Nguồn', 'en': 'Source'},

    'c.export.heading': {'vi': 'Xuất báo cáo', 'en': 'Export'},
    'c.export.daily': {'vi': 'Tồn trữ theo ngày (khoảng đã lọc)',
                       'en': 'Stock by day (filtered range)'},
    'c.export.daily_file': {'vi': 'ton_tru_theo_ngay_%s_%s.csv',
                            'en': 'stock_by_day_%s_%s.csv'},
    'c.export.iv': {'vi': 'Đối chiếu ngưỡng Phụ lục IV',
                    'en': 'Appendix IV threshold check'},
    'c.export.iv_file': {'vi': 'doi_chieu_nguong_phu_luc_IV.csv',
                         'en': 'appendix_IV_threshold_check.csv'},

    # ---------- màn hình Tra cứu ----------
    'l.title': {'vi': 'Tra cứu MSDS &amp; tạo nhãn', 'en': 'SDS lookup &amp; label builder'},
    'l.intro': {'vi': '176/176 mã có file MSDS trùng khớp với CODE. Tìm theo mã, tên hóa '
                      'chất hoặc số CAS.',
                'en': 'All 176 codes have an SDS file matched by CODE. Search by code, '
                      'chemical name or CAS number.'},
    'l.offline': {'vi': '%d/%d file MSDS mới chỉ là vỏ rỗng OneDrive, chưa tải về máy. Mở '
                        'từng file vẫn được — bấm nút tải khi cần — hoặc chạy '
                        '`python etl\\tai_ve_onedrive.py` để tải sẵn toàn bộ.',
                  'en': '%d of %d SDS files are still OneDrive stubs and have not been '
                        'downloaded. You can still open them one at a time with the '
                        'download button, or run `python etl\\tai_ve_onedrive.py` to fetch '
                        'them all at once.'},
    'l.search': {'vi': 'Tìm kiếm', 'en': 'Search'},
    'l.placeholder': {'vi': 'Ví dụ: CH-06-630 · toluene · 108-88-3',
                      'en': 'For example: CH-06-630 · toluene · 108-88-3'},
    'l.hits': {'vi': '%d mã khớp.', 'en': '%d codes matched.'},
    'l.hits_one': {'vi': '%d mã khớp.', 'en': '%d code matched.'},
    'l.no_hits': {'vi': 'Không tìm thấy mã nào. Thử tìm bằng số CAS hoặc một phần tên.',
                  'en': 'No code matched. Try a CAS number or part of the name.'},
    'l.select': {'vi': 'Chọn mã', 'en': 'Choose a code'},
    'l.summary': {'vi': '`%s` · thể **%s** · tồn trữ tối đa khai báo **%s kg**',
                  'en': '`%s` · **%s** · max declared storage **%s kg**'},
    'l.appendix': {'vi': 'Phụ lục sau khi duyệt: **%s**',
                   'en': 'Appendix after review: **%s**'},
    'l.no_msds': {'vi': 'Không tìm thấy file MSDS cho mã này.',
                  'en': 'No SDS file was found for this code.'},
    'l.not_pdf': {'vi': 'File này ở định dạng .%s — nên chuyển sang PDF để xem trực tiếp '
                        'trên web.',
                  'en': 'This file is a .%s — convert it to PDF to view it in the browser.'},
    'l.comp': {'vi': '**Thành phần thuộc Phụ lục II/III**',
               'en': '**Components in Appendix II/III**'},
    'l.stock': {'vi': '**Tồn kho**: đỉnh %s kg · ngày cuối kỳ %s kg',
                'en': '**Stock**: peak %s kg · last day %s kg'},
    'l.stock_zero': {'vi': '**Tồn kho**: bằng 0 trong toàn bộ kỳ theo dõi.',
                     'en': '**Stock**: zero throughout the tracked period.'},
    'l.label': {'vi': 'Nhãn hóa chất', 'en': 'Chemical label'},
    'l.label_size': {'vi': 'Khổ nhãn', 'en': 'Label size'},
    'l.label_dl': {'vi': 'Tải nhãn để in (HTML)', 'en': 'Download the label to print (HTML)'},
    'l.label_file': {'vi': 'nhan_%s.html', 'en': 'label_%s.html'},
    'l.batch': {'vi': 'In nhãn hàng loạt', 'en': 'Batch label printing'},
    'l.preset': {'vi': 'Chọn nhanh', 'en': 'Quick pick'},
    'l.preset.custom': {'vi': 'Tự chọn', 'en': 'Custom'},
    'l.preset.iv': {'vi': 'Toàn bộ mã thuộc Phụ lục IV', 'en': 'Every Appendix IV code'},
    'l.preset.ii_iii': {'vi': 'Mã thuộc Phụ lục II hoặc III',
                        'en': 'Codes in Appendix II or III'},
    'l.preset.instock': {'vi': 'Mã đang có tồn kho', 'en': 'Codes currently in stock'},
    'l.batch_codes': {'vi': 'Mã cần in', 'en': 'Codes to print'},
    'l.batch_size': {'vi': 'Khổ', 'en': 'Size'},
    # Tiếng Anh phân biệt số ít/số nhiều, tiếng Việt thì không — hai khóa cho
    # cùng một câu, `lookup.render` chọn theo số nhãn đã chọn.
    'l.batch_dl': {'vi': 'Tải %d nhãn để in', 'en': 'Download %d labels to print'},
    'l.batch_dl_one': {'vi': 'Tải %d nhãn để in', 'en': 'Download %d label to print'},
    'l.batch_file': {'vi': 'nhan_hoa_chat_%d_ma.html', 'en': 'chemical_labels_%d_codes.html'},
    'l.print_hint': {'vi': 'Nhấn Ctrl+P để in. Khổ giấy A4, mỗi trang xếp vừa nhiều nhãn.',
                     'en': 'Press Ctrl+P to print. A4 paper; several labels fit on a page.'},

    # ---------- nhãn hóa chất ----------
    'g.signal.danger': {'vi': 'NGUY HIỂM', 'en': 'DANGER'},
    'g.signal.warning': {'vi': 'CẢNH BÁO', 'en': 'WARNING'},
    'g.no_picto': {'vi': 'Không có hình đồ cảnh báo', 'en': 'No hazard pictogram'},
    'g.no_statement': {'vi': '(chưa có câu cảnh báo trong từ điển)',
                       'en': '(no hazard statement in the dictionary yet)'},
    'g.max_storage': {'vi': 'tồn trữ tối đa %s kg', 'en': 'max storage %s kg'},
    'g.appendix': {'vi': 'PL %s', 'en': 'App. %s'},
    'g.label_title': {'vi': 'Nhãn hóa chất', 'en': 'Chemical labels'},
}
