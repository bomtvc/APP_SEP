# -*- coding: utf-8 -*-
"""Màn hình D — Tra cứu MSDS và tạo nhãn hóa chất."""
import os

import streamlit as st
import streamlit.components.v1 as components

import ghs
import i18n
from i18n import t
from loaders import chemicals, composition, msds_file, msds_offline_count, stock
from msds_ui import nut_mo_msds

PRINT_CSS = """
<style>
  @page { size: A4 portrait; margin: 10mm; }
  body { margin:0; font-family:'Be Vietnam Pro',Arial,sans-serif; background:#fff; }
  .sheet { display:flex; flex-wrap:wrap; gap:6mm; }
  .sheet > div { break-inside:avoid; page-break-inside:avoid; }
  @media print { .noprint { display:none } }
</style>
"""


def _label_page(html_labels, title=None):
    # Trang in đứng riêng ngoài Streamlit nên phải tự khai `lang` cho đúng ngôn
    # ngữ đang xem — trình duyệt dựa vào đó để ngắt dòng và kiểm tả.
    return ('<!doctype html><html lang="%s"><head><meta charset="utf-8"><title>%s</title>%s</head>'
            '<body><div class="noprint" style="padding:8px 0;font:13px sans-serif;color:#555">'
            '%s</div>'
            '<div class="sheet">%s</div></body></html>'
            % (i18n.lang(), title or t('g.label_title'),
               PRINT_CSS + ghs.picto_css(), t('l.print_hint'),
               ''.join(html_labels)))


def render():
    ch = chemicals()
    comp = composition()

    st.markdown('### ' + t('l.title'))
    st.caption(t('l.intro'))
    chua_tai, tong = msds_offline_count()
    if chua_tai:
        st.caption(t('l.offline', chua_tai, tong))

    q = st.text_input(t('l.search'), placeholder=t('l.placeholder'),
                      label_visibility='collapsed')
    hits = ch
    if q.strip():
        tu = q.strip().lower()   # đừng đặt tên `t`: trùng với hàm dịch chuỗi
        mask = (ch.code.str.lower().str.contains(tu, regex=False)
                | ch.name.str.lower().str.contains(tu, regex=False)
                | ch.cas_raw.astype(str).str.lower().str.contains(tu, regex=False))
        hits = ch[mask]
        st.caption(t('l.hits_one' if len(hits) == 1 else 'l.hits', len(hits)))
    if hits.empty:
        st.warning(t('l.no_hits'))
        return

    code = st.selectbox(t('l.select'), sorted(hits.code), key='lookup_code',
                        format_func=lambda c: '%s — %s' % (c, ch.loc[ch.code == c, 'name'].iloc[0][:70]))
    r = ch[ch.code == code].iloc[0]
    codes_h = ghs.h_codes(r)
    pictos = ghs.pictograms(codes_h)
    word = ghs.signal_word(codes_h)
    stmts = ghs.statements(codes_h)

    left, right = st.columns([1, 1])

    with left:
        st.markdown('#### %s' % r['name'])
        st.markdown(t('l.summary', code, i18n.state(r['state']), r['max_stock_kg']))
        st.markdown(t('l.appendix', r['appendices_chot'] or t('c.one.none')))
        if r['appendices'] != r['appendices_chot']:
            st.caption(t('c.one.before', r['appendices'] or '—'))
        st.markdown(t('c.one.cas', str(r['cas_raw']) or 'N/A'))
        if str(r.get('cas_raw_goc', '')).strip():
            st.caption(t('c.one.corrected', r['cas_raw_goc']))

        path = msds_file(code)
        if path:
            ext = path.rsplit('.', 1)[-1].lower()
            nut_mo_msds(st, path, 'lookup_' + code)
            if ext != 'pdf':
                st.caption(t('l.not_pdf', ext))
        else:
            st.error(t('l.no_msds'))

        cc = comp[comp.code == code]
        if len(cc):
            st.markdown(t('l.comp'))
            cc = cc[['cas', 'phu_luc', 'ham_luong', 'nguon']].assign(
                phu_luc=cc.phu_luc.map(i18n.appendix), nguon=cc.nguon.map(i18n.source))
            st.dataframe(cc.rename(columns={
                'cas': t('c.col.cas'), 'phu_luc': t('c.col.appendix'),
                'ham_luong': t('c.col.conc'), 'nguon': t('c.col.source')}),
                hide_index=True, width='stretch')

        one = stock().query('code == @code')
        if len(one) and one.qty_kg.max() > 0:
            st.markdown(t('l.stock', i18n.num(one.qty_kg.max()),
                          i18n.num(one.sort_values('date').qty_kg.iloc[-1])))
        else:
            st.markdown(t('l.stock_zero'))

    with right:
        st.markdown('#### ' + t('l.label'))
        size = st.radio(t('l.label_size'), ['A6', 'A5'], horizontal=True, key='label_size')
        html = ghs.label_html(r, pictos, word, stmts, size=size)
        # `components.html` dựng một iframe riêng, không thừa hưởng CSS của trang
        # nên khối khai báo hình đồ phải đi kèm ngay trong đó.
        components.html(ghs.picto_css()
                        + '<div style="background:#fff;padding:10px">%s</div>' % html,
                        height=430 if size == 'A6' else 520, scrolling=True)
        st.download_button(t('l.label_dl'), _label_page([html]).encode('utf-8'),
                           file_name=t('l.label_file', code), mime='text/html',
                           width='stretch')

    # ---------- in hàng loạt ----------
    st.markdown('#### ' + t('l.batch'))
    c1, c2 = st.columns([3, 1])
    # Lựa chọn giữ mã bất biến, chỉ tên hiển thị mới đổi theo ngôn ngữ — đổi ngôn
    # ngữ không được làm nhảy về mục đầu.
    preset = c1.selectbox(t('l.preset'), ['custom', 'iv', 'ii_iii', 'instock'],
                          format_func=lambda k: t('l.preset.' + k), key='batch_preset')
    if preset == 'iv':
        default = sorted(ch[ch.pl_IV].code)
    elif preset == 'ii_iii':
        default = sorted(ch[ch.pl_II_chot | ch.pl_III_chot].code)
    elif preset == 'instock':
        pk = stock().groupby('code').qty_kg.max()
        default = sorted(pk[pk > 0].index)
    else:
        default = [code]
    picked = st.multiselect(t('l.batch_codes'), sorted(ch.code), default=default,
                            key='batch_codes')
    bsize = c2.radio(t('l.batch_size'), ['A6', 'A5'], horizontal=True, key='batch_size')

    if picked:
        labels = []
        for c in picked:
            rr = ch[ch.code == c].iloc[0]
            hc = ghs.h_codes(rr)
            labels.append(ghs.label_html(rr, ghs.pictograms(hc), ghs.signal_word(hc),
                                         ghs.statements(hc), size=bsize))
        st.download_button(t('l.batch_dl_one' if len(picked) == 1 else 'l.batch_dl',
                             len(picked)),
                           _label_page(labels).encode('utf-8'),
                           file_name=t('l.batch_file', len(picked)),
                           mime='text/html')
