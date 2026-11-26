# TV5 tuần 1

## Phạm vi bàn giao

TV5 kiểm thử đầu vào RED/IR mô phỏng và hàm xử lý `process_ppg` của TV1. Bộ kiểm thử đọc năm fixture mẫu của TV1 và năm JSON được firmware lưu trong thư mục Wokwi. Đây là kiểm thử phần mềm trên dữ liệu tổng hợp, không phải phép đo trên người hoặc cảm biến MAX30102 thật.

## Bảng ca kiểm thử và kết quả

| ID | Ca kiểm thử | Kết quả mong đợi | Kết quả thực tế | Trạng thái |
|---|---|---|---|---|
| TC01 | Clean 60 bpm | Hợp lệ, HR trong ±2 bpm | 59.6 bpm, hợp lệ, err 0 | PASS |
| TC02 | Clean 75 bpm | Hợp lệ, HR trong ±2 bpm | 74.8 bpm, hợp lệ, err 0 | PASS |
| TC03 | Clean 90 bpm | Hợp lệ, HR trong ±2 bpm | 89.8 bpm, hợp lệ, err 0 | PASS |
| TC04 | Noisy 75 bpm | Theo expected đã lưu; nếu hợp lệ thì HR trong ±3 bpm | 74.5 bpm, hợp lệ, err 0 | PASS |
| TC05 | No Finger | Không hợp lệ, err 1 | HR 0.0, SpO₂ 0.0, invalid, err 1 | PASS |
| TC06 | RED=0 và IR=0 | Không hợp lệ, không crash | Invalid, err 1 | PASS |
| TC07 | Buffer rỗng, ngắn hoặc lệch độ dài | Invalid, không crash | Invalid, không crash | PASS |
| TC08 | Có NaN hoặc sampling rate không hợp lệ | Invalid, không crash | Invalid, không crash | PASS |
| TC09 | Cấu trúc fixture TV1 | 5 ca, fs=100, mỗi kênh 400 mẫu hữu hạn | Đạt | PASS |
| TC10 | JSON firmware Wokwi | 5 file parse được; đúng độ dài và HR/no-finger | Đạt trên 5 file | PASS |

## Kết quả tổng

**8 phương thức kiểm thử tự động đạt.** Ca clean nằm trong sai số HR đặt trước; noisy case vẫn được xử lý; no-finger và các dữ liệu lỗi trả invalid thay vì làm chương trình dừng.

## Cách chạy lại

Mở terminal tại thư mục repository của thành viên Linh:

```powershell
python -m pip install -r tests/requirements-test.txt
python -m unittest discover -s tests -v
```

Kết quả lần chạy đã lưu tại `docs/TV5_WEEK1_TEST_RUN.txt`.

## Sản phẩm bàn giao

- `tests/test_week1_tv5.py` — mã kiểm thử tự động.
- `docs/TV5_WEEK1_TEST_PLAN.md` — kế hoạch và tiêu chí từng ca.
- `docs/TV5_WEEK1_TEST_REPORT.md` — báo cáo kết quả, lỗi đã xử lý và giới hạn.
- `docs/TV5_WEEK1_TEST_RUN.txt` — log thực chạy.
- `signal_processing/ppg_algorithm.py` — thêm kiểm tra đầu vào để buffer sai/thiếu trả invalid; đưa import matplotlib vào phần chạy demo để test không phụ thuộc matplotlib.

## Giới hạn SpO₂

SpO₂ hiện được tính bằng công thức xấp xỉ chưa xác nhận hiệu chuẩn cho cảm biến và dữ liệu này. Vì vậy, giá trị SpO₂ trong fixture chỉ là đầu ra demo, không phải độ chính xác đã kiểm chứng và không dùng cho mục đích y tế. Khi `is_valid=false`, phía hiển thị phải bỏ qua các giá trị sentinel bằng 0.
