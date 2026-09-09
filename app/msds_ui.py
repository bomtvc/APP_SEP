# -*- coding: utf-8 -*-
"""Nút mở file MSDS — dùng chung cho cả hai màn hình.

Tách ra vì cách xử lý file OneDrive chưa tải về không tầm thường: không mở bừa
(sẽ treo trang), nhưng cũng không được thành ngõ cụt. Xem `loaders.msds_state`.
"""
import os

import streamlit as st

from i18n import t
from loaders import msds_bytes, msds_state

_MIME = {'PDF': 'application/pdf', 'DOC': 'application/msword',
         'DOCX': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


def nut_mo_msds(box, path, key, nhan=None):
    """Vẽ nút mở MSDS vào `box` (st, một cột, hay một container).

    File đã có sẵn trên máy thì hiện nút mở luôn. File còn là vỏ rỗng OneDrive thì
    nói rõ lý do và mời tải — chỉ khi người dùng bấm mới thực sự mở file.
    """
    ext = path.rsplit('.', 1)[-1].upper()
    trang_thai, ly_do = msds_state(path)
    da_xin_tai = 'msds_tai_' + key

    if trang_thai != 'san_sang' and not st.session_state.get(da_xin_tai):
        box.warning(t('m.blocked', ext, ly_do))
        if not box.button(t('m.fetch'), key='msds_nut_' + key,
                          width='stretch'):
            return
        st.session_state[da_xin_tai] = True

    if trang_thai == 'san_sang':
        data, loi = msds_bytes(path)
    else:
        with st.spinner(t('m.fetching', os.path.basename(path))):
            data, loi = msds_bytes(path, tai_ve=True)

    if data is None:
        st.session_state.pop(da_xin_tai, None)
        box.error(t('m.failed', loi))
        return

    box.download_button(nhan or t('m.open', ext, len(data) / 1e6),
                        data, file_name=os.path.basename(path),
                        mime=_MIME.get(ext, 'application/octet-stream'),
                        key='msds_tai_ve_' + key, width='stretch')
