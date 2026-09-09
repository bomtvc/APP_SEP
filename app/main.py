# -*- coding: utf-8 -*-
r"""Dashboard Hóa chất — điểm vào.

Chạy:  .venv\Scripts\streamlit.exe run app/main.py

Phạm vi đã thu hẹp ngày 09/09/2026: chỉ còn hóa chất. Phần chất thải, phế liệu và
quỹ ve chai đã gỡ khỏi cả ETL lẫn Dashboard (xem CLAUDE.md).
"""
import io
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(ROOT, 'Logo_Mark.png')

# Cờ OneDrive Files On-Demand — file "chỉ có trên đám mây" vẫn qua được
# os.path.exists nhưng mở ra thì treo rồi ném OSError(22). Kiểm tra thuộc tính
# TRƯỚC khi mở (xem loaders.msds_offline và bẫy OneDrive trong CLAUDE.md).
_RECALL = 0x00400000 | 0x00040000


@st.cache_data(show_spinner=False)
def _page_icon():
    """Logo công ty làm favicon; quay về emoji nếu không đọc được file.

    Trả về bytes PNG đã thu nhỏ chứ không trả đường dẫn: file gốc 2448x2448,
    Streamlit giải mã lại ở MỖI lần rerun (~230 ms) nếu đưa đường dẫn thẳng.
    Thu nhỏ về 256 px một lần rồi cache — favicon 64 KB thay vì 337 KB.
    """
    try:
        attrs = getattr(os.stat(LOGO), 'st_file_attributes', 0)
        if attrs & _RECALL:
            return '🧪'
        from PIL import Image
        im = Image.open(LOGO)
        im.load()
        buf = io.BytesIO()
        im.resize((256, 256), Image.LANCZOS).save(buf, 'PNG')
        return buf.getvalue()
    except Exception:
        return '🧪'


import i18n  # noqa: E402  (cần sys.path ở trên)
from i18n import t  # noqa: E402

# i18n.lang() đọc thẳng khóa widget trong session_state nên tiêu đề tab đã đúng
# ngôn ngữ ngay trong lượt rerun sau khi bấm đổi — xem chú thích ở `i18n.py`.
st.set_page_config(page_title=t('app.title'), page_icon=_page_icon(),
                   layout='wide', initial_sidebar_state='collapsed')

# Nhịp trang chung. Màu để `.streamlit/config.toml` lo, ở đây chỉ có khoảng thở.
st.markdown("""<style>
      .block-container{padding-top:2.2rem;max-width:1400px}
      h3{margin-bottom:.2rem}
      h4{margin-top:1.8rem;margin-bottom:.5rem;font-size:1.05rem}
    </style>""", unsafe_allow_html=True)

import chemical  # noqa: E402
import lookup  # noqa: E402

# Khóa màn hình là mã bất biến, KHÔNG phải tên hiển thị: đổi ngôn ngữ thì tên
# đổi theo nhưng lựa chọn trong sidebar phải giữ nguyên màn hình đang xem.
PAGES = {
    'chemical': chemical.render,
    'lookup': lookup.render,
}

# Nút VI / EN nằm góc trên bên phải, TRƯỚC mọi nội dung của màn hình — sidebar
# mặc định đang thu nên để trong đó thì không ai thấy.
i18n.picker(st.columns([7, 1])[1])

if len(PAGES) > 1:
    choice = st.sidebar.radio(t('nav.screen'), list(PAGES), key='nav',
                              format_func=lambda p: t('page.' + p))
else:
    choice = next(iter(PAGES))

PAGES[choice]()
