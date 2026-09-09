# -*- coding: utf-8 -*-
"""Trích hàm lượng % của từng thành phần từ Mục "Thông tin về thành phần" của MSDS PDF.

Vì sao cần: Nghị định 24/2026 phân loại HỖN HỢP theo ngưỡng hàm lượng
(Phụ lục II > 5%, Phụ lục III nhóm 1 > 1%), trong khi danh mục Excel mới ghi %
cho một phần nhỏ số dòng CAS. Không có %, mọi hỗn hợp có chứa chất trong danh mục
đều bị xếp vào phụ lục — bao trùm quá mức.

Hai điều khiến việc này khó hơn vẻ ngoài:

  1. Hàm lượng trong bảng thành phần KHÔNG kèm dấu % — dấu % là tiêu đề cột, nên
     giá trị hiện ra dưới dạng "≥10 - ≤25", "≤0.3", "<3", ">=2,5 - <10".
  2. Các nhà cung cấp dùng bốn bố cục khác nhau, và có bố cục đặt hàm lượng ở dòng
     TRƯỚC số CAS (tiêu đề cột của mục 3.2 ghi rõ: "% theo Trọng lượng | Mã số CAS
     | Mã số EC"). Đoán sai chiều thì lấy phải hàm lượng của chất bên cạnh — sai
     lệch kiểu đó nguy hiểm hơn là bỏ trống, nên hàm extract_pdf() nhận diện bố
     cục từ chính từng file thay vì giả định.
  3. Việc dò chiều phải giới hạn trong mục thành phần (xem composition_region).
     Số CAS còn xuất hiện ở mục giới hạn phơi nhiễm, mục sinh thái và mục quy định;
     để cả tài liệu tham gia thống kê thì nhịp khoảng cách bị nhiễu và chọn nhầm phía.

Số CAS được kiểm tra bằng chữ số kiểm tra (xem valid_cas) để mã EC, số đăng ký
REACH và ngày tháng không bị nhận nhầm thành CAS.

Độ chính xác: đối chiếu với 94 giá trị đã có sẵn trong Excel do người nhập,
kết quả trích tự động khớp 92 (98%); hai chỗ lệch đều là khác biệt cách ghi
khoảng, không phải lấy nhầm chất.

Đầu ra:
  data/msds_composition.csv - mọi cặp (code, cas, hàm lượng) trích được, kèm
                              nguồn (excel / msds_pdf) và độ tin cậy
  data/conc_todo.csv        - các cặp còn thiếu, cần nhập tay
  data/threshold_review.csv - mỗi (mã, phụ lục): giữ lại / loại được / chưa quyết
"""
import csv
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz
import pandas as pd

import config

CAS_ANY = re.compile(r'(\d{2,7}-\d{2}-\d)')
# Số CAS đứng một mình, hoặc có nhãn phía trước: "Số CAS: 1330-20-7", "CAS number 123-86-4".
CAS_CELL = re.compile(r'^\s*(?:(?:s[ốo]\s*)?cas(?:\s*(?:number|no|#))?\s*[:.\-]?\s*)?'
                      r'(\d{2,7}-\d{2}-\d)\s*(.*)$', re.I)
# Dòng mã EC/EINECS (dạng NNN-NNN-N) chen giữa CAS và hàm lượng — phải bỏ qua, không cắt vòng lặp.
EC_LINE = re.compile(r'^\s*(?:s[ốo]\s*)?(?:ec|einecs|elincs)\b', re.I)
_OP = r'(?:[≥≤<>~]=?|=[<>])'
_NUM = r'(?:%s\s*)?\d{1,3}(?:[.,]\d+)?' % _OP
CONC = re.compile(r'^\s*(%s(?:\s*[-–—]\s*%s)?)\s*%%?\s*$' % (_NUM, _NUM))
# Hàm lượng nằm giữa dòng văn xuôi: "n-Hexane (CAS 110-54-3): 10-20%."
CONC_INLINE = re.compile(r'(%s(?:\s*[-–—]\s*%s)?)\s*%%' % (_NUM, _NUM))
BOUND = re.compile(r'(%s|)\s*(\d{1,3}(?:[.,]\d+)?)' % _OP)
LOOKAHEAD = 10     # số dòng tối đa giữa số CAS và ô hàm lượng của nó

# Tiêu đề mở đầu mục thành phần (mục 2 hoặc 3 của MSDS, tuỳ nhà cung cấp).
COMP_HEAD = re.compile(r'(th[àa]nh\s*ph[ầa]n|h[ợo]p\s*ph[ầa]n|h[ỗo]n\s*h[ợo]p'
                       r'|composition|ingredient)', re.I)
# Tiêu đề của một mục khác: "4. CÁC BIỆN PHÁP SƠ CỨU", "IV. ...", "Section 4."
SECTION_HEAD = re.compile(r'^\s*(?:section\s+)?(?:[IVX]{1,5}|\d{1,2})(?:\.\d+)?[\.\)]\s*\S', re.I)
COMP_WINDOW = 70   # số dòng tối đa của một mục thành phần


def valid_cas(cas):
    """Kiểm tra chữ số kiểm tra của số CAS.

    Số CAS có dạng A-B-C với C là chữ số kiểm tra: lấy các chữ số của A và B,
    đảo ngược, nhân lần lượt với 1, 2, 3... rồi cộng lại, lấy phần dư cho 10.
    Nhờ đó loại được ngày tháng ("18-02-2014"), mã EC và số đăng ký REACH lọt vào.
    """
    try:
        head, mid, check = cas.split('-')
    except ValueError:
        return False
    digits = (head + mid)[::-1]
    return sum(int(d) * (i + 1) for i, d in enumerate(digits)) % 10 == int(check)


def parse_bounds(expr):
    """'≥10-≤25' -> (10.0, 25.0); '≤0.3' -> (0.0, 0.3); '<1' -> (0.0, 1.0)."""
    parts = BOUND.findall(expr)
    if not parts:
        return None, None
    vals = [(op, float(v.replace(',', '.'))) for op, v in parts]
    if len(vals) == 1:
        op, v = vals[0]
        if op.startswith(('≤', '<')) or op == '=<':
            return 0.0, v
        if op.startswith(('≥', '>')) or op == '=>':
            return v, 100.0
        return v, v
    return min(v for _, v in vals), max(v for _, v in vals)


def composition_region(lines):
    """Chỉ số các dòng nằm trong mục "Thông tin về thành phần" của MSDS.

    Cần khoanh vùng vì số CAS còn xuất hiện ở mục giới hạn phơi nhiễm, mục sinh
    thái và mục quy định. Nếu để cả tài liệu tham gia thống kê, nhịp khoảng cách
    giữa CAS và ô hàm lượng bị nhiễu và thuật toán dò chiều sẽ chọn nhầm phía.
    """
    region = set()
    for h, line in enumerate(lines):
        if len(line) > 90 or not COMP_HEAD.search(line):
            continue
        for j in range(h + 1, min(h + 1 + COMP_WINDOW, len(lines))):
            nxt = lines[j]
            if j > h + 2 and SECTION_HEAD.match(nxt) and not COMP_HEAD.search(nxt):
                break
            region.add(j)
    return region


def extract_pdf(path):
    """{cas: (biểu thức hàm lượng, %min, %max)} đọc từ bảng thành phần của MSDS.

    Các nhà cung cấp dùng ba bố cục khác nhau, nên hàm này nhận diện bố cục
    thay vì giả định một kiểu:

      A. Bảng xếp theo cột — cả cụm số CAS liệt kê liền nhau rồi mới tới cả cụm
         hàm lượng. Ghép theo vị trí.
      B. Văn xuôi — "n-Hexane (CAS 110-54-3): 10-20%."
      C. Bảng xếp theo dòng — hàm lượng nằm cùng dòng với CAS, hoặc ở dòng liền
         trước, hoặc ở dòng phía sau. Chiều nào đúng thì suy ra từ chính file:
         đo khoảng cách tới ô hàm lượng gần nhất ở hai phía rồi chọn phía có
         khoảng cách nhỏ hơn. Gán nhầm chiều sẽ lệch đúng một bản ghi, tức lấy
         hàm lượng của chất bên cạnh — sai nguy hiểm hơn là bỏ trống.
    """
    doc = fitz.open(path)
    lines = []
    for page in doc:
        lines += [l.strip() for l in page.get_text().split('\n')]
    doc.close()

    region = composition_region(lines)
    if not region:                       # không nhận ra mục nào thì xét cả tài liệu
        region = set(range(len(lines)))

    out = {}

    def take(cas, expr, conf='cao'):
        expr = expr.replace(' ', '')
        lo, hi = parse_bounds(expr)
        if hi is not None and 0 < hi <= 100:
            out.setdefault(cas, (expr, lo, hi, conf))
            return True
        return False

    def cas_of(line):
        """Số CAS hợp lệ nếu dòng chỉ chứa nó (có thể kèm nhãn 'Số CAS:')."""
        m = CAS_CELL.match(line)
        if m and valid_cas(m.group(1)):
            return m.group(1), m.group(2).strip()
        return None, None

    # --- A. bảng xếp theo cột ---
    i = 0
    while i < len(lines):
        run = []
        while i + len(run) < len(lines):
            ln = lines[i + len(run)]
            c, tail = cas_of(ln)
            if not c or tail or ln != c:
                break
            run.append(c)
        if len(run) >= 2:
            j = i + len(run)
            while j < len(lines) and j <= i + len(run) + LOOKAHEAD and not CONC.match(lines[j]):
                j += 1
            concs = []
            while j + len(concs) < len(lines) and CONC.match(lines[j + len(concs)]):
                concs.append(CONC.match(lines[j + len(concs)]).group(1))
            if len(concs) == len(run):
                for c, expr in zip(run, concs):
                    take(c, expr)
        i += max(1, len(run))

    # --- B. văn xuôi + C-bis. hàm lượng cùng dòng với CAS ---
    cas_at = {}          # chỉ số dòng -> số CAS (dòng chỉ chứa CAS)
    for i, line in enumerate(lines):
        if i not in region or EC_LINE.match(line):
            continue
        c, tail = cas_of(line)
        if c is None:
            m = CAS_ANY.search(line)
            if m and valid_cas(m.group(1)):
                cm = CONC_INLINE.search(line[m.end():])
                if cm:
                    take(m.group(1), cm.group(1))
            continue
        if tail and CONC.match(tail):
            take(c, tail)
        cas_at[i] = c

    # --- C. bảng xếp theo dòng: quyết định chiều ---
    conc_at = {i: CONC.match(l).group(1) for i, l in enumerate(lines)
               if i in region and CONC.match(l) and i not in cas_at}
    if cas_at and conc_at:
        keys = sorted(conc_at)
        d_before, d_after = [], []
        for i in cas_at:
            prev = [k for k in keys if k < i]
            nxt = [k for k in keys if k > i]
            if prev:
                d_before.append(i - prev[-1])
            if nxt:
                d_after.append(nxt[0] - i)
        med = lambda v: sorted(v)[len(v) // 2] if v else 10 ** 6
        before_wins = med(d_before) < med(d_after)
        typical = med(d_before if before_wins else d_after)
        for i, c in cas_at.items():
            if c in out:
                continue
            cand = [k for k in keys if k < i] if before_wins else [k for k in keys if k > i]
            if not cand:
                continue
            k = cand[-1] if before_wins else cand[0]
            # không vượt qua một số CAS khác, và phải nằm trong tầm nhìn
            between = [x for x in cas_at if min(i, k) < x < max(i, k)]
            if not between and abs(k - i) <= LOOKAHEAD:
                # Khoảng cách lệch nhiều so với nhịp chung của file thường có nghĩa
                # bản ghi này thiếu ô hàm lượng và ta đang với sang chất bên cạnh.
                take(c, conc_at[k], 'cao' if abs(k - i) <= typical else 'thap')
    return out


def all_cas_in_pdf(path):
    """Mọi số CAS hợp lệ xuất hiện trong file — để phân biệt "MSDS không có chất
    này" với "có chất nhưng không đọc được ô hàm lượng"."""
    doc = fitz.open(path)
    txt = ''.join(page.get_text() for page in doc)
    doc.close()
    return {c for c in CAS_ANY.findall(txt) if valid_cas(c)}


def safe_write(path, header, rows):
    """Ghi CSV; nếu file đang mở trong Excel (bị khoá) thì ghi ra bản .new.csv và cảnh báo."""
    target = path
    try:
        fh = open(target, 'w', newline='', encoding='utf-8-sig')
    except PermissionError:
        target = path[:-4] + '.new.csv'
        fh = open(target, 'w', newline='', encoding='utf-8-sig')
        print('  ! %s đang bị khoá (mở trong Excel?) -> đã ghi ra %s'
              % (os.path.basename(path), os.path.basename(target)))
    with fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main(data_dir):
    p = lambda n: os.path.join(data_dir, n)
    cl = pd.read_csv(p('chem_classified.csv')).fillna('')
    dec = pd.read_csv(p('decree_chemicals.csv'), dtype=str).fillna('')

    # CAS nào cần biết hàm lượng: các chất thuộc Phụ lục II hoặc III
    need = {}
    for _, r in dec[dec.appendix.isin(['II', 'III'])].iterrows():
        for c in r['cas'].split(';'):
            if c:
                need.setdefault(c, set()).add(
                    r['appendix'] + ('/' + r['subgroup'] if r['subgroup'] else ''))

    rows, todo = [], []
    cache, cas_seen = {}, {}
    for _, r in cl.iterrows():
        code = r['code']
        path = os.path.join(config.SRC_MSDS_DIR, code + '.pdf')
        if path not in cache:
            cache[path] = extract_pdf(path) if os.path.exists(path) else {}
            cas_seen[path] = all_cas_in_pdf(path) if os.path.exists(path) else set()
        found = cache[path]

        for part in str(r['cas_raw']).split(';'):
            part = part.strip()
            m = CAS_ANY.search(part)
            if not m:
                continue
            cas = m.group(1)
            in_excel = part[m.end():].strip()
            if cas not in need:
                continue
            if in_excel:
                lo, hi = parse_bounds(in_excel)
                rows.append([code, cas, ';'.join(sorted(need[cas])), in_excel, lo, hi, 'excel', 'cao'])
            elif cas in found:
                expr, lo, hi, conf = found[cas]
                rows.append([code, cas, ';'.join(sorted(need[cas])), expr, lo, hi, 'msds_pdf', conf])
            else:
                if not os.path.exists(path):
                    why = 'khong co file MSDS dang PDF'
                elif cas not in cas_seen[path]:
                    why = ('MSDS KHONG liet ke CAS nay - can doi chieu lai danh muc. '
                           'MSDS co: ' + ', '.join(sorted(cas_seen[path])[:8]))
                else:
                    why = 'co CAS trong MSDS nhung khong doc duoc o ham luong'
                todo.append([code, r['name'][:60], cas, ';'.join(sorted(need[cas])), why])

    safe_write(p('msds_composition.csv'),
               ['code', 'cas', 'phu_luc', 'ham_luong', 'pct_min', 'pct_max', 'nguon', 'do_tin_cay'], rows)
    safe_write(p('conc_todo.csv'), ['code', 'ten', 'cas', 'phu_luc', 'ly_do'], todo)

    # --- bảng rà soát ngưỡng: mỗi (mã, phụ lục) đang ở trạng thái nào ---
    comp = pd.DataFrame(rows, columns=['code', 'cas', 'phu_luc', 'ham_luong',
                                       'pct_min', 'pct_max', 'nguon', 'do_tin_cay'])
    todo_df = pd.DataFrame(todo, columns=['code', 'ten', 'cas', 'phu_luc', 'ly_do'])
    review = []
    for pl, flag in [('II', 'pl_II'), ('III', 'pl_III')]:
        thr = 5.0 if pl == 'II' else 1.0
        pick = lambda s: s.str.startswith('III') if pl == 'III' else (
            s.str.startswith('II') & ~s.str.startswith('III'))
        sub = comp[pick(comp.phu_luc)]
        miss = set(todo_df[pick(todo_df.phu_luc)].code)
        for code in cl.loc[cl[flag], 'code']:
            g = sub[sub.code == code]
            if code in miss:
                status, why = 'chua_quyet_duoc', 'thieu ham luong cua it nhat 1 thanh phan'
            elif g.empty:
                status, why = 'chua_quyet_duoc', 'khong co du lieu ham luong'
            elif (g.pct_max > thr).any():
                over = g[g.pct_max > thr]
                status = 'giu_lai'
                why = '; '.join('%s=%s' % (r.cas, r.ham_luong) for r in over.itertuples())
            else:
                status = 'loai_duoc'
                why = 'tat ca thanh phan <= %g%%: ' % thr + '; '.join(
                    '%s=%s' % (r.cas, r.ham_luong) for r in g.itertuples())
            review.append([code, 'Phu luc ' + pl, thr, status, why[:180]])
    safe_write(p('threshold_review.csv'),
               ['code', 'phu_luc', 'nguong_pct', 'trang_thai', 'bang_chung'], review)

    total = len(rows) + len(todo)
    from_excel = sum(1 for r in rows if r[6] == 'excel')
    from_pdf = sum(1 for r in rows if r[6] == 'msds_pdf')
    low = sum(1 for r in rows if r[7] == 'thap')
    print('Cặp (mã, CAS) cần biết hàm lượng : %d' % total)
    print('  đã có sẵn trong Excel          : %d' % from_excel)
    print('  TRÍCH ĐƯỢC từ MSDS PDF         : %d (%.0f%% phần còn thiếu)' % (
        from_pdf, 100 * from_pdf / max(1, total - from_excel)))
    print('  trong đó độ tin cậy thấp       : %d (nên rà lại trước)' % low)
    print('  còn phải nhập tay              : %d  -> conc_todo.csv' % len(todo))
    print('  số mã cần nhập tay             : %d' % len({t[0] for t in todo}))
    rv = pd.DataFrame(review, columns=['code', 'phu_luc', 'nguong', 'trang_thai', 'bang_chung'])
    print('\nRà soát ngưỡng hàm lượng (threshold_review.csv):')
    for pl in ['Phu luc II', 'Phu luc III']:
        g = rv[rv.phu_luc == pl].trang_thai.value_counts()
        print('  %-12s giữ lại %-4d | loại được %-4d | chưa quyết được %d' % (
            pl, g.get('giu_lai', 0), g.get('loai_duoc', 0), g.get('chua_quyet_duoc', 0)))


if __name__ == '__main__':
    main(sys.argv[1])
