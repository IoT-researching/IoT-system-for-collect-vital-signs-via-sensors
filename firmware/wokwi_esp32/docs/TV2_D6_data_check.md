# TV2 - D6: Kiểm tra hai kênh RED/IR và dữ liệu lỗi

## Phạm vi
Kiểm tra 5 file JSON do TV2 tạo trong `firmware/wokwi_esp32/`.
Chỉ đọc dữ liệu, không sửa file nguồn.

## Kết quả kiểm tra
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

## Giới hạn
Đây là kiểm tra dữ liệu cơ bản (số mẫu, giá trị số, khoảng giá trị và độ biến thiên).
Chưa xác nhận thuật toán PPG của TV1 có đọc và xử lý đúng cả 5 trường hợp.

## Việc tiếp theo
TV1 kiểm tra khả năng đọc JSON và xử lý các mẫu RED/IR; nhóm ghi nhận kết quả ở bước kiểm thử mô phỏng D7.