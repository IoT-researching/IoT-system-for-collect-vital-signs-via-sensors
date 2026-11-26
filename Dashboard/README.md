# Dashboard HR / SpO₂ – TV4 (Database + Dashboard)

Phần việc của **TV4** trong đề tài NCKH *"Hệ thống IoT thu thập tín hiệu sự sống – Nhịp tim (HR) và SpO₂"*:
lưu dữ liệu vào **Microsoft SQL Server** và hiển thị bằng **Streamlit**.

> ⚠️ **Nguyên mẫu nghiên cứu, không phải thiết bị y tế.** SpO₂ lấy từ nguồn RED/IR **mô phỏng**, chưa hiệu chuẩn,
> không có độ chính xác y tế. Cảnh báo trên dashboard chỉ là cảnh báo demo. BIDMC (PhysioNet) chỉ là dữ liệu
> tham chiếu cho nghiên cứu, không phải tín hiệu đo từ MAX30102.

## 1. Luồng dữ liệu

```
RED/IR mô phỏng → ESP32/Wokwi → Wi-Fi/MQTT → Python Subscriber (TV3) → SQL Server → Streamlit (TV4)
```

TV4 chỉ **đọc** CSDL (dashboard). Việc **ghi** từ MQTT là của TV3; hàm `hrdash.db.insert_measurement()` có thể dùng
lại nếu cần (tự kiểm tra trùng `device_id + sequence`).

## 2. Cấu trúc thư mục

```
app.py                      Dashboard Streamlit (4 tab)
hrdash/config.py            Cấu hình, ngưỡng, nhãn SpO₂ mô phỏng (đọc từ .env)
hrdash/db.py                Định nghĩa bảng, kết nối, hàm ghi dùng chung
hrdash/queries.py           Truy vấn đọc dữ liệu (chạy được trên SQL Server và SQLite)
hrdash/logic.py             Trạng thái node, khoảng mất/không hợp lệ, cảnh báo, ghép tham chiếu, MAE/RMSE
hrdash/charts.py            Biểu đồ Plotly
sql/01_create_schema.sql    Tạo CSDL HRSpO2Db, bảng devices, measurements
sql/02_views_and_queries.sql  View trạng thái node, chất lượng dữ liệu, khoảng mất/không hợp lệ
sql/03_reference_tables.sql   Bảng tham chiếu BIDMC và HR ước lượng
tools/seed_demo_data.py     Sinh dữ liệu demo theo kịch bản (sạch, cũ, offline, mất dữ liệu, ...)
tools/import_bidmc.py       Nạp numerics BIDMC và CSV HR ước lượng
docs/                       Báo cáo phần Database/Dashboard, checklist kiểm tra giao diện
```

## 3. Yêu cầu

- Python 3.10+ (khuyến nghị 3.11 trở lên)
- Microsoft SQL Server (Express/Developer đều được) và **ODBC Driver 18 for SQL Server**
  (cài từ trang Microsoft; trên Windows dùng bản x64)
- Không có SQL Server? Dùng chế độ demo SQLite (mục 5.B)

## 4. Cài đặt

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env   rồi sửa .env
```

## 5. Chuẩn bị CSDL

### A. SQL Server (chính thức)

1. Mở SQL Server Management Studio (hoặc `sqlcmd`) và chạy lần lượt:
   `sql/01_create_schema.sql` → `sql/03_reference_tables.sql` → `sql/02_views_and_queries.sql`
2. Trong `.env` đặt `DB_BACKEND=mssql`, `SQL_SERVER`, `SQL_DATABASE`, `SQL_USER`, `SQL_PASSWORD`
   (hoặc `SQL_TRUSTED=1` để dùng Windows Authentication).
3. Nếu bảng `measurements` của TV3 đã có sẵn và **tên cột khác** (ví dụ `timestamp` thay cho `measured_at`),
   sửa hằng `SELECT_COLS` và các câu SQL trong `hrdash/queries.py` cho khớp.

### B. SQLite (demo nhanh, không cần SQL Server)

Trong `.env` đặt `DB_BACKEND=sqlite`. Bảng tự được tạo khi chạy công cụ nạp dữ liệu hoặc khi mở dashboard.

## 6. Nạp dữ liệu và chạy dashboard

```bash
# Dữ liệu demo (có mất dữ liệu, đoạn không hợp lệ, HR cao, SpO₂ thấp) + tham chiếu TỔNG HỢP
python -m tools.seed_demo_data --scenario mixed --reset --with-reference

streamlit run app.py          # mở http://localhost:8501
```

Các kịch bản (`python -m tools.seed_demo_data --list`):

| `--scenario` | Mục đích |
|---|---|
| `normal` | Dữ liệu sạch, node ONLINE |
| `stale` | Bản tin cuối cách ≈ 30 s → DỮ LIỆU CŨ |
| `offline` | Bản tin cuối cách ≈ 10 phút → OFFLINE |
| `gap` | Mất dữ liệu liên tục và rớt gói lẻ (nhảy `sequence`) |
| `invalid` | Đoạn không có tín hiệu (NULL) và đoạn chất lượng trung bình |
| `mixed` | Gộp các tình huống trên + cảnh báo HR/SpO₂ |
| `empty` | Xóa hết `measurements` để thử giao diện rỗng |

Khi nhận dữ liệu thật từ TV3, bỏ qua bước seed; dashboard tự đọc bảng `measurements`.

## 7. Các tab của dashboard (Tuần 4)

| Tab | Nội dung | Ngày |
|---|---|---|
| 📡 Trực tiếp | Trạng thái node (online/cũ/offline), HR, **SpO₂ (mô phỏng)**, chất lượng, cảnh báo demo, biểu đồ 5 phút | 25, 26 |
| 📈 Lịch sử | Biểu đồ HR/SpO₂, **tô khoảng không hợp lệ (cam) và mất dữ liệu (đỏ)**, bảng khoảng, bảng dữ liệu có lọc/phân trang, tải CSV | 23 |
| 📚 Dữ liệu tham chiếu | Biểu đồ HR (ECG), PR (PPG), SpO₂ tham chiếu của bản ghi BIDMC | 22 |
| ⚖️ So sánh HR | HR ước lượng và tham chiếu cùng trục, sai số theo thời gian, MAE/RMSE tham khảo | 24 |

## 8. Nạp dữ liệu tham chiếu BIDMC và HR ước lượng

```bash
# (1) Tham chiếu từ PhysioNet BIDMC – file numerics (Time [s], HR, PULSE, RESP, SpO2)
python -m tools.import_bidmc --numerics duong_dan/bidmc_01_Numerics.csv

# (2) HR ước lượng do TV1/TV3 xuất (t_sec, hr_est_bpm, is_valid)
python -m tools.import_bidmc --record bidmc01 --estimates duong_dan/hr_estimates_bidmc01.csv
```

Quy ước cần thống nhất với TV1/TV5:

- `t_sec` = thời điểm **kết thúc cửa sổ** (giây từ đầu bản ghi). Nếu TV1 dùng thời điểm giữa cửa sổ, báo lại để đổi.
- Cửa sổ không hợp lệ: `is_valid = false` và để trống `hr_est_bpm` (nhập vào CSDL là NULL, không phải 0).
- Tên cột kiểu TV1 (`hr`, `is_valid`) cũng được chấp nhận; `hr <= 0` được coi là không hợp lệ.
- Tham chiếu `0` hoặc trống trong numerics → NULL.
- Nên so với **PR (PPG)** trước vì thuật toán dựa trên PPG; HR từ ECG là tham chiếu khác loại.

## 9. Quy ước dữ liệu (JSON → CSDL)

| JSON (bản tin chuẩn từ Ngày 8) | Cột `measurements` | Ghi chú |
|---|---|---|
| `device_id` | `device_id` | |
| `timestamp` (UTC) | `measured_at` | đồng hồ thiết bị |
| – | `received_at` | đồng hồ server, dùng để xác định online/offline |
| `heart_rate_bpm` | `heart_rate_bpm` | NULL khi không hợp lệ |
| `spo2_percent` | `spo2_percent` | NULL khi không hợp lệ; giá trị **mô phỏng** |
| `signal_quality` | `signal_quality` | good / fair / poor / no_signal |
| `measurement_valid` | `measurement_valid` | BIT |
| `sequence` | `sequence` | duy nhất theo `(device_id, sequence)` |
| (đầu ra TV1) `error_code` | `error_code` | tùy chọn |

Đầu ra thuật toán của TV1 (`hr, spo2, is_valid, error_code`) ánh xạ sang JSON chuẩn: `hr → heart_rate_bpm`,
`spo2 → spo2_percent`, `is_valid → measurement_valid`; giá trị `0.0` khi lỗi phải đổi thành `null`.

## 10. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `Can't open lib 'ODBC Driver 18 for SQL Server'` | Cài ODBC Driver 18 hoặc đổi `SQL_DRIVER` đúng tên driver đã cài |
| `Login failed for user` | Kiểm tra `SQL_USER/SQL_PASSWORD`; bật SQL Server Authentication; hoặc `SQL_TRUSTED=1` |
| Không kết nối được `localhost\SQLEXPRESS` | Đặt `SQL_SERVER=localhost\SQLEXPRESS` hoặc `127.0.0.1,1433` và bật TCP/IP |
| Lỗi chứng chỉ SSL | Cấu hình đã có `TrustServerCertificate=yes` cho môi trường học tập |
| Dashboard báo "Chưa có dữ liệu" | Chạy `tools.seed_demo_data` hoặc kiểm tra TV3 đã ghi vào `measurements` |
| Trạng thái luôn "OFFLINE" khi vừa nhận dữ liệu | Kiểm tra đồng hồ máy chủ; trạng thái dùng `received_at` (UTC, server) |
| Giờ hiển thị lệch | Đổi `DISPLAY_TZ` trong `.env` |
| Trang chậm khi xem 7 ngày | Biểu đồ được giảm mẫu; giới hạn `MAX_ROWS` bản ghi gần nhất |

## 11. Giới hạn đã biết

- SpO₂ là giá trị mô phỏng; chưa có tham chiếu SpO₂ thật để hiệu chuẩn nên không công bố độ chính xác.
- MAE/RMSE trên dashboard chỉ để tham khảo; số liệu đánh giá chính thức do TV5 công bố.
- Đã soạn checklist kiểm tra giao diện (`docs/D26_Checklist_kiem_tra_giao_dien.md`) nhưng **chưa thực thi**;
  cần chạy và điền kết quả trước khi nghiệm thu.
- Ngưỡng cảnh báo là ngưỡng demo, không phải ngưỡng lâm sàng.
