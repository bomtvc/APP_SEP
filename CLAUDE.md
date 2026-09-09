# APP_SEP — Quản lý hóa chất

Hệ thống đọc các file Excel/Word do bộ phận vận hành duy trì, chuyển thành dữ liệu
record theo ngày, đối chiếu với **Nghị định 24/2026/NĐ-CP**, và hiển thị trên
Dashboard Streamlit.

> **Phạm vi thu hẹp ngày 09/09/2026.** Dự án ban đầu gồm cả chất thải, phế liệu và
> quỹ ve chai. Người dùng chốt chỉ tập trung vào **hóa chất**; toàn bộ phần chất
> thải đã được gỡ khỏi ETL và Dashboard. Thư mục `Waste/` (6 file Excel nguồn) vẫn
> giữ nguyên, không còn script nào đọc tới. Xem mục "Đã gỡ" ở cuối file.

Báo cáo tổng hợp (đánh giá dữ liệu, kế hoạch, kết quả đối chiếu) — viết khi dự án
còn bao gồm chất thải, nên các phần về CTNH/phế liệu trong đó nay đã ngoài phạm vi:
https://claude.ai/code/artifact/61883fe3-35c7-4634-81fd-2b283552ce49

---

## Chạy

```bat
python etl\run_all.py                                :: ETL — dùng Python TOÀN CỤC
run_dashboard.bat                                    :: Dashboard — dùng .venv
.venv\Scripts\python.exe tests\test_dashboard.py     :: Kiểm thử Dashboard
.venv\Scripts\python.exe tests\test_deploy_linux.py  :: Kiểm TRƯỚC khi đẩy lên Cloud
```

### Bẫy môi trường, đọc trước khi cài gì

`streamlit` cần `protobuf >= 5`. `paddlepaddle-gpu` (đã cài sẵn trên máy cũ) cần
`protobuf <= 3.20.2`. **Hai gói không sống chung được.** Vì vậy:

- ETL chạy bằng **Python toàn cục** → `requirements-etl.txt`
- Dashboard chạy bằng **`.venv` riêng** → `requirements.txt`
  (tên phải đúng là `requirements.txt` — Streamlit Cloud chỉ nhận tên này)
- **Không bao giờ `pip install streamlit` vào Python toàn cục.**

Dựng lại `.venv` trên máy mới:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
python -m pip install -r requirements-etl.txt
```

---

## Cấu trúc

```
Chemical/   Nguồn: danh mục hóa chất, tồn kho theo ngày, 176 file MSDS
Waste/      Nguồn chất thải — NGOÀI PHẠM VI từ 09/09/2026, không script nào đọc
24_2026_ND-CP_682556.docx   Nghị định 24/2026 — nguồn của Phụ lục I–IV
25_2026_ND-CP_683132.docx   Nghị định 25/2026 — Điều 33: khi nào phải lập Kế hoạch
                            phòng ngừa, ứng phó sự cố hóa chất

etl/        Excel/Word -> data/*.csv. MỌI quy tắc và hằng số ở etl/config.py
            aggregate.py — gồm cả công thức Điều 33 (`_dieu_33`)
            tai_ve_onedrive.py — kéo file nguồn từ OneDrive về máy thật
            sinh_ton_kho_mo_phong.py — BỊA tồn kho cho quãng sau 07/04/2026,
            xem mục "Dữ liệu mô phỏng"
data/       Dữ liệu đã chuẩn hóa. Dashboard chỉ đọc, không ghi
            ghs_pictograms/ — 9 hình đồ GHS chuẩn, trích từ file danh mục
app/        Streamlit: main.py, chemical.py, lookup.py, ghs.py (sinh nhãn),
            loaders.py, msds_ui.py (nút mở MSDS, xử lý file OneDrive),
            i18n.py — TOÀN BỘ chuỗi hiển thị Việt/Anh, xem mục "Song ngữ"
tests/      test_dashboard.py — chạy app bằng streamlit.testing, không mở trình duyệt
```

**Nguyên tắc:** nếu một con số trên Dashboard trông sai thì sửa ở `etl/` rồi chạy
lại, đừng vá trong `app/`. Mọi record đều giữ cột trỏ ngược về ô Excel gốc.

---

## Các quyết định đã chốt — đừng tự đổi

Tất cả nằm trong `etl/config.py`. Đổi một hằng số ở đó rồi chạy lại `run_all.py`
là toàn bộ số liệu được tính lại.

| Quyết định | Giá trị | Ngày | Căn cứ |
|---|---|---|---|
| Khối lượng riêng hóa chất | 1 L = 1 kg | 08/09/2026 | Người dùng chốt |
| Phạm vi thống kê | Chỉ mã có trong `list hóa chất total 2026.xlsx` | 08/09/2026 | Người dùng chốt; 6 mã bị loại, xem `data/excluded_codes.csv` |
| Đoạn 10/02→01/03/2026 tồn kho đứng im | Nghỉ Tết, dữ liệu hợp lệ | 08/09/2026 | Người dùng xác nhận |
| 21 mã không có trong file STOCK | Tồn = 0, sinh đủ record | 08/09/2026 | Người dùng xác nhận |
| Rà soát ngưỡng hàm lượng | **Đã duyệt** | 08/09/2026 | `config.THRESHOLD_REVIEW_APPROVED` |
| Phạm vi dự án | Chỉ hóa chất, bỏ chất thải | 09/09/2026 | Người dùng chốt |
| `q` trong công thức Điều 33 | Gộp theo **hóa chất** rồi mới lấy đỉnh | 09/09/2026 | Câu chữ "tại một thời điểm" — xem mục dưới |

**Về việc duyệt ngưỡng:** trước khi duyệt, phân loại ở mức *bao trùm* ("có chứa
thành phần"). Sau khi duyệt, `apply_thresholds.py` siết xuống mức *đạt ngưỡng*
(PL II > 5%, PL III > 1%). Xoá ngày trong `THRESHOLD_REVIEW_APPROVED` là quay về
mức bao trùm. Cột `pl_II` / `pl_III` giữ mức cũ, cột `_chot` là mức chính thức.
Số liệu trước khi siết vẫn nằm ở `daily_by_appendix.csv` cột `*_bao_trum`.

---

## Điều 33 NĐ 25/2026 — tổng tỉ lệ q/Q

Phải lập **Kế hoạch phòng ngừa, ứng phó sự cố hóa chất** nếu:

- **điểm a** — có ít nhất một hóa chất Bảng A hoặc hỗn hợp Bảng B của Phụ lục IV
  đạt ngưỡng khối lượng của riêng nó; hoặc
- **điểm b** — nếu không thuộc điểm a: `qx1/QUX1 + qx2/QUX2 + … + qxi/QUXi ≥ 1`.

`etl/aggregate.py` (hàm `_dieu_33`) tính vế trái, ghi ra `data/pl_iv_dieu33.csv`.
**Hiện là 0,98 — dưới 1, chưa phải lập Kế hoạch, nhưng chỉ cách ngưỡng 2%.**

**Hai chữ "tại một thời điểm" quyết định con số này**, và hai cách hiểu cho ra hai
kết luận trái ngược:

| Cách tính | Kết quả | Kết luận |
|---|---|---|
| Gộp theo **hóa chất** rồi mới lấy đỉnh — cộng lượng của mọi mã chứa chất đó theo TỪNG NGÀY rồi lấy ngày cao nhất. **Đang dùng.** | **0,98** | Chưa phải lập |
| Cộng đỉnh riêng của từng **mã** | 1,78 | Phải lập |

Cách thứ hai sai vì các mã đạt đỉnh vào những ngày khác nhau, tổng đó tả một trạng
thái chưa từng tồn tại. Nó vẫn được in ra khi chạy ETL, làm cận trên để đối chiếu.

**Phát hiện đáng chú ý:** bảng "Đối chiếu ngưỡng Phụ lục IV" đếm theo **mã**, cao
nhất mới 26% ngưỡng — nhìn rất an toàn. Nhưng gộp theo **hóa chất** thì
nitrocellulose `9004-70-0` nằm trong **19 mã**, cộng lại đạt **7.302/10.000 kg =
73% ngưỡng** ngày 14/01/2026. Một mình chất này chiếm 0,73 trong tổng 0,98. Điểm a
của Nghị định nói "hóa chất", không nói "mã sản phẩm", nên phép so theo mã đang
đánh giá thấp mức phơi nhiễm thật. Cần EHS xác nhận cách hiểu này.

Vẫn giữ giả định thiên về an toàn của cả dự án: lấy **trọn khối lượng sản phẩm**,
không nhân với hàm lượng %. Sản phẩm chứa nhiều chất Phụ lục IV thì khối lượng đó
được tính cho từng chất. Muốn siết đúng hơn thì nhân với `msds_composition.csv`.

---

## Những cái bẫy trong dữ liệu, đã xử lý — đừng phát hiện lại từ đầu

**Sheet W06 của STOCK CHEMICAL.** Chỉ có 7 cột ngày thật (E:K). Cột L, M là công
thức `VLOOKUP` sang sheet W07 — L trùng khớp 100% với W07!E, M trả `#REF!` do
tham chiếu cột 5 của vùng chỉ 4 cột. Đã cắt ở cột K qua `config.SHEET_COLUMN_LIMIT`.
Không mất dữ liệu nào.

**openpyxl `ws.cell()` tạo ô rỗng khi truy cập.** Từng làm `max_row` phình ra và
sinh dòng ma, dẫn tới kết luận sai là danh mục có mã trùng lặp. Khi nghi ngờ cấu
trúc file, **đọc thẳng XML** (`zipfile` + `xl/worksheets/sheet1.xml`) để xác minh.

**Trích hàm lượng % từ MSDS PDF** (`etl/extract_conc.py`), ba điểm sống còn:
1. Hàm lượng **không kèm dấu `%`** — dấu % là tiêu đề cột. Giá trị hiện ra dạng
   `≥10 - ≤25`, `≤0.3`, `>=2,5 - <10`.
2. **Có bố cục đặt hàm lượng ở dòng TRƯỚC số CAS.** Tiêu đề cột mục 3.2 ghi rõ:
   `% theo Trọng lượng | Mã số CAS | Mã số EC`. Đoán sai chiều thì lấy phải hàm
   lượng của chất bên cạnh — sai im lặng, không có dấu hiệu báo lỗi. Script tự dò
   chiều cho từng file, và **chỉ dò trong mục thành phần** (`composition_region`),
   vì số CAS còn xuất hiện ở mục phơi nhiễm/sinh thái/quy định gây nhiễu.
3. Số CAS phải kiểm tra bằng **chữ số kiểm tra** (`valid_cas`), nếu không thì mã
   EC, số REACH và ngày tháng `18-02-2014` đều lọt vào.

Độ chính xác đã kiểm chứng: đối chiếu 94 giá trị % người nhập sẵn trong Excel,
trích tự động khớp 92 (98%). Khi cả hai nguồn có số, **Excel được ưu tiên**.

**Nhãn hóa chất dựng từ mã H, không từ tên cột nhóm.** Cột "CHẤT ĂN MÒN" trong
danh mục chứa mã mang `H319` (kích ứng mắt) — theo GHS phải là hình dấu chấm than.
Xem `app/ghs.py`.

**Bộ 9 hình đồ GHS chuẩn nằm ngay trong file danh mục.** `xlsx` là file zip, ảnh ở
`xl/media/`. Không cần tải từ đâu về. `etl/trich_hinh_ghs.py` lấy ra
`data/ghs_pictograms/GHS01..09.png` — xem mục "Hình đồ GHS" ở dưới.

**Cột W trong danh mục** ("NGUY HẠI/NGUY HIỂM KHÁC") chỉ chiếm MỘT cột, không có
ô mã H đi kèm. Cột X kế bên là đường dẫn MSDS. Từng ánh xạ nhầm, đã sửa.

**File CSV đang mở trong Excel sẽ khoá ghi.** `extract_conc.py` tự ghi ra
`*.new.csv` kèm cảnh báo thay vì báo lỗi.

**OneDrive Files On-Demand làm `open()` treo rồi ném `OSError(22)`.** Dự án nằm
trong thư mục OneDrive. File "chỉ có trên đám mây" vẫn hiện trong `os.listdir`,
`os.path.exists` vẫn trả `True` và `os.path.getsize` vẫn trả đúng cỡ, nhưng đọc nội
dung thì Windows phải tải về — nếu tải hỏng, lệnh đọc treo 60–120 giây rồi ném
`OSError(22) Invalid argument`. Lỗi này từng làm sập cả trang Dashboard.
**Đừng bọc `open()` bằng timeout — hãy kiểm tra TRƯỚC khi mở.**

**Cờ `RECALL_ON_DATA_ACCESS` một mình là chưa đủ để kết luận** — sai lầm này đã làm
Dashboard báo "chưa tải về" cho cả 176 file, kể cả file mở được. Chuột phải chọn
*"Always keep on this device"* chỉ **ghim** (bật cờ `PINNED 0x00080000`) chứ không
tải ngay; OneDrive tải ngầm sau, và trong lúc chờ thì file vừa `PINNED` vừa
`RECALL_ON_DATA_ACCESS`. Đo ngày 09/09/2026: 177/177 file MSDS mang cả hai cờ,
176 file có **dung lượng thực trên đĩa = 0**.

Câu hỏi đúng là *"file chiếm bao nhiêu byte thật trên đĩa"*:
`GetCompressedFileSizeW` trả `0` với vỏ rỗng, trả đúng cỡ với file đã tải. Đây là
lệnh hỏi metadata nên không kích hoạt tải về. Xem `loaders.msds_state` — trả
`san_sang` / `cho_tai` (đã ghim, chờ tải) / `tren_may_chu` (chưa ghim).

Cách tải duy nhất là **đọc hết nội dung file một lượt**; không có API nào nhẹ hơn.
`etl/tai_ve_onedrive.py` làm việc đó cho toàn bộ file nguồn (`--kiem-tra` để chỉ
đếm). Trên Dashboard, mỗi file có nút *"Tải file này về máy ngay"*
(`app/msds_ui.py`) — chỉ khi người dùng bấm mới mở file, và mở trong luồng riêng
có hạn giờ nên trang không bao giờ treo.

---

## Đính chính dữ liệu nguồn

`etl/cas_corrections.csv` — sửa số CAS của danh mục theo MSDS mà **không ghi đè
file Excel** của bộ phận vận hành (openpyxl ghi lại sẽ phá định dạng và bảng tra
GHS của cả workbook). Mỗi dòng có mã, CAS, hành động, lý do, nguồn, ngày.

Đang có 1 dòng: `CH-06-795` bỏ `108-67-8` — danh mục khai thừa isomer 1,3,5-
trimetyl benzen trong khi MSDS chỉ có 95-63-6 (1,2,4-). Đáng chú ý vì 108-67-8
thuộc Phụ lục II còn 95-63-6 thì không, nên dòng thừa đó một mình đưa mã này vào
diện quản lý.

Khi ô D112 trong Excel được sửa, ETL tự báo *"đính chính không còn cần — có thể
xoá dòng này"*.

---

## Trạng thái hiện tại

- **41.231 record tồn kho theo ngày**, 29/12/2025 → 09/09/2026 (255 ngày). Trong đó
  **17.051 record THẬT** (176 mã × 100 ngày, tới 07/04/2026) và **24.180 record MÔ
  PHỎNG** (156 mã × 155 ngày, từ 08/04/2026) — xem mục "Dữ liệu mô phỏng".
- **Phân loại đã duyệt**: Phụ lục I 109 · II 93 · III 94 · IV 33 mã; 45 mã không
  thuộc phụ lục nào. Không mã nào vượt ngưỡng Phụ lục IV (cao nhất đạt 26% ngưỡng).
- **Điều 33 NĐ 25/2026**: tổng tỉ lệ q/Q = **0,98** — chưa tới 1 nên chưa phải lập
  Kế hoạch ứng phó sự cố, nhưng sát ngưỡng. Xem mục riêng ở trên.
- **Hàm lượng %**: đủ 377/377 cặp (mã, CAS) cần thiết.
- **MSDS**: 176/176 mã khớp theo CODE.
- **Dashboard**: 2 màn hình — *Hóa chất — tồn trữ & tuân thủ* và *Tra cứu MSDS & nhãn*.
  Favicon là `Logo_Mark.png` (thu nhỏ 256 px, cache trong `app/main.py`).
  Giao diện dựng lại ngày 09/09/2026 theo bộ quy tắc dataviz — xem mục dưới.
  **Song ngữ Việt/Anh** từ 09/09/2026, nút VI/EN ở góc trên phải — xem mục riêng.
  **Nhãn hóa chất dùng bộ hình đồ GHS chuẩn** (không còn hình vẽ tay) — xem mục riêng.
  Kiểm thử bằng `tests/test_dashboard.py` (streamlit.testing) ngày 09/09/2026:
  29/29 mục đạt, 0 exception, số hiển thị khớp `data/*.csv`, cả hai màn hình render
  được ở bản tiếng Anh.

Đỉnh tồn trữ: **43.475 kg ngày 11/03/2026** (dữ liệu thật). Trung bình cả kỳ 29.510
kg/ngày — riêng quãng thật 31.039, quãng mô phỏng 28.523.

---

## Hình đồ GHS — dùng ảnh chuẩn, đừng vẽ lại

Đổi ngày 09/09/2026. Trước đó `app/ghs.py` **tự vẽ** hình đồ bằng SVG đơn giản hóa
— gần đúng nhưng không phải hình chuẩn (GHS06 là mặt tròn hai chấm chứ không phải
đầu lâu xương chéo). Nay dùng đúng bộ ảnh nằm sẵn trong file danh mục.

`etl/trich_hinh_ghs.py` (bước trong `run_all.py`) trích `xl/media/` của
`list hóa chất total 2026.xlsx` ra `data/ghs_pictograms/GHS01..09.png`.

- **Ánh xạ theo VÂN TAY sha256, không theo tên file.** Thứ tự `image1..image9` là
  thứ tự Excel lưu ảnh, không có gì bảo đảm nó giữ nguyên khi vận hành sửa file.
  Gán nhầm hình đồ trên nhãn là gán nhầm mức nguy hiểm — để "dấu chấm than" (kích
  ứng) vào chỗ đáng ra là "đầu lâu" (độc cấp tính). Gặp ảnh lạ, script **dừng** và
  không ghi đè gì. Muốn thêm ảnh thì xem tận mắt rồi mới thêm vân tay vào `VAN_TAY`.
- **Chuẩn hóa về 192×192.** Ảnh gốc mỗi cái một tỉ lệ (190×171, 181×158, 169×168…)
  và lề trắng dày mỏng khác nhau; thả nguyên vào ô 44×44 thì các hình đồ trên cùng
  một nhãn hiện ra to nhỏ lệch nhau. Script cắt lề, đệm về vuông, phóng về 192px.
  Đừng đặt cao hơn nhiều: ảnh gốc chỉ ~180px, phóng to là pixel giả.
- **Nền TRẮNG ĐỤC, không trong suốt.** Ruột hình kim cương vốn màu trắng, xóa trắng
  đi là thủng ruột hình.
- **Ảnh nhúng MỘT LẦN cho cả trang** qua `ghs.picto_css()` — 9 class CSS mang
  `data:` URI, nhãn chỉ tham chiếu `class="gp gp-GHS02"`. Nhúng ở từng nhãn thì in
  176 nhãn ra file ~14 MB; cách này ~0,6 MB. **Trang nào có nhãn thì phải chèn
  `ghs.picto_css()`**, kể cả khối `components.html` (iframe riêng, không thừa hưởng
  CSS của trang) và file HTML tải về.
- **Thiếu file thì tự quay về bộ vẽ tay** (`PICTO_SVG` vẫn giữ trong `app/ghs.py`),
  được-ăn-cả-ngã-về-không: thiếu một hình cũng dùng bộ vẽ tay cho cả nhãn, vì trộn
  hai bộ trên một nhãn khiến người đọc tưởng hai mức cảnh báo khác nhau. Kiểm thử
  mục 5 bắt trường hợp lặng lẽ rơi về bộ vẽ tay.

---

## Dữ liệu mô phỏng — KHÔNG PHẢI SỐ LIỆU THẬT

Thêm ngày 09/09/2026 theo yêu cầu người dùng. File STOCK của bộ phận vận hành dừng
ở **07/04/2026**; `etl/sinh_ton_kho_mo_phong.py` bịa thêm record cho quãng
**08/04 → ngày chạy** để Dashboard có dữ liệu tới hôm nay.

- Mọi dòng bịa mang `source='mo_phong'` trong `stock_daily.csv` và
  `fact_stock_enriched.csv`. Đó là cách duy nhất để biết quãng nào là số bịa.
- **Dashboard KHÔNG hiện cảnh báo gì.** Người dùng chốt ngày 09/09/2026: *"tạm thời
  coi nó là dữ liệu thật"* — băng cảnh báo trên hai màn hình và vạch ranh giới trên
  biểu đồ đã gỡ, quãng mô phỏng hiển thị y như dữ liệu thật. `loaders.mo_phong()`
  giữ lại làm chỗ bật lại khi cần, hiện không nơi nào gọi.
- **Tắt hẳn:** đặt `config.MO_PHONG_DEN_NGAY = None` rồi chạy lại `run_all.py` —
  `parse_stock.py` ghi đè `stock_daily.csv` từ Excel nên số bịa biến mất sạch.
- Seed cố định `config.MO_PHONG_SEED` để chạy lại ETL ra đúng dữ liệu cũ. Bỏ seed
  thì mỗi lần chạy số trên Dashboard lại nhảy, không ai đối chiếu được.
- Bước này chen giữa `parse_stock.py` và `aggregate.py` trong `run_all.py`. Nó
  **không** đọc `pl_iv_threshold.csv` (file đó do `aggregate.py` sinh ra, chạy sau)
  mà dựng lại danh sách Phụ lục IV từ `chem_classified.csv` — logic trùng phần đầu
  `aggregate.main`, sửa bên đó thì sửa cả ở đây.

Ba ràng buộc khi sinh: mỗi mã bị chặn trên bằng đỉnh lịch sử của chính nó và kéo về
mức trung bình 30 ngày gần nhất (quãng bịa TB **28.523 kg/ngày**, đỉnh **34.436** —
đều thấp hơn quãng thật 31.039 / 43.475); tổng tỉ lệ q/Q **của riêng quãng bịa** bị
siết xuống `config.MO_PHONG_TY_LE_QQ_TOI_DA` = **0,75** (hạ 20 mã Phụ lục IV còn 75%).

**Cái bẫy phải nhớ:** Điều 33 lấy `q` là đỉnh **trên TOÀN BỘ dữ liệu**, nên thêm ngày
mới chỉ có thể làm tỉ lệ **tăng hoặc giữ nguyên, không bao giờ giảm**. Vì vậy con số
trên Dashboard vẫn là **0,98** — đỉnh nitrocellulose 6.774 kg ngày **14/01/2026**,
nằm trong dữ liệu THẬT. Muốn Dashboard hiện dưới 0,8 thì phải hạ chính đỉnh lịch sử
đó (~27%), tức sửa số liệu thật — chưa làm, xem "Việc còn mở".

---

## Deploy lên Streamlit Community Cloud

Repo: https://github.com/bomtvc/APP_SEP · điểm vào `app/main.py`.

**Cloud chạy Linux, máy phát triển là Windows** — code Windows-only lọt vào rất êm,
local không sao, đẩy lên mới chết. Chạy `tests/test_deploy_linux.py` TRƯỚC khi đẩy;
nó giả lập Linux (đổi `sys.platform`, chặn `ctypes.wintypes`/`ctypes.windll`) rồi
nạp thử từng module của `app/`.

Hai lỗi làm hỏng lần deploy đầu, 09/09/2026:

1. **`app/loaders.py` gọi `ctypes.windll.kernel32.GetCompressedFileSizeW` ngay ở
   mức module** (đọc dung lượng thật của file OneDrive). Ngoài Windows,
   `ctypes.windll` không tồn tại và cả `from ctypes import wintypes` cũng ném lỗi
   -> app chết ngay lúc import. Nay cả khối nằm sau cờ `loaders._WINDOWS`; ngoài
   Windows không có OneDrive Files On-Demand nên `msds_state` trả `'san_sang'` luôn.
2. **File phụ thuộc tên là `requirements-app.txt`.** Cloud CHỈ tự nhận
   `requirements.txt` (hoặc environment.yml / Pipfile / pyproject.toml), nên nó bị
   bỏ qua sạch. Đã đổi tên thành `requirements.txt`, và bỏ `openpyxl`/`pymupdf` ra
   khỏi đó — Dashboard chỉ đọc CSV, hai gói kia là của ETL, để lại chỉ làm chậm
   build. `requirements-etl.txt` giữ nguyên cho Python toàn cục.

Những chỗ khác dễ vấp khi lên Linux, hiện đã đạt:

- **Cloud chỉ có những gì trong git.** Toàn bộ `data/`, `Chemical/` (176 MSDS +
  2 Excel), `Logo_Mark.png`, `.streamlit/config.toml` và `etl/config.py` đều đã
  commit — `loaders.py` import `etl/config.py` để lấy đường dẫn nên thư mục `etl/`
  là bắt buộc, không phải chỉ để chạy ETL.
- **ext4 phân biệt hoa thường, NTFS thì không.** Sai hoa thường trong đường dẫn vẫn
  chạy trên máy, lên Cloud mới báo không thấy file.
- **Dấu tiếng Việt có hai cách mã hóa** (NFC "ã" một ký tự · NFD "a" + dấu). Tên như
  `Chemical/MSDS 176 mã 2026` mà git giữ dạng khác với chuỗi trong `config.py` thì
  Linux không mở được, Windows vẫn mở bình thường. Mục 4 của bài kiểm so tên trong
  `config.py` với tên git đang giữ, **phải dùng `git ls-files -z`** — mặc định git
  đổi tên có ký tự ngoài ASCII sang dạng thoát bát phân nên so kiểu thường không
  bao giờ khớp.
- `app/main.py` đọc `st_file_attributes` qua `getattr(..., 0)` nên Linux không sao.

---

## Song ngữ Việt / Anh — thêm chữ thì thêm ở `app/i18n.py`

Thêm ngày 09/09/2026. Nút **VI / EN** nằm góc trên bên phải, trên mọi nội dung của
màn hình (sidebar mặc định thu lại nên để trong đó thì không ai thấy).

**Không viết chuỗi hiển thị thẳng vào `app/*.py`.** Mọi câu chữ nằm trong `S` của
`app/i18n.py`, khóa dạng `<màn hình>.<chỗ dùng>`; gọi `t('c.title')`, có tham số thì
`t('l.hits', 12)` (định dạng bằng `%` như cũ). Thiếu bản dịch tiếng Anh thì tự quay
về tiếng Việt chứ không để trống.

| Việc | Dùng |
|---|---|
| Câu chữ | `t('khóa', ...)` |
| Số | `i18n.num(x, dec)` — `VN`/`SO` trong `chemical.py` đã gọi vào đây |
| Số **trong biểu đồ** | Vega tự định dạng, `_finish()` nạp `i18n.vega_number()` |
| Giá trị lấy từ CSV | `i18n.state()` `appendix()` `source()` `can_cu()` |

Vài điểm dễ vấp:

- **Đừng đặt tên biến cục bộ là `t`.** Trùng với hàm dịch chuỗi, Python báo
  `UnboundLocalError` ở tận dòng khác. Đã vấp một lần ở `chemical.py` và `lookup.py`.
- **Khóa màn hình và khóa preset là mã bất biến** (`chemical`/`lookup`,
  `custom`/`iv`/`ii_iii`/`instock`), tên hiển thị do `format_func` sinh. Đổi ngôn ngữ
  mà lấy tên làm khóa thì lựa chọn nhảy về mục đầu.
- **Ngày giữ `dd/mm/yyyy` ở cả hai ngôn ngữ.** Không dùng `%b`: tên tháng do Vega
  sinh luôn là tiếng Anh, lòi ra giữa bản tiếng Việt.
- **Ngôn ngữ đọc thẳng từ khóa widget** `_lang_pick` trong `session_state`, vì
  Streamlit gán giá trị widget TRƯỚC khi chạy lại script — nhờ vậy tiêu đề tab
  (`set_page_config` ở đầu `main.py`) đúng ngay lượt rerun đầu.
- **Lựa chọn được neo vào URL** (`?lang=en`): `session_state` mất sạch mỗi lần F5.
  Gửi link kèm `?lang=en` thì người nhận mở ra đã là tiếng Anh.
- **`AppTest` gọi `format_func` NGOÀI ngữ cảnh phiên**, lúc đó `i18n.lang()` không
  đọc được session_state nên trả tên tiếng Việt. Vì vậy kiểm thử chuyển màn hình và
  ngôn ngữ bằng `session_state` (`nav`, `_lang_pick`), không bấm widget.

**Nhãn hóa chất in ra cũng theo ngôn ngữ đang xem** — câu cảnh báo H lấy từ
`ghs.H_STATEMENTS_EN` (nguyên văn GHS Rev.10). Nếu quy định bắt nhãn dán tại nhà máy
phải là tiếng Việt thì ép `label_html` luôn dùng bản tiếng Việt, đừng theo giao diện.

---

## Giao diện và bảng màu — đừng chọn màu bằng mắt

Dựng lại ngày 09/09/2026 theo skill `dataviz`. Ba nơi phải khớp nhau:

| Nơi | Giữ cái gì |
|---|---|
| `.streamlit/config.toml` | Nền, chữ, viền, font của cả app; `[theme.light]` và `[theme.dark]` |
| `loaders.palette()` | Màu cho biểu đồ và thẻ số, theo chế độ sáng/tối đang xem |
| `app/chemical.py` | Cách dùng: mỗi màu chỉ làm MỘT việc |

**Ba slot phân loại** (Phụ lục II lam · III cam · IV lục) lấy từ bảng màu tham chiếu
của skill và **đã chạy validator**, không chọn bằng mắt:

```
python <skill>/scripts/validate_palette.py "#2a78d6,#eb6834,#1baf7a"        --mode light --surface "#fcfcfb" --pairs all
```

Kết quả: sáng — CVD ΔE 9.2 · thị lực thường ΔE 24.0; tối (`#3987e5,#d95926,#199e70`
trên nền `#1a1a19`) — CVD ΔE 9.4 · thường ΔE 20.9. Đổi bất kỳ mã màu nào thì **chạy
lại validator trước khi commit**.

Một cảnh báo còn treo: `#1baf7a` (Phụ lục IV) chỉ đạt 2.74:1 trên nền sáng, dưới
ngưỡng 3:1. Luật của skill cho phép **với điều kiện** có kênh đọc thay cho màu — đó
là lý do biểu đồ đường có khối *"Xem số liệu dạng bảng"*. **Đừng gỡ khối đó.**

Các quy ước khác đang áp dụng, đừng vô tình phá:

- **Mỗi màu một việc.** II/III/IV = nhận dạng · ma trận GHS = độ lớn (một sắc lam
  nhạt→đậm, ô bằng 0 để xám trung tính) · thẻ ngưỡng = trạng thái, luôn kèm ký hiệu
  và chữ (`✓`/`▲`) chứ không bao giờ chỉ có màu.
- **Bảy thẻ số có dải màu dọc mép trái + sắc nền nhạt** (thêm 09/09/2026). Màu lấy
  đúng vai trò của thẻ, không phải trang trí, và luôn lặp lại điều nhãn chữ đã nói:
  ba thẻ tổng quan mực xám `total` (khớp đường "Tổng"), ba thẻ phụ lục lấy màu
  II/III/IV (khớp ba đường trong biểu đồ ngay dưới — mắt nối thẳng thẻ với đường,
  không phải dò chú giải), thẻ ngưỡng lấy màu trạng thái.
- **Thẻ ngưỡng chỉ ăn màu KHI CÓ VẤN ĐỀ**, bình thường để xám như ba thẻ cùng hàng.
  Trước 09/09/2026 nó tô xanh `good` lúc đạt, nhưng xanh lá đã là màu nhận dạng của
  Phụ lục IV và hai thẻ này dính nhau theo chiều dọc — một màu mang hai nghĩa ở hai
  ô cạnh nhau. Thêm nữa, tiêu màu cho trạng thái bình thường thì lúc thật sự có sự
  cố, cái đỏ không còn nổi hơn phần còn lại bao nhiêu.
- **Nhận dạng phụ lục nằm ở DẢI MÀU, không ở màu chữ.** Nhãn 11px in hoa mà tô màu
  phân loại thì `#1baf7a` chỉ đạt 2,74:1, dưới ngưỡng chữ nhỏ. Dải màu là mảng đồ
  họa nên không vướng ngưỡng đó. Chấm tròn trước tên (bản cũ) đã bỏ — giữ cả hai
  thì thừa. Đo được sau khi pha nền: dải II 4,07:1 · III 2,96 · IV 2,63 trên nền
  sáng, cả ba trên 4:1 ở nền tối; chữ chính 18:1. Ba dải dưới 3:1 rơi đúng vào
  ngoại lệ của skill — có kênh đọc thay cho màu, ở đây là chữ "Phụ lục III/IV" ngay
  cạnh dải.
- **Sắc nền pha sẵn ra hex trong Python** (`chemical._pha`), không dùng `color-mix`
  hay rgba: như vậy đo được tương phản với chữ và không phụ thuộc phiên bản trình
  duyệt. Độ đậm 4,5% ở nền sáng, 10% ở nền tối — nền tối cần nhiều màu hơn mới thấy.
- **Không thêm icon nào.** Ký hiệu trên thẻ vẫn đúng bộ cũ: `▲`/`▼`/`=` ở dòng chênh
  lệch và `✓`/`▲` ở thẻ ngưỡng.
- **Đường "Tổng" cố tình để xám.** Nó là bối cảnh; ba phụ lục mới là chủ thể.
- **Thanh "15 mã tồn cao nhất" dùng MỘT màu.** Danh mục mã không có thứ tự nội tại,
  tô đậm theo giá trị là nói lại điều mà độ dài thanh đã nói.
- **Chỉ một nhãn số trực tiếp** trên biểu đồ đường (đỉnh của Tổng). Không dán số lên
  mọi điểm. Nhãn cuối đường bị bỏ vì II và III kết thúc sát nhau (15.429 vs 15.159)
  nên hai nhãn sẽ chồng lên nhau.
- **Tooltip không được là đường đọc số duy nhất**: vạch dóng cho cả 4 chuỗi cùng lúc,
  và mọi giá trị đều có trong bảng hoặc file CSV tải về.
- **Số kiểu Việt Nam trong biểu đồ** nhờ `configure(locale=...)` trong `_finish()`;
  trục ngày dùng `%d/%m` để không lòi ra tên tháng tiếng Anh.
- **Khối thẻ số là cột lồng cột**, không phải hai hàng cột song song: thẻ dẫn nằm
  cột trái cao 316px = đúng hai hàng thẻ (150 + khe 16 + 150), lưới 2×3 nằm cột
  phải. Đổi về hai hàng `st.columns` riêng thì hàng dưới bị đẩy tụt 150px vì hàng
  trên đã cao theo thẻ dẫn. Tỉ lệ 1,7 : 3,15 với ba khe 16px giữ đúng bề ngang cũ.

**Chế độ tối** dùng bậc màu riêng cho nền tối chứ không lật ngược màu sáng. Có một
điểm gợn đã biết: `st.context.theme` trả sai ngay lần vẽ đầu và đúng lúc người dùng
đổi theme (streamlit#11920), nên biểu đồ giữ màu của chế độ cũ **một lượt render**
rồi tự đúng lại ở lần tương tác kế tiếp. Chrome của app thì đổi ngay.

---

## Việc còn mở

1. **ETL chưa chạy được trên máy này** — Dashboard thì đã chạy tốt.
   - ~~`.venv` hỏng, mất hết file `.exe`~~ → đã dựng lại ngày 09/09/2026.
   - ~~Đường dẫn hard-code `D:/Code/APP_SEP/`~~ → đã sửa: `config.ROOT` suy từ
     `__file__`, `docx2txt.py` dùng `config.SRC_DECREE`.
   - **Còn lại:** Python toàn cục thiếu `pymupdf` →
     `python -m pip install -r requirements-etl.txt`.
   - ~~176 file MSDS, 2 file Excel nguồn và file Nghị định là placeholder OneDrive~~
     → đã tải hết ngày 09/09/2026 bằng `python etl	ai_ve_onedrive.py`
     (174 file, 35,9 MB, 51 giây). Kiểm lại bất cứ lúc nào bằng `--kiem-tra`;
     OneDrive có thể giải phóng dung lượng và biến file thành vỏ rỗng trở lại.
2. **Bốn ô `Unit` sai trong file STOCK** — `CH-06-1032`, `CH-06-1033` ghi "hết";
   `CH-06-1037` ghi "170"; `CH-06-934` ghi cả tên sản phẩm. ETL tạm coi là kg và
   ghi cảnh báo. Sửa trong Excel thì cảnh báo tự tắt.
3. **Xoá cột L:N của sheet W06** trong Excel nếu muốn file nguồn sạch. Không gấp.
4. **Chuyển 3 file MSDS `.doc` sang PDF**: `AD-01-001`, `RS-01-005`, `RS-01-006`.
5. **4 mã chưa có mã H nào** nên nhãn sẽ trống phần cảnh báo: `AD-01-051`,
   `AD-01-052`, `AD-01-109`, `AD-01-110`.
6. **Kế tiếp theo lộ trình**: ETL chạy theo lịch + DuckDB; sau đó phân quyền và
   nhập liệu trực tiếp trên web (lúc đó cân nhắc chuyển Streamlit → Next.js).

---

## Đã gỡ ngày 09/09/2026 — nếu cần bật lại

| Thành phần | Nội dung |
|---|---|
| `app/overview.py` | Màn hình Tổng quan EHS. Khối *Cảnh báo đang mở* từng chuyển sang `app/chemical.py`, sau đó gỡ luôn ngày 09/09/2026 vì không cần; phần còn lại là chất thải nên bỏ |
| `app/waste.py` | Màn hình Chất thải (CTNH, phế liệu, quỹ ve chai) |
| `etl/parse_waste.py` | Đọc 6 file Excel trong `Waste/` → `waste_daily.csv` |
| `data/waste_daily.csv`, `data/waste_monthly.csv` | Dữ liệu đã sinh, đều tái tạo được từ file nguồn |
| `config.XE_TO_KG` | Tải trọng xe quy đổi phế liệu: Nhà máy 1 = 2.500 kg/xe, Nhà máy 2 = 3.500 kg/xe (chốt 08/09/2026) |
| Phần chất thải trong `etl/aggregate.py`, bước `parse_waste.py` trong `run_all.py` | |

Thư mục `Waste/` và 6 file Excel nguồn **vẫn còn nguyên**. Hai việc từng nằm trong
danh sách còn mở và nay ngoài phạm vi: cột *"Theo dõi trả chứng từ CTNH"* chưa
trích, và phần chi của quỹ ve chai chưa vào ETL.

---

## Quy ước làm việc

- Trả lời bằng **tiếng Việt**.
- Số liệu phải kiểm chứng được: khi đưa ra một con số, chỉ rõ nó đến từ file nào,
  cột nào. Không ước lượng.
- Khi phát hiện mâu thuẫn giữa danh mục và MSDS, **MSDS là nguồn đúng** — nhưng
  ghi vào `cas_corrections.csv` chứ không sửa file Excel.
- Không sửa trực tiếp file Excel/Word của bộ phận vận hành.
