# -*- coding: utf-8 -*-
"""Suy ra nội dung nhãn hóa chất từ dữ liệu GHS trong danh mục.

Nhãn được dựng từ MÃ H chứ không từ tên cột nhóm nguy hại. Lý do: cột "CHẤT ĂN MÒN"
trong danh mục có mã chứa H319 (kích ứng mắt) — theo GHS phải mang hình dấu chấm
than, không phải hình ăn mòn. Mã H là căn cứ chính xác hơn tên nhóm.

Kết quả là ĐỀ XUẤT. Trước khi in hàng loạt, bộ phận EHS cần đối chiếu lại với
Mục 2 của MSDS gốc.
"""
import base64
import functools
import os
import re

import i18n
from i18n import t

H_CODE = re.compile(r'H\d{3}')

# Bộ hình đồ GHS chuẩn, do `etl/trich_hinh_ghs.py` trích từ file danh mục.
_PICTO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'data', 'ghs_pictograms')

# --- Cảnh báo nguy cơ (H-statements) bằng tiếng Việt ---
H_STATEMENTS = {
    'H221': 'Khí dễ cháy',
    'H225': 'Chất lỏng và hơi rất dễ cháy',
    'H226': 'Chất lỏng và hơi dễ cháy',
    'H227': 'Chất lỏng có thể cháy',
    'H271': 'Có thể gây cháy hoặc nổ; chất oxy hóa mạnh',
    'H280': 'Chứa khí nén; có thể nổ khi bị đốt nóng',
    'H301': 'Độc nếu nuốt phải',
    'H302': 'Có hại nếu nuốt phải',
    'H303': 'Có thể có hại nếu nuốt phải',
    'H304': 'Có thể chết người nếu nuốt phải và đi vào đường thở',
    'H305': 'Có thể có hại nếu nuốt phải và đi vào đường thở',
    'H311': 'Độc khi tiếp xúc với da',
    'H314': 'Gây bỏng da nghiêm trọng và tổn thương mắt',
    'H315': 'Gây kích ứng da',
    'H316': 'Gây kích ứng da nhẹ',
    'H317': 'Có thể gây phản ứng dị ứng da',
    'H318': 'Gây tổn thương mắt nghiêm trọng',
    'H319': 'Gây kích ứng mắt nghiêm trọng',
    'H320': 'Gây kích ứng mắt',
    'H331': 'Độc nếu hít phải',
    'H332': 'Có hại nếu hít phải',
    'H333': 'Có thể có hại nếu hít phải',
    'H334': 'Có thể gây dị ứng, hen suyễn hoặc khó thở nếu hít phải',
    'H335': 'Có thể gây kích ứng hô hấp',
    'H336': 'Có thể gây buồn ngủ hoặc chóng mặt',
    'H350': 'Có thể gây ung thư',
    'H351': 'Nghi ngờ gây ung thư',
    'H360': 'Có thể làm giảm khả năng sinh sản hoặc gây hại cho thai nhi',
    'H361': 'Nghi ngờ làm giảm khả năng sinh sản hoặc gây hại cho thai nhi',
    'H370': 'Gây tổn thương cơ quan',
    'H371': 'Có thể gây tổn thương cơ quan',
    'H372': 'Gây tổn thương cơ quan qua phơi nhiễm kéo dài hoặc lặp lại',
    'H373': 'Có thể gây tổn thương cơ quan qua phơi nhiễm kéo dài hoặc lặp lại',
    'H400': 'Rất độc đối với sinh vật thủy sinh',
    'H401': 'Độc đối với sinh vật thủy sinh',
    'H402': 'Có hại đối với sinh vật thủy sinh',
    'H411': 'Độc đối với sinh vật thủy sinh với ảnh hưởng kéo dài',
    'H412': 'Có hại đối với sinh vật thủy sinh với ảnh hưởng kéo dài',
    'H413': 'Có thể gây ảnh hưởng có hại lâu dài đối với sinh vật thủy sinh',
}

# Câu cảnh báo GHS bản tiếng Anh — dùng nguyên văn của GHS Rev.10, Phụ lục 3.
# Cùng bộ khóa với H_STATEMENTS; thiếu khóa nào thì `statements()` quay về bản
# tiếng Việt chứ không bỏ trống.
H_STATEMENTS_EN = {
    'H221': 'Flammable gas',
    'H225': 'Highly flammable liquid and vapour',
    'H226': 'Flammable liquid and vapour',
    'H227': 'Combustible liquid',
    'H271': 'May cause fire or explosion; strong oxidiser',
    'H280': 'Contains gas under pressure; may explode if heated',
    'H301': 'Toxic if swallowed',
    'H302': 'Harmful if swallowed',
    'H303': 'May be harmful if swallowed',
    'H304': 'May be fatal if swallowed and enters airways',
    'H305': 'May be harmful if swallowed and enters airways',
    'H311': 'Toxic in contact with skin',
    'H314': 'Causes severe skin burns and eye damage',
    'H315': 'Causes skin irritation',
    'H316': 'Causes mild skin irritation',
    'H317': 'May cause an allergic skin reaction',
    'H318': 'Causes serious eye damage',
    'H319': 'Causes serious eye irritation',
    'H320': 'Causes eye irritation',
    'H331': 'Toxic if inhaled',
    'H332': 'Harmful if inhaled',
    'H333': 'May be harmful if inhaled',
    'H334': 'May cause allergy or asthma symptoms or breathing difficulties if inhaled',
    'H335': 'May cause respiratory irritation',
    'H336': 'May cause drowsiness or dizziness',
    'H350': 'May cause cancer',
    'H351': 'Suspected of causing cancer',
    'H360': 'May damage fertility or the unborn child',
    'H361': 'Suspected of damaging fertility or the unborn child',
    'H370': 'Causes damage to organs',
    'H371': 'May cause damage to organs',
    'H372': 'Causes damage to organs through prolonged or repeated exposure',
    'H373': 'May cause damage to organs through prolonged or repeated exposure',
    'H400': 'Very toxic to aquatic life',
    'H401': 'Toxic to aquatic life',
    'H402': 'Harmful to aquatic life',
    'H411': 'Toxic to aquatic life with long lasting effects',
    'H412': 'Harmful to aquatic life with long lasting effects',
    'H413': 'May cause long lasting harmful effects to aquatic life',
}

# --- Mã H -> hình đồ cảnh báo ---
PICTO_OF_H = {
    'GHS02': {'H221', 'H225', 'H226', 'H228', 'H241', 'H242', 'H250', 'H251', 'H252', 'H260', 'H261'},
    'GHS03': {'H270', 'H271', 'H272'},
    'GHS04': {'H280', 'H281'},
    'GHS05': {'H290', 'H314', 'H318'},
    'GHS06': {'H300', 'H301', 'H310', 'H311', 'H330', 'H331'},
    'GHS07': {'H302', 'H312', 'H315', 'H317', 'H319', 'H332', 'H335', 'H336'},
    'GHS08': {'H304', 'H334', 'H340', 'H341', 'H350', 'H351', 'H360', 'H361',
              'H370', 'H371', 'H372', 'H373'},
    'GHS09': {'H400', 'H410', 'H411'},
    'GHS01': {'H200', 'H201', 'H202', 'H203', 'H204', 'H205', 'H209', 'H210', 'H211'},
}
PICTO_NAME = {
    'GHS01': 'Chất nổ', 'GHS02': 'Dễ cháy', 'GHS03': 'Oxy hóa', 'GHS04': 'Khí nén',
    'GHS05': 'Ăn mòn', 'GHS06': 'Độc cấp tính', 'GHS07': 'Kích ứng, có hại',
    'GHS08': 'Nguy hại sức khỏe', 'GHS09': 'Nguy hại môi trường',
}
PICTO_NAME_EN = {
    'GHS01': 'Explosive', 'GHS02': 'Flammable', 'GHS03': 'Oxidising',
    'GHS04': 'Gas under pressure', 'GHS05': 'Corrosive', 'GHS06': 'Acute toxicity',
    'GHS07': 'Irritant, harmful', 'GHS08': 'Health hazard',
    'GHS09': 'Environmental hazard',
}
PICTO_ORDER = ['GHS01', 'GHS02', 'GHS03', 'GHS04', 'GHS05', 'GHS06', 'GHS07', 'GHS08', 'GHS09']

# Mã H buộc dùng từ cảnh báo "NGUY HIỂM"; còn lại là "CẢNH BÁO".
DANGER_H = {
    'H200', 'H201', 'H202', 'H203', 'H204', 'H220', 'H222', 'H224', 'H225', 'H240', 'H241',
    'H250', 'H260', 'H270', 'H271', 'H290', 'H300', 'H301', 'H304', 'H310', 'H311', 'H314',
    'H318', 'H330', 'H331', 'H334', 'H340', 'H350', 'H360', 'H370', 'H372', 'H400',
}

# --- Hình đồ DỰ PHÒNG, vẽ tay ------------------------------------------------
# Chỉ dùng khi chưa trích được bộ ảnh chuẩn (`data/ghs_pictograms/` trống hoặc
# thiếu file). Đây là hình vẽ đơn giản hóa — khung kim cương viền đỏ, nền trắng,
# ký hiệu đen — gần đúng chứ KHÔNG phải hình đồ chuẩn: GHS06 chẳng hạn là mặt tròn
# hai chấm chứ không phải đầu lâu xương chéo thật.
# Chạy `python etl/trich_hinh_ghs.py data` là nhãn tự chuyển sang ảnh chuẩn.
_D = '<path d="M32 3 61 32 32 61 3 32Z" fill="#ffffff" stroke="#d32f2f" stroke-width="4.5"/>'
PICTO_SVG = {
    'GHS01': _D + '<circle cx="32" cy="36" r="8" fill="#111"/><path d="M32 16l3 8-3-2-3 2z" fill="#111"/>'
                  '<path d="M20 22l6 5M44 22l-6 5M32 12v6" stroke="#111" stroke-width="2.4"/>',
    'GHS02': _D + '<path d="M32 15c2.4 6.8-4.2 8.4-4.2 13.9 0 2.1 1.1 3.7 2.6 4.7-.5-2.6.8-4.9 2.6-6'
                  '-.6 3.9 5.5 5.8 5.5 10.3 0 4.2-3.2 7.3-7.3 7.3s-7.4-3.2-7.4-7.8c0-7.1 8.2-10.2 8.2-22.4Z" fill="#111"/>'
                  '<path d="M18 50h28" stroke="#111" stroke-width="3"/>',
    'GHS03': _D + '<circle cx="32" cy="38" r="11" fill="none" stroke="#111" stroke-width="3"/>'
                  '<path d="M32 14c1.8 5-3 6.2-3 10.2 0 1.6.8 2.8 1.9 3.5-.4-1.9.6-3.6 1.9-4.4'
                  '-.5 2.9 4 4.3 4 7.6 0 3-2.3 5.3-5.3 5.3s-5.4-2.4-5.4-5.7c0-5.2 5.9-7.5 5.9-16.5Z" fill="#111"/>',
    'GHS04': _D + '<rect x="25" y="16" width="14" height="32" rx="6" fill="#111"/>'
                  '<rect x="29" y="11" width="6" height="7" fill="#111"/>'
                  '<path d="M18 48h28" stroke="#111" stroke-width="3"/>',
    'GHS05': _D + '<path d="M14 20l10 5v6l-10-4z" fill="#111"/><path d="M50 20l-10 5v6l10-4z" fill="#111"/>'
                  '<path d="M20 33h6l2 10h-10zM38 33h6l2 10h-10z" fill="#111"/>'
                  '<path d="M12 46h40" stroke="#111" stroke-width="3"/>',
    'GHS06': _D + '<circle cx="32" cy="28" r="11" fill="#111"/><circle cx="28" cy="26" r="2.6" fill="#fff"/>'
                  '<circle cx="36" cy="26" r="2.6" fill="#fff"/><path d="M30 33h4v3h-4z" fill="#fff"/>'
                  '<path d="M22 42l20 10M42 42L22 52" stroke="#111" stroke-width="3.4"/>',
    # GHS07 là dấu chấm than trần trong khung kim cương — tam giác là ký hiệu vận
    # chuyển ADR, không thuộc GHS, nên không vẽ.
    'GHS07': _D + '<path d="M28.6 17h6.8l-1.5 22h-3.8z" fill="#111"/>'
                  '<circle cx="32" cy="45.5" r="3.6" fill="#111"/>',
    # GHS08: hình nửa thân người, trên ngực có vết loang hình sao.
    'GHS08': _D + '<circle cx="32" cy="20" r="5.4" fill="#111"/>'
                  '<path d="M32 27c-7.4 0-12.6 4.6-12.6 10.6V50h25.2V37.6C44.6 31.6 39.4 27 32 27Z" fill="#111"/>'
                  '<path d="M32 30.5l2.3 4.7 5.2.8-3.8 3.7.9 5.2-4.6-2.5-4.6 2.5.9-5.2-3.8-3.7 5.2-.8z" fill="#fff"/>',
    'GHS09': _D + '<path d="M12 44c8 0 8-4 16-4s8 4 16 4" stroke="#111" stroke-width="3" fill="none"/>'
                  '<path d="M24 36c-4-6-2-14 4-18 0 6 4 6 6 11 1.6 4-1 8-4 9-2.6.8-5-.6-6-2Z" fill="#111"/>'
                  '<path d="M40 22c2 4 1 9-3 11" stroke="#111" stroke-width="2.4" fill="none"/>',
}

HAZARD_COLUMNS = ['explosive', 'flammable', 'oxidizing', 'gas_pressure',
                  'corrosive', 'toxic', 'health', 'env', 'other']


def h_codes(row):
    """Mọi mã H của một mã hóa chất, giữ nguyên thứ tự xuất hiện."""
    out = []
    for key in HAZARD_COLUMNS:
        for code in H_CODE.findall(str(row.get(key + '_h', '') or '')):
            if code not in out:
                out.append(code)
    return out


def pictograms(codes):
    """Danh sách hình đồ cảnh báo suy ra từ tập mã H."""
    s = set(codes)
    return [p for p in PICTO_ORDER if PICTO_OF_H.get(p, set()) & s]


def picto_name(p):
    """Tên hình đồ cảnh báo theo ngôn ngữ đang xem."""
    return (PICTO_NAME_EN if i18n.lang() == 'en' else PICTO_NAME).get(p, p)


@functools.lru_cache(maxsize=1)
def _anh_chuan():
    """{mã: data URI} bộ hình đồ chuẩn, hoặc {} nếu chưa trích đủ.

    Được-ăn-cả-ngã-về-không: thiếu dù một hình cũng trả {} để cả nhãn quay về bộ
    vẽ tay. Trộn ảnh chuẩn với hình vẽ tay trên cùng một nhãn thì người đọc tưởng
    hai mức cảnh báo khác nhau, trong khi thật ra chỉ là thiếu file.

    Cache vĩnh viễn trong tiến trình: 9 ảnh ~187 KB, đọc và mã hóa base64 lại ở
    mỗi lần rerun thì phí.
    """
    out = {}
    for p in PICTO_ORDER:
        try:
            with open(os.path.join(_PICTO_DIR, p + '.png'), 'rb') as fh:
                out[p] = 'data:image/png;base64,' + base64.b64encode(fh.read()).decode()
        except OSError:
            return {}
    return out


def picto_css():
    """`<style>` khai báo 9 hình đồ MỘT LẦN cho cả trang. '' nếu dùng bộ vẽ tay.

    Phải chèn vào mọi trang có nhãn. Lý do dùng CSS class thay vì `<img src>` ở
    từng nhãn: in hàng loạt 176 mã thì kiểu kia nhúng lại ảnh ở từng nhãn, file
    phình lên hàng chục MB; cách này ảnh chỉ nằm một lần trong trang, ~250 KB bất
    kể bao nhiêu nhãn.
    """
    anh = _anh_chuan()
    if not anh:
        return ''
    return ('<style>.gp{display:inline-block;flex:0 0 auto;background-repeat:no-repeat;'
            'background-position:center;background-size:contain}%s</style>'
            % ''.join('.gp-%s{background-image:url(%s)}' % (k, v)
                      for k, v in sorted(anh.items())))


def signal_word(codes):
    if set(codes) & DANGER_H:
        return t('g.signal.danger')
    return t('g.signal.warning') if codes else ''


def statements(codes):
    """[(mã H, câu cảnh báo)] — mã chưa có trong từ điển vẫn được liệt kê."""
    en = i18n.lang() == 'en'
    out = []
    for c in codes:
        s = (H_STATEMENTS_EN.get(c) if en else None) or H_STATEMENTS.get(c)
        out.append((c, s or t('g.no_statement')))
    return out


def label_html(row, pictos, word, stmts, size='A6'):
    """Nhãn hóa chất dạng HTML, in được từ trình duyệt."""
    w, fs = ('105mm', 1.0) if size == 'A6' else ('148mm', 1.32)
    anh = _anh_chuan()
    if anh:
        # Ảnh chuẩn: chỉ tham chiếu class, dữ liệu ảnh nằm ở `picto_css()`.
        picto_html = ''.join(
            '<span class="gp gp-%s" style="width:%dpx;height:%dpx" role="img" '
            'aria-label="%s" title="%s"></span>'
            % (p, 44 * fs, 44 * fs, picto_name(p), picto_name(p)) for p in pictos)
    else:
        picto_html = ''.join(
            '<svg viewBox="0 0 64 64" width="%d" height="%d"><title>%s</title>%s</svg>'
            % (44 * fs, 44 * fs, picto_name(p), PICTO_SVG[p]) for p in pictos)
    picto_html = picto_html or ('<span style="font-size:11px;color:#666">%s</span>'
                                % t('g.no_picto'))
    lines = ''.join(
        '<div style="margin-bottom:2px"><b>%s</b> %s</div>' % (c, t) for c, t in stmts)
    cas = str(row.get('cas_raw', '') or 'N/A').replace(';', ' · ')
    apx = row.get('appendices_chot', '') or row.get('appendices', '')
    # Dòng phụ dưới tên: thể và mức tồn trữ tối đa khai báo, theo ngôn ngữ đang xem.
    meta = ' · '.join(x for x in (row['code'], i18n.state(row.get('state', '')),
                                  t('g.max_storage', row.get('max_stock_kg', ''))) if x)
    return f"""
<div style="width:{w};border:1.5px solid #111;padding:{10 * fs:.0f}px {12 * fs:.0f}px;
     font-family:'Be Vietnam Pro',Arial,sans-serif;color:#111;background:#fff;box-sizing:border-box">
  <div style="display:flex;gap:10px;align-items:flex-start;border-bottom:1.5px solid #111;padding-bottom:7px">
    <div style="flex:1">
      <div style="font-weight:700;font-size:{13 * fs:.0f}px;line-height:1.25">{row['name']}</div>
      <div style="font-family:monospace;font-size:{10 * fs:.0f}px;color:#555;margin-top:2px">
        {meta}</div>
    </div>
    <div style="display:flex;gap:4px;flex-shrink:0">{picto_html}</div>
  </div>
  <div style="font-weight:700;font-size:{12 * fs:.0f}px;color:#b3261e;letter-spacing:.05em;margin:6px 0 4px">{word}</div>
  <div style="font-size:{10.5 * fs:.0f}px;line-height:1.45">{lines}</div>
  <div style="border-top:1px solid #bbb;margin-top:7px;padding-top:5px;display:flex;
       justify-content:space-between;gap:8px;font-family:monospace;font-size:{9.5 * fs:.0f}px;color:#555">
    <span>CAS {cas[:80]}</span><span>{t('g.appendix', apx.replace(',', '·')) if apx else ''}</span>
  </div>
</div>"""
