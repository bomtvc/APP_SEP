# -*- coding: utf-8 -*-
"""Màn hình C — Hóa chất: tồn trữ và tuân thủ NĐ 24/2026/NĐ-CP.

Quy ước trình bày (theo skill dataviz, xem chú thích bảng màu ở `loaders.py`):
  · Màu chỉ làm một việc: II/III/IV là NHẬN DẠNG (slot 1-2-3), ma trận GHS là
    ĐỘ LỚN (một sắc lam, nhạt→đậm), thẻ vượt ngưỡng là TRẠNG THÁI (kèm ký hiệu
    và chữ, không bao giờ chỉ có màu).
  · Nét mảnh, lưới kẻ mảnh liền nét, không viền quanh mảng dữ liệu.
  · Tooltip chỉ để đọc thêm: mọi con số đều lấy được ở bảng số liệu hoặc nhãn.
"""
import os

import altair as alt
import pandas as pd
import streamlit as st

import i18n
from i18n import t
from loaders import (chemicals, composition, daily, dieu33, freshness, msds_file,
                     palette, shutdowns, stock, thresholds)
from msds_ui import nut_mo_msds

# Dấu phân cách số đổi theo ngôn ngữ: 1.234,5 tiếng Việt · 1,234.5 tiếng Anh.
VN = lambda n: i18n.num(n)
SO = lambda x, n=2: i18n.num(x, n)


def _finish(chart):
    """Chốt cấu hình chung cho một biểu đồ trước khi vẽ.

    Nhãn số bên trong biểu đồ do Vega định dạng chứ không đi qua `VN`, nên phải
    nạp bảng locale ứng với ngôn ngữ đang xem.
    """
    return chart.configure(
        locale={'number': i18n.vega_number()}).configure_view(strokeWidth=0)


def _pha(mau, nen, a):
    """Trộn `mau` lên `nen` với độ đậm `a` (0–1), trả về hex.

    Dùng để pha sắc nền rất nhạt cho thẻ số. Tính sẵn ra hex thay vì để trình duyệt
    lo bằng `color-mix`/rgba: như vậy màu nền là một giá trị đặc, kiểm được độ tương
    phản với chữ, và không phụ thuộc phiên bản trình duyệt.
    """
    h = lambda s: tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
    m, n = h(mau), h(nen)
    return '#%02x%02x%02x' % tuple(round(m[i] * a + n[i] * (1 - a)) for i in range(3))


def _style(P):
    """CSS của thẻ số — màu lấy từ bảng màu nên phải phát lại mỗi lần render."""
    st.markdown("""<style>
      /* Dải màu dọc mép trái + sắc nền nhạt, cả hai lấy từ --kpi-accent do từng
         thẻ tự đặt. Màu ở đây KHÔNG mang thông tin mới: nó lặp lại đúng vai trò
         mà nhãn chữ của thẻ đã nói (xem chú thích ở `render`), nên thẻ vẫn đọc
         được nguyên vẹn khi in trắng đen hoặc với người loạn sắc. */
      .kpi{position:relative;overflow:hidden;
           border:1px solid %(border)s;border-radius:8px;padding:14px 16px 14px 19px;
           min-height:150px;background:var(--kpi-bg,%(surface)s);
           display:flex;flex-direction:column;gap:2px}
      .kpi::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;
                   background:var(--kpi-accent,transparent)}
      .kpi-label{font-size:11px;letter-spacing:.06em;text-transform:uppercase;
                 color:%(muted)s;font-weight:600}
      .kpi-value{font-weight:600;line-height:1.15;color:%(ink)s;font-size:28px}
      .kpi-hero .kpi-value{font-size:44px;letter-spacing:-.02em}
      .kpi-unit{font-size:13px;font-weight:400;color:%(muted)s}
      .kpi-sub{font-size:12px;color:%(ink2)s;opacity:.85;margin-top:auto}
      .kpi-delta{font-size:12.5px;color:%(ink2)s}
      .kpi-spark{margin:8px 0 2px;width:100%%;height:30px}
      /* Thẻ dẫn cao bằng đúng hai hàng thẻ (150 + khe 16 + 150) để cột trái không
         hụt so với lưới 2x3 bên phải. Đường xu hướng giãn theo chỗ trống nhưng có
         trần: cao quá thì nó thành cái biểu đồ thứ hai, tranh chỗ với biểu đồ thật
         ngay bên dưới. */
      .kpi-hero{min-height:316px}
      .kpi-hero .kpi-spark{flex:1 1 auto;height:auto;min-height:44px;max-height:118px}
    </style>""" % P, unsafe_allow_html=True)


def _spark(values, P, w=260, h=30, tail=10):
    """Đường xu hướng nhỏ trong thẻ số: phần nền mực phụ, kỳ gần nhất màu nhấn."""
    if len(values) < 3:
        return ''
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1
    pts = [(i * w / (len(values) - 1), h - 2 - (v - lo) / rng * (h - 4))
           for i, v in enumerate(values)]
    fmt = lambda seq: ' '.join('%.1f,%.1f' % p for p in seq)
    return ('<svg class="kpi-spark" width="100%%" height="%d" viewBox="0 0 %d %d" '
            'preserveAspectRatio="none" aria-hidden="true">'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.5" '
            'stroke-linejoin="round" opacity=".45"/>'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="2" '
            'stroke-linejoin="round"/></svg>'
            % (h, w, h, fmt(pts), P['muted'], fmt(pts[-tail:]), P['II']))


def _tile(col, label, value, unit='', sub='', hero=False, color=None, spark='', delta='',
          accent=None, P=None):
    """Một thẻ số. `accent` là màu vai trò của thẻ — xem chú thích ở `render`."""
    style = ''
    if accent and P:
        # Sắc nền đậm hơn ở chế độ tối: nền tối cần nhiều màu hơn mới thấy được,
        # nền sáng thì chỉ cần một lớp phớt, quá tay là chữ khó đọc.
        style = ' style="--kpi-accent:%s;--kpi-bg:%s"' % (
            accent, _pha(accent, P['surface'], 0.10 if P['toi'] else 0.045))
    col.markdown(
        '<div class="kpi%s"%s><div class="kpi-label">%s</div>'
        '<div class="kpi-value"%s>%s<span class="kpi-unit"> %s</span></div>%s%s'
        '<div class="kpi-sub">%s</div></div>'
        % (' kpi-hero' if hero else '', style, label,
           ' style="color:%s"' % color if color else '', value, unit,
           '<div class="kpi-delta">%s</div>' % delta if delta else '', spark, sub),
        unsafe_allow_html=True)


def render():
    P = palette()
    _style(P)

    fresh = freshness()
    d, ch, iv = daily(), chemicals(), thresholds()
    st_all = stock()

    st.markdown('### ' + t('c.title'))
    # ---------- bộ lọc: một hàng, nằm trên mọi thứ nó chi phối ----------
    f1, f2, f3 = st.columns([2, 2, 1.2])
    lo, hi = fresh['tu'].date(), fresh['den'].date()
    rng = f1.date_input(t('c.filter.range'), value=(lo, hi),
                        min_value=lo, max_value=hi)
    if isinstance(rng, tuple) and len(rng) == 2:
        d0, d1 = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])
    else:
        d0, d1 = pd.Timestamp(lo), pd.Timestamp(hi)
    pls = f2.multiselect(t('c.filter.appendix'), ['II', 'III', 'IV'],
                         default=['II', 'III', 'IV'])
    chi_co_ton = f3.checkbox(t('c.filter.instock'), value=True)

    dd = d[(d.date >= d0) & (d.date <= d1)]
    ss = st_all[(st_all.date >= d0) & (st_all.date <= d1)]
    if dd.empty:
        st.warning(t('c.empty'))
        return

    # ---------- thẻ số ----------
    last = dd.iloc[-1]
    peak = dd.loc[dd.total.idxmax()]
    codes_pos = ss.groupby('code').qty_kg.max()
    codes_pos = set(codes_pos[codes_pos > 0].index)
    vuot = int(iv.vuot_nguong.sum())
    # Điều 33 khoản 2 NĐ 25/2026: phải lập Kế hoạch phòng ngừa, ứng phó sự cố khi
    # (a) có một mã đạt ngưỡng riêng, HOẶC (b) tổng tỉ lệ q/Q của mọi hóa chất >= 1.
    d33 = dieu33()
    tong33 = float(d33.ty_le.sum())
    phai_lap = bool(vuot) or tong33 >= 1

    # Bố cục: thẻ dẫn chiếm trọn cột trái, lưới 2x3 nằm cột phải. Lồng cột như
    # vậy để thẻ dẫn cao đúng bằng hai hàng thẻ (150 + khe 16 + 150 = 316px) —
    # xếp thành hai hàng cột song song thì hàng dưới bị đẩy tụt 150px.
    # Tỉ lệ 1,7 : 3,15 và ba khe 16px giữ nguyên bề ngang từng thẻ như cũ.
    # Màu của thẻ số KHÔNG phải trang trí, nó nói thẻ đó thuộc nhóm nào — và nói
    # lại đúng điều nhãn chữ đã nói, nên không có thông tin nào chỉ nằm ở màu:
    #   · ba thẻ tổng quan  -> mực xám 'total', đúng màu đường "Tổng" ở biểu đồ dưới
    #   · thẻ ngưỡng PL IV  -> màu TRẠNG THÁI, vẫn kèm ✓ / ▲ và câu chữ như cũ
    #   · ba thẻ phụ lục    -> màu NHẬN DẠNG II/III/IV, khớp ba đường trong biểu đồ
    # Nhờ vậy mắt nối thẳng được thẻ với đường tương ứng, không phải dò chú giải.
    # Không thêm icon nào: ký hiệu duy nhất trên thẻ vẫn là ▲/▼/= và ✓ vốn có.
    trai, phai = st.columns([1.7, 3.15])
    # Chênh lệch đầu kỳ để mực trung tính, không dùng màu trạng thái: tồn kho tăng
    # hay giảm đều không đương nhiên là tốt hay xấu.
    dau = dd.iloc[0]
    chenh = last.total - dau.total
    _tile(trai, t('c.tile.last'), VN(last.total), 'kg',
          last.date.strftime('%d/%m/%Y'), hero=True, spark=_spark(list(dd.total), P),
          delta=t('c.tile.delta', '▲' if chenh > 0 else ('▼' if chenh < 0 else '='),
                  VN(abs(chenh)), dau.date.strftime('%d/%m/%Y')),
          accent=P['total'], P=P)

    with phai:
        r1 = st.columns([1, 1, 1.15])
        _tile(r1[0], t('c.tile.peak'), VN(peak.total), 'kg', peak.date.strftime('%d/%m/%Y'),
              accent=P['total'], P=P)
        _tile(r1[1], t('c.tile.codes'), VN(len(codes_pos)),
              t('c.tile.of_total', ch.code.nunique()), t('c.tile.in_range'),
              accent=P['total'], P=P)
        # Thẻ ngưỡng chỉ ăn màu KHI CÓ VẤN ĐỀ, lúc bình thường để mực trung tính.
        # Hai lý do: (1) xanh lá đã là màu nhận dạng của Phụ lục IV — thẻ này nằm
        # ngay trên thẻ Phụ lục IV nên tô xanh "đạt" thì một màu mang hai nghĩa ở
        # hai ô dính nhau; (2) tiêu tốn màu cho trạng thái BÌNH THƯỜNG thì lúc thật
        # sự có sự cố, cái đỏ không còn nổi hơn phần còn lại bao nhiêu.
        # Trạng thái vẫn không bao giờ chỉ dựa vào màu: ✓ / ▲ và câu chữ giữ nguyên.
        trang_thai = P['crit'] if phai_lap else None
        _tile(r1[2], t('c.tile.threshold'), VN(vuot), t('c.tile.of_over', len(iv)),
              t('c.tile.must_plan') if phai_lap else t('c.tile.no_plan'),
              delta=t('c.tile.ratio', SO(tong33)),
              color=trang_thai, accent=trang_thai or P['total'], P=P)

        # Hàng hai — tách theo phụ lục. Nhận dạng nằm ở DẢI MÀU mép trái, không ở
        # màu của chữ: nhãn 11px in hoa mà tô màu phân loại thì #1baf7a chỉ đạt
        # 2,74:1, dưới ngưỡng chữ nhỏ. Dải màu là mảng đồ họa nên không vướng
        # ngưỡng đó, mà vẫn kèm chữ "Phụ lục II/III/IV" ngay bên cạnh.
        # (Trước 09/09/2026 vai trò này do một chấm tròn trước tên đảm nhiệm; dải
        # màu thay hẳn nó, giữ cả hai thì thừa và rối.)
        cot_pl = {'II': 'pl_II_chot', 'III': 'pl_III_chot', 'IV': 'pl_IV'}
        r2 = st.columns([1, 1, 1.15])
        for i, pl in enumerate(['II', 'III', 'IV']):
            thuoc = set(ch.loc[ch[cot_pl[pl]].astype(bool), 'code'])
            _tile(r2[i], t('c.tile.appendix', pl),
                  VN(len(thuoc & codes_pos)), t('c.tile.of_instock', len(thuoc)),
                  t('c.tile.closing', VN(last['pl_' + pl])),
                  accent=P[pl], P=P)

    # ---------- đường tồn trữ ----------
    st.markdown('#### ' + t('c.chart.daily'))
    series = {t('c.series.total'): ('total', P['total'])}
    for pl in pls:
        series[t('c.tile.appendix', pl)] = ('pl_' + pl, P[pl])
    order = list(series)
    long = pd.concat([
        dd[['date', col]].rename(columns={col: 'kg'}).assign(nhom=name)
        for name, (col, _) in series.items()
    ])

    base = alt.Chart(long).mark_line(strokeWidth=2, strokeJoin='round', strokeCap='round').encode(
        x=alt.X('date:T', title=None,
                axis=alt.Axis(format='%d/%m', tickCount=8, grid=False, domainColor=P['axis'],
                              tickColor=P['axis'], labelColor=P['muted'], labelFontSize=11)),
        y=alt.Y('kg:Q', title='kg',
                axis=alt.Axis(grid=True, gridColor=P['grid'], gridWidth=1, domain=False,
                              tickSize=0, labelPadding=8, format=',.0f',
                              labelColor=P['muted'], titleColor=P['muted'], titleFontSize=11)),
        color=alt.Color('nhom:N', title=None, sort=order,
                        scale=alt.Scale(domain=order, range=[c for _, c in series.values()]),
                        legend=alt.Legend(orient='top', direction='horizontal', offset=4,
                                          symbolType='stroke', symbolStrokeWidth=3,
                                          labelColor=P['ink2'], labelFontSize=12)),
    )

    # Vùng nghỉ nhà máy — nền bối cảnh, mực xám nhạt, không phải một chuỗi dữ liệu.
    layers = []
    for a, b, why in shutdowns():
        if b >= d0 and a <= d1:
            layers.append(alt.Chart(pd.DataFrame({'a': [max(a, d0)], 'b': [min(b, d1)], 'why': [why]}))
                          .mark_rect(opacity=.10, color=P['muted'])
                          .encode(x='a:T', x2='b:T',
                                  tooltip=alt.Tooltip('why:N', title=t('c.tt.note'))))
    co_ky_nghi = bool(layers)
    layers.append(base)

    # Nhãn trực tiếp DUY NHẤT: đỉnh của đường Tổng. Không dán số lên mọi điểm.
    pk = dd.loc[[dd.total.idxmax()]]
    layers += [
        alt.Chart(pk).mark_point(size=52, filled=True, color=P['total'],
                                 stroke=P['surface'], strokeWidth=2)
        .encode(x='date:T', y='total:Q'),
        alt.Chart(pk).mark_text(dy=-13, fontSize=11.5, fontWeight=600, color=P['ink'])
        .encode(x='date:T', y='total:Q', text=alt.Text('total:Q', format=',.0f')),
    ]

    # Một tooltip cho MỌI chuỗi tại ngày đang trỏ — không phải trỏ trúng từng đường.
    # Vùng bắt chuột rộng 14px và trong suốt; vạch dóng nhìn thấy chỉ 1px. Tách hai
    # lớp vì nếu để chung thì vạch mảnh 1px là đích chuột không ai trỏ trúng.
    hover = alt.selection_point(fields=['date'], nearest=True, on='pointerover',
                                clear='pointerout', empty=False)
    layers += [
        alt.Chart(dd).mark_rule(color=P['axis'], strokeWidth=1).encode(
            x='date:T', opacity=alt.condition(hover, alt.value(.7), alt.value(0))),
        alt.Chart(dd).mark_rule(strokeWidth=14, opacity=0).encode(
            x='date:T',
            tooltip=[alt.Tooltip('date:T', title=t('c.tt.date'), format='%d/%m/%Y')]
                    + [alt.Tooltip(col + ':Q', title=name, format=',.0f')
                       for name, (col, _) in series.items()],
        ).add_params(hover),
    ]

    st.altair_chart(_finish(alt.layer(*layers).properties(height=330)), width='stretch')
    # if co_ky_nghi:
    #     st.caption('Vùng tô nhạt là kỳ nghỉ nhà máy — tồn kho không dịch chuyển, không phải thiếu số liệu.')

    # Kênh đọc thay cho màu: mọi giá trị trên biểu đồ đều có ở đây, không cần rê chuột.
    with st.expander(t('c.table.expander')):
        tbl = dd[['date'] + [col for _, (col, _) in series.items()]].copy()
        tbl['date'] = tbl['date'].dt.strftime('%d/%m/%Y')
        st.dataframe(
            tbl.rename(columns=dict([('date', t('c.tt.date'))]
                                    + [(col, name) for name, (col, _) in series.items()])),
            hide_index=True, width='stretch', height=280)

    # ---------- đối chiếu ngưỡng Phụ lục IV ----------
    st.markdown('#### ' + t('c.iv.heading'))
    # Đừng đặt tên biến là `t`: đó là hàm dịch chuỗi, trùng tên sẽ che mất nó.
    bang = iv.copy()
    bang['ty_le'] = (bang.ton_de_so_nguong.fillna(0) / bang.nguong_kg).clip(0, 1)
    show = bang.sort_values('ty_le', ascending=False)[
        ['code', 'name', 'nguong_kg', 'ton_de_so_nguong', 'ty_le', 'vuot_nguong']]
    st.dataframe(
        show, hide_index=True, width='stretch',
        column_config={
            'code': st.column_config.TextColumn(t('c.iv.code'), width='small'),
            'name': st.column_config.TextColumn(t('c.iv.name')),
            'nguong_kg': st.column_config.NumberColumn(t('c.iv.threshold'), format='%.0f'),
            'ton_de_so_nguong': st.column_config.NumberColumn(t('c.iv.stock'), format='%.0f'),
            'ty_le': st.column_config.ProgressColumn(t('c.iv.pct'), min_value=0, max_value=1,
                                                     format='%.1f%%'),
            'vuot_nguong': st.column_config.CheckboxColumn(t('c.iv.over'), width='small'),
        })

    with st.expander(t('c.d33.expander', SO(tong33))):
        st.markdown(t('c.d33.intro'))
        st.markdown(t('c.d33.a',
                      SO(100 * (iv.ton_de_so_nguong.fillna(0) / iv.nguong_kg).max(), 0)))
        st.markdown(t('c.d33.b'))
        st.markdown(t('c.d33.now', SO(tong33),
                      t('c.d33.reached') if tong33 >= 1
                      else t('c.d33.below', SO(100 * (1 - tong33), 0))))
        b33 = d33.copy()
        # Chất chỉ đến từ mã không theo dõi hàng ngày thì không có ngày đỉnh: q là
        # mức khai báo lớn nhất, coi như giữ nguyên suốt kỳ.
        b33['ngay_dinh'] = [pd.to_datetime(x).strftime('%d/%m/%Y') if str(x).strip()
                            and str(x) != 'nan' else t('c.d33.declared')
                            for x in b33.ngay_dinh]
        st.dataframe(
            b33[['cas', 'so_ma', 'q_kg', 'ngay_dinh', 'nguong_kg', 'ty_le']],
            hide_index=True, width='stretch',
            column_config={
                'cas': st.column_config.TextColumn(t('c.d33.cas'), width='small'),
                'so_ma': st.column_config.NumberColumn(t('c.d33.codes'), format='%d'),
                'q_kg': st.column_config.NumberColumn(t('c.d33.q'), format='%.0f'),
                'ngay_dinh': st.column_config.TextColumn(t('c.d33.peak_date'), width='small'),
                'nguong_kg': st.column_config.NumberColumn(t('c.d33.Q'), format='%.0f'),
                'ty_le': st.column_config.ProgressColumn(t('c.d33.ratio'), min_value=0,
                                                         max_value=1,
                                                         format='%.3f'),
            })

    # ---------- top mã và mã nằm im ----------
    c1, c2 = st.columns([1.35, 1])
    peaks = ss.groupby(['code', 'name']).qty_kg.max().reset_index()
    top = peaks.nlargest(15, 'qty_kg')
    c1.markdown('#### ' + t('c.top.heading'))
    # Danh mục mã không có thứ tự nội tại → MỘT màu cho mọi thanh, không tô đậm
    # theo giá trị (độ dài thanh đã nói điều đó rồi). Số nằm ở đầu thanh nên bỏ trục x.
    bars = alt.Chart(top).mark_bar(color=P['II'], cornerRadiusEnd=4, size=15).encode(
        x=alt.X('qty_kg:Q', title=None, axis=None),
        y=alt.Y('code:N', sort='-x', title=None,
                axis=alt.Axis(domain=False, ticks=False, labelPadding=8,
                              labelColor=P['ink2'], labelFontSize=11.5)),
        tooltip=[alt.Tooltip('code:N', title=t('c.iv.code')),
                 alt.Tooltip('name:N', title=t('c.top.name')),
                 alt.Tooltip('qty_kg:Q', title=t('c.top.peak'), format=',.0f')],
    )
    tips = alt.Chart(top).mark_text(align='left', dx=6, fontSize=11, color=P['ink2']).encode(
        x='qty_kg:Q', y=alt.Y('code:N', sort='-x'), text=alt.Text('qty_kg:Q', format=',.0f'))
    c1.altair_chart(
        _finish(alt.layer(bars, tips).properties(height=380, padding={'right': 52})),
        width='stretch')

    # ---------- ma trận GHS — nằm cột phải, cạnh biểu đồ thanh ----------
    c2.markdown('#### ' + t('c.ghs.heading'))
    groups = [(k, t('c.ghs.' + k)) for k in
              ('explosive', 'flammable', 'oxidizing', 'gas_pressure', 'corrosive',
               'toxic', 'health', 'env', 'other')]
    sub = ch[ch.code.isin(codes_pos)] if chi_co_ton else ch
    rows = []
    for key, label in groups:
        col = key + '_cat'
        has = sub[sub[col].astype(str).str.strip().replace('nan', '') != '']
        # Lọc theo giá trị GỐC trong CSV, chỉ dịch lúc hiển thị.
        for the in ['LỎNG', 'RẮN', 'KHÍ']:
            rows.append({'nhom': label, 'the': i18n.state(the),
                         'so_ma': int((has.state == the).sum())})
    m = pd.DataFrame(rows)
    ynhom = alt.Y('nhom:N', title=None, sort=[l for _, l in groups],
                  axis=alt.Axis(domain=False, ticks=False, labelPadding=8, labelLimit=220,
                                labelColor=P['ink2'], labelFontSize=12))
    xthe = alt.X('the:N', title=None,
                 axis=alt.Axis(orient='top', domain=False, ticks=False, labelPadding=8,
                               labelAngle=0, labelColor=P['ink2'], labelFontSize=12))
    # Độ lớn → MỘT sắc lam nhạt→đậm. Khe hở 2px màu nền tách ô, không vẽ viền.
    # Ô bằng 0 lùi về xám trung tính: "không có mã nào" không phải một mức độ lớn.
    cells = alt.Chart(m).mark_rect(stroke=P['surface'], strokeWidth=2).encode(
        x=xthe, y=ynhom,
        color=alt.condition(
            alt.datum.so_ma > 0,
            alt.Color('so_ma:Q', title=t('c.ghs.count'), scale=alt.Scale(range=P['seq']),
                      legend=None),
            alt.value(P['grid'])),
        tooltip=[alt.Tooltip('nhom:N', title=t('c.ghs.group')),
                 alt.Tooltip('the:N', title=t('c.ghs.state')),
                 alt.Tooltip('so_ma:Q', title=t('c.ghs.count'))],
    )
    nums = alt.Chart(m).mark_text(fontSize=12, fontWeight=600).encode(
        x=xthe, y=ynhom, text='so_ma:Q',
        color=alt.condition(alt.datum.so_ma > m.so_ma.max() * .55,
                            alt.value(P['surface']), alt.value(P['ink2'])))
    # Cao bằng biểu đồ thanh bên trái để hai khối kết thúc cùng một đường ngang;
    # bề ngang co theo cột chứ không đặt cứng, vì cột này hẹp hơn cả trang.
    c2.altair_chart(_finish(alt.layer(cells, nums).properties(height=380)), width='stretch')

    # ---------- tra cứu một mã ----------
    st.markdown('#### ' + t('c.one.heading'))
    code = st.selectbox(t('c.one.select'), sorted(ch.code),
                        format_func=lambda c: '%s — %s' % (c, ch.loc[ch.code == c, 'name'].iloc[0][:60]))
    r = ch[ch.code == code].iloc[0]
    a, b = st.columns([1, 1.3])
    with a:
        st.markdown('**%s**' % r['name'])
        st.markdown(t('c.one.state', i18n.state(r['state']), r['max_stock_kg']))
        st.markdown(t('c.one.appendix', r['appendices_chot'] or t('c.one.none')))
        if r['appendices'] != r['appendices_chot']:
            st.caption(t('c.one.before', r['appendices'] or '—'))
        for pl, key in [('II', 'can_cu_II'), ('III', 'can_cu_III')]:
            if str(r.get(key, '')).strip():
                st.caption('%s — %s' % (t('c.tile.appendix', pl), i18n.can_cu(r[key])))
        st.markdown(t('c.one.cas', r['cas_raw'] or 'N/A'))
        if str(r.get('cas_raw_goc', '')).strip():
            st.caption(t('c.one.corrected', r['cas_raw_goc']))
        path = msds_file(code)
        if path:
            nut_mo_msds(st, path, 'chem_' + code)
        comp = composition()
        cc = comp[comp.code == code]
        if len(cc):
            st.markdown(t('c.one.comp'))
            cc = cc[['cas', 'phu_luc', 'ham_luong']].assign(
                phu_luc=cc.phu_luc.map(i18n.appendix))
            st.dataframe(cc.rename(columns={'cas': t('c.col.cas'),
                                            'phu_luc': t('c.col.appendix'),
                                            'ham_luong': t('c.col.conc')}),
                         hide_index=True, width='stretch')
    with b:
        one = ss[ss.code == code]
        if one.qty_kg.max() == 0:
            st.info(t('c.one.no_stock'))
        # Một chuỗi duy nhất nên không cần chú giải — tiêu đề đã nói đang vẽ gì.
        st.altair_chart(_finish(
            alt.Chart(one).mark_area(
                opacity=.12, color=P['II'],
                line={'color': P['II'], 'strokeWidth': 2, 'strokeJoin': 'round'}).encode(
                x=alt.X('date:T', title=None,
                        axis=alt.Axis(format='%d/%m', tickCount=6, grid=False,
                                      domainColor=P['axis'], tickColor=P['axis'],
                                      labelColor=P['muted'], labelFontSize=11)),
                y=alt.Y('qty_kg:Q', title='kg',
                        axis=alt.Axis(grid=True, gridColor=P['grid'], gridWidth=1, domain=False,
                                      tickSize=0, labelPadding=8, format=',.0f',
                                      labelColor=P['muted'], titleColor=P['muted'], titleFontSize=11)),
                tooltip=[alt.Tooltip('date:T', title=t('c.tt.date'), format='%d/%m/%Y'),
                         alt.Tooltip('qty_kg:Q', title=t('c.one.qty'), format=',.0f')],
            ).properties(height=260, title=t('c.one.chart', code))),
            width='stretch')

    # ---------- xuất báo cáo ----------
    st.markdown('#### ' + t('c.export.heading'))
    e1, e2 = st.columns(2)
    e1.download_button(
        t('c.export.daily'),
        dd.to_csv(index=False).encode('utf-8-sig'),
        file_name=t('c.export.daily_file', d0.date(), d1.date()), mime='text/csv')
    e2.download_button(
        t('c.export.iv'),
        iv.to_csv(index=False).encode('utf-8-sig'),
        file_name=t('c.export.iv_file'), mime='text/csv')
