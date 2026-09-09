# Dashboard Hóa chất

## Chạy

```
run_dashboard.bat
```

hoặc `.venv\Scripts\streamlit.exe run app\main.py`. Trình duyệt mở ở `http://localhost:8501`.

## Hai màn hình

| Màn hình | Nội dung |
|---|---|
| **Hóa chất — tồn trữ & tuân thủ** | Thẻ số tồn trữ, cảnh báo đang mở, đường tồn trữ theo ngày, đối chiếu ngưỡng Phụ lục IV, ma trận GHS, tra cứu từng mã, xuất báo cáo |
| **Tra cứu MSDS & nhãn** | Tìm theo mã/tên/CAS, mở MSDS, sinh nhãn hóa chất khổ A5/A6, in hàng loạt |

Phần chất thải, phế liệu và quỹ ve chai đã được gỡ ngày 09/09/2026 khi phạm vi dự
án thu hẹp còn hóa chất. Chi tiết những gì đã gỡ và cách bật lại: xem `CLAUDE.md`.

## Kiểm thử

```
.venv\Scripts\python.exe tests\test_dashboard.py
```

Chạy app thật bằng `streamlit.testing`, không mở trình duyệt. Thoát 0 nếu tất cả
đạt. Nên chạy sau mỗi lần sửa `app/` hoặc chạy lại ETL.

## Cập nhật số liệu

Dashboard chỉ đọc các file CSV trong `data/`. Sau khi nhận file Excel mới từ bộ
phận vận hành, chạy lại ETL rồi tải lại trang:

```
python etl\run_all.py
```

## Vì sao có thư mục .venv riêng

`streamlit` cần `protobuf >= 5`, trong khi `paddlepaddle-gpu` cài sẵn trên máy này
yêu cầu `protobuf <= 3.20.2`. Hai gói không sống chung được trong một môi trường,
nên Dashboard chạy trong `.venv` riêng. Python toàn cục giữ `protobuf 3.20.2` để
paddlepaddle không hỏng.

**ETL chạy bằng Python toàn cục. Dashboard chạy bằng `.venv`.** Đừng cài streamlit
vào Python toàn cục.

## Cấu trúc

```
etl/     Đọc Excel/Word -> data/*.csv. Mọi quy tắc và hằng số ở etl/config.py.
data/    Dữ liệu đã chuẩn hóa. Dashboard chỉ đọc, không ghi.
app/     Giao diện Streamlit.
           main.py      điểm vào, danh sách màn hình
           chemical.py  Hóa chất — tồn trữ và tuân thủ
           lookup.py    Tra cứu MSDS và nhãn
           ghs.py       Suy ra hình đồ, từ cảnh báo và câu H cho nhãn
           loaders.py   Nạp và cache dữ liệu
```

Nếu một con số trên Dashboard trông sai, sửa ở `etl/` rồi chạy lại — đừng vá
trong `app/`.

## Về nhãn hóa chất

Hình đồ cảnh báo và từ cảnh báo được suy ra từ **mã H** trong danh mục, không từ
tên cột nhóm nguy hại — vì cột "CHẤT ĂN MÒN" có mã mang H319 (kích ứng mắt), theo
GHS phải dùng hình dấu chấm than chứ không phải hình ăn mòn.

Nhãn là **đề xuất**. Trước khi in hàng loạt, EHS cần đối chiếu Mục 2 của MSDS gốc.
Bốn mã chưa có mã H nào trong danh mục (`AD-01-051`, `AD-01-052`, `AD-01-109`,
`AD-01-110`) sẽ ra nhãn trống phần cảnh báo — app có cảnh báo riêng cho việc này.
