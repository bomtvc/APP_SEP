# -*- coding: utf-8 -*-
"""Trích 9 hình đồ cảnh báo GHS chuẩn từ file danh mục -> data/ghs_pictograms/.

    python etl/trich_hinh_ghs.py data

Bộ hình chuẩn nằm sẵn trong `list hóa chất total 2026.xlsx` (xlsx là file zip,
ảnh ở `xl/media/`). Trước đây `app/ghs.py` tự vẽ hình đồ bằng SVG đơn giản hóa —
gần đúng nhưng không phải hình chuẩn. Nay dùng đúng bộ ảnh của danh mục.

**Ánh xạ theo VÂN TAY sha256, không theo tên file.** Thứ tự `image1..image9` trong
xlsx là thứ tự Excel lưu ảnh, không có gì bảo đảm nó ổn định khi bộ phận vận hành
sửa file. Gán nhầm hình đồ trên nhãn hóa chất là gán nhầm mức nguy hiểm — ví dụ để
"dấu chấm than" (kích ứng) vào chỗ đáng ra là "đầu lâu" (độc cấp tính). Nên script
thà DỪNG còn hơn đoán: gặp ảnh lạ thì báo lỗi và giữ nguyên file cũ.

Thêm/đổi ảnh trong Excel thì chạy script, đọc vân tay nó in ra, xem tận mắt ảnh đó
là hình đồ nào rồi mới thêm vào `VAN_TAY`.
"""
import hashlib
import io
import os
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

THU_MUC = 'ghs_pictograms'
CANH = 192      # cạnh ảnh sau khi chuẩn hóa, px
                # Ảnh gốc trong Excel cỡ ~180px. Đặt cao hơn nhiều là phóng to
                # pixel giả, chỉ nặng file chứ không nét thêm. 192px in ở khổ A5
                # (ô 58px ~ 15mm) vẫn trên 300 dpi.
LE = 0.03       # lề trắng chừa quanh hình, theo tỉ lệ cạnh

# sha256 -> mã hình đồ. Đo ngày 09/09/2026 trên file danh mục hiện hành; đã xem
# từng ảnh bằng mắt để xác nhận đúng hình đồ nào (xem CLAUDE.md).
VAN_TAY = {
    '227e723fcfd64ab18988bcd3cf977eb2ffa38f37d78004d8fa1865fe75445ade': 'GHS01',
    'cd5f9a61edf52e19846046bb38573dfcd76ec3b42df07e822274154616dc6287': 'GHS02',
    '48a61605e06ca7382b6741c21cfafef8a15125a87bb2f575aab41e7f97785397': 'GHS03',
    '76f19a535ea4cc9cee19bd2c8ce9043a1f6d3439cad4403fad301a6172a98661': 'GHS04',
    'cf57192d7ac59332baa1d68175143f6e64503854b5e8a6abef43238d8bf9e767': 'GHS05',
    '2df99ca1f1125d63a77a9692e6dffdb9c4e5483dc3e216b51c5e58ff1a0a7b44': 'GHS06',
    '6eea98ed388bb5725fa4ffb855c186441921134c8f70b762e074123486397dea': 'GHS07',
    '9518f846def4a9c013d7c67477a754d67c57c040ffe0beb6af7bbdfe921a2501': 'GHS08',
    'effb98654095dec6c12fd98a37822080e848dd8100513e62216093bc684aeb13': 'GHS09',
}
TEN = {
    'GHS01': 'bom nổ', 'GHS02': 'ngọn lửa', 'GHS03': 'lửa trên vòng tròn',
    'GHS04': 'bình khí nén', 'GHS05': 'ăn mòn', 'GHS06': 'đầu lâu xương chéo',
    'GHS07': 'dấu chấm than', 'GHS08': 'nguy hại sức khỏe', 'GHS09': 'môi trường',
}


def _chuan_hoa(noi_dung):
    """Cắt lề trắng, đệm về khung VUÔNG, phóng về CANH x CANH.

    Ảnh trong Excel mỗi cái một tỉ lệ (190x171, 181x158, 169x168...) và lề trắng
    quanh hình cũng dày mỏng khác nhau. Thả nguyên vào một ô 44x44 với
    `background-size:contain` thì các hình đồ trên cùng một nhãn hiện ra to nhỏ
    lệch nhau, nhìn rõ khi chúng đứng cạnh nhau. Chuẩn hóa ở đây một lần để nhãn
    khỏi phải bận tâm.

    Giữ nền TRẮNG ĐỤC chứ không làm trong suốt: ruột hình kim cương vốn là màu
    trắng, xóa trắng đi thì thủng cả ruột hình.
    """
    im = Image.open(io.BytesIO(noi_dung)).convert('RGB')
    nen = Image.new('RGB', im.size, (255, 255, 255))
    khung = ImageChops.difference(im, nen).getbbox()
    if khung:
        im = im.crop(khung)

    canh = max(im.size)
    canh = int(round(canh / (1 - 2 * LE)))          # cộng thêm lề
    o = Image.new('RGB', (canh, canh), (255, 255, 255))
    o.paste(im, ((canh - im.width) // 2, (canh - im.height) // 2))

    ra = io.BytesIO()
    o.resize((CANH, CANH), Image.LANCZOS).save(ra, 'PNG', optimize=True)
    return ra.getvalue()


def main(data_dir):
    ra = os.path.join(data_dir, THU_MUC)
    os.makedirs(ra, exist_ok=True)

    if not os.path.exists(config.SRC_CHEM_LIST):
        sys.exit('Không thấy %s' % config.SRC_CHEM_LIST)

    with zipfile.ZipFile(config.SRC_CHEM_LIST) as z:
        anh = [n for n in z.namelist() if n.startswith('xl/media/')]
        thay, la = {}, []
        for n in sorted(anh):
            noi_dung = z.read(n)
            ma = VAN_TAY.get(hashlib.sha256(noi_dung).hexdigest())
            if ma is None:
                la.append((n, hashlib.sha256(noi_dung).hexdigest(), len(noi_dung)))
                continue
            thay[ma] = noi_dung

    if la:
        print('ẢNH LẠ trong %s — chưa biết là hình đồ nào:' % os.path.basename(config.SRC_CHEM_LIST))
        for n, h, kich_thuoc in la:
            print('  %-20s %s  %d bytes' % (n.rsplit('/', 1)[-1], h, kich_thuoc))
        print('  Xem tận mắt rồi thêm vân tay vào VAN_TAY trong file này.')

    thieu = [m for m in sorted(VAN_TAY.values()) if m not in thay]
    if thieu:
        sys.exit('DỪNG: thiếu hình đồ %s trong file danh mục — không ghi đè gì cả.\n'
                 '       Nhãn hóa chất sẽ tạm quay về hình vẽ tay trong app/ghs.py.'
                 % ', '.join(thieu))

    chuan = {ma: _chuan_hoa(nd) for ma, nd in thay.items()}
    for ma, noi_dung in sorted(chuan.items()):
        with open(os.path.join(ra, ma + '.png'), 'wb') as f:
            f.write(noi_dung)

    print('HÌNH ĐỒ GHS — trích từ %s' % os.path.basename(config.SRC_CHEM_LIST))
    print('  %d/9 hình vào %s (đã chuẩn hóa về %dx%d)'
          % (len(chuan), os.path.join(THU_MUC, ''), CANH, CANH))
    for ma in sorted(chuan):
        print('    %s  %-22s %6d -> %6d bytes'
              % (ma, TEN[ma], len(thay[ma]), len(chuan[ma])))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(config.ROOT, 'data'))
