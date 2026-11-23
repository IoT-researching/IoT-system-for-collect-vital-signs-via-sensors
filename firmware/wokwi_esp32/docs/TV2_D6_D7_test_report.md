# TV2 – Báo cáo D6–D7: Kiểm tra dữ liệu và chạy mô phỏng tín hiệu

## D6 – Kiểm tra hai kênh RED/IR và dữ liệu lỗi

### Phạm vi

Kiểm tra 5 file JSON do TV2 tạo trong `firmware/wokwi_esp32/`.

Chỉ đọc dữ liệu, không sửa file nguồn.

### Kết quả kiểm tra

Tất cả 5 file đều đọc được. Mỗi file có `fs = 100`, 400 mẫu RED và 400 mẫu IR.

| File | RED min–max | RED số giá trị khác nhau | IR min–max | IR số giá trị khác nhau |
|---|---:|---:|---:|---:|
| Clean 60 bpm | 94318–95681 | 95 | 98296–101703 | 99 |
| Clean 75 bpm | 94318–95681 | 79 | 98295–101704 | 79 |
| Clean 90 bpm | 94318–95681 | 189 | 98295–101704 | 200 |
| No Finger | 4400–4600 | 174 | 4900–5100 | 173 |
| Noisy 75 bpm | 94111–95913 | 348 | 98054–101864 | 377 |

- Không phát hiện giá trị không phải số hoặc giá trị không hữu hạn trong hai kênh.
- Các kênh đều có nhiều giá trị khác nhau, không bị đứng yên.
- Mẫu No Finger có mức RED/IR thấp hơn rõ rệt so với các mẫu có ngón tay.
- Mẫu Noisy 75 bpm có khoảng dao động rộng hơn mẫu Clean 75 bpm.

### Giới hạn

Đây là kiểm tra dữ liệu cơ bản (số mẫu, giá trị số, khoảng giá trị và độ biến thiên). Chưa xác nhận thuật toán PPG của TV1 có đọc và xử lý đúng cả 5 trường hợp.

### Việc tiếp theo

TV1 kiểm tra khả năng đọc JSON và xử lý các mẫu RED/IR; nhóm ghi nhận kết quả ở bước kiểm thử mô phỏng D7.

---

## D7 – Chạy mô phỏng các trường hợp tín hiệu

### Phạm vi

Chạy mô phỏng ESP32/Wokwi và kiểm tra đầu ra Serial Monitor cho 5 trường hợp:

1. Clean 60 bpm
2. Clean 75 bpm
3. Clean 90 bpm
4. Noisy 75 bpm
5. No Finger

Sau đó, TV1 dùng các file JSON của TV2 làm đầu vào cho hàm `process_ppg()` và gửi lại kết quả HR/SpO₂, trạng thái hợp lệ và mã lỗi.

### Kết quả mô phỏng của TV2

Cả 5 trường hợp đã được chạy trên Serial Monitor. Các lần chạy xuất gói dữ liệu RED/IR với dấu `JSON_BEGIN` và `JSON_END`.

Mỗi gói có trường `case`, `fs`, `red` và `ir`. Dữ liệu có `fs = 100` và 400 mẫu cho mỗi kênh.

### Kết quả xử lý của TV1

Theo ảnh kết quả TV1 gửi, cả 5 file đều hiển thị `Đọc OK` và có đầu ra như sau:

| File | HR đầu ra | SpO₂ đầu ra | `Valid` | `Err` |
|---|---:|---:|---|---:|
| `ppg_tv2_clean_75bpm.json` | 74.8 bpm | 99.6% | True | 0 |
| `ppg_tv2_clean_60bpm.json` | 59.6 bpm | 99.6% | True | 0 |
| `ppg_tv2_clean_90bpm.json` | 89.8 bpm | 99.6% | True | 0 |
| `ppg_tv2_noisy_75bpm.json` | 75.0 bpm | 99.6% | True | 0 |
| `ppg_tv2_no_finger.json` | 0.0 bpm | 0.0% | False | 1 |

### Nhận xét

- Cả 5 file JSON đều được đọc và xử lý, không có lỗi đọc file được thể hiện trong kết quả TV1 gửi.
- Với các mẫu Clean 60/75/90 bpm, HR đầu ra gần với giá trị mục tiêu của từng mẫu.
- Với mẫu Noisy 75 bpm, thuật toán vẫn trả HR 75.0 bpm và `Valid = True` trong lần chạy này.
- Với mẫu No Finger, thuật toán trả `Valid = False`, `Err = 1`. Đây là kết quả nhận diện không có ngón tay theo mã lỗi của thuật toán TV1, không phải lỗi đọc JSON.
- SpO₂ đầu ra của 4 mẫu có tín hiệu là 99.6%; mẫu No Finger trả 0.0%.

### Kết luận D7

TV2 đã chạy mô phỏng và xuất dữ liệu cho cả 5 trường hợp qua Serial Monitor. Kết quả kiểm thử phối hợp do TV1 thực hiện cho thấy các file JSON được đọc và xử lý trong lần chạy được báo cáo; No Finger được đánh dấu không hợp lệ với mã lỗi 1.

## Giới hạn chung

- Các mẫu là tín hiệu mô phỏng, không phải dữ liệu đo trên người thật.
- Kết quả HR/SpO₂ phản ánh lần chạy các file và cấu hình được báo cáo; không chứng minh độ chính xác trên thiết bị hoặc người thật.
- Báo cáo này ghi nhận việc tạo, kiểm tra và chạy thử dữ liệu mô phỏng của TV2. Không xem đây là xác nhận hoàn tất tích hợp phần cứng cảm biến MAX30102 hoặc giao thức backend.