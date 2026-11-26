# Ngày 26 – Checklist kiểm tra dữ liệu cũ, mất dữ liệu, lỗi giao diện (TV4)

> **Trạng thái: CHƯA THỰC THI.** Bảng dưới là kịch bản kiểm tra kèm kết quả mong đợi. Người thực hiện chạy từng
> dòng, điền cột *Kết quả* (Đạt / Không đạt), chụp ảnh minh chứng và gửi TV5 để tổng hợp.

Chuẩn bị: `DB_BACKEND=sqlite` (hoặc SQL Server), `streamlit run app.py`, mở tab tương ứng.
Ngưỡng mặc định: online ≤ 10 s, dữ liệu cũ ≤ 60 s, offline > 60 s; mất dữ liệu khi khoảng cách > 5 s hoặc nhảy `sequence`.

## A. Dữ liệu cũ / node offline

| # | Lệnh chuẩn bị | Thao tác | Kết quả mong đợi | Kết quả |
|---|---|---|---|---|
| A1 | `python -m tools.seed_demo_data --scenario normal --reset` | Mở tab Trực tiếp | 🟢 ONLINE; HR và SpO₂ (mô phỏng) hiển thị số; "Không có cảnh báo" | |
| A2 | `--scenario stale --reset` | Mở tab Trực tiếp | 🟡 DỮ LIỆU CŨ; nhãn KPI có "· dữ liệu cũ"; có cảnh báo vàng | |
| A3 | `--scenario offline --reset` | Mở tab Trực tiếp | 🔴 OFFLINE; cảnh báo đỏ; biểu đồ 5 phút báo mất dữ liệu (vùng đỏ toàn khoảng) | |
| A4 | `--scenario normal --reset` rồi chờ > 60 s không nạp thêm | Giữ tab Trực tiếp bật tự làm mới | Trạng thái chuyển ONLINE → DỮ LIỆU CŨ → OFFLINE mà không cần bấm tải lại | |
| A5 | – | Đổi đồng hồ máy chủ lệch vài giây (nếu có thể) | Tuổi bản tin không âm; không lỗi | |

## B. Mất dữ liệu và không hợp lệ

| # | Lệnh chuẩn bị | Thao tác | Kết quả mong đợi | Kết quả |
|---|---|---|---|---|
| B1 | `--scenario gap --reset` | Tab Lịch sử, 1 giờ | Vùng đỏ ở khoảng mất liên tục + các vùng đỏ nhỏ ở rớt gói lẻ; bảng khoảng có loại "Mất dữ liệu" và số bản tin thiếu > 0 | |
| B2 | `--scenario invalid --reset` | Tab Lịch sử, 1 giờ | Vùng cam; đường HR/SpO₂ **ngắt**, không có điểm 0; bảng khoảng có loại "Không hợp lệ" | |
| B3 | `--scenario mixed --reset` | Tab Lịch sử | Cả vùng cam và đỏ; "Tỷ lệ hợp lệ" < 100 %; có thể tải CSV khoảng | |
| B4 | như B3 | Tích "Chỉ số đo hợp lệ" ở bảng | Bảng không còn dòng ✘; biểu đồ không đổi (bộ lọc chỉ áp cho bảng) | |
| B5 | như B3 | Chọn "7 ngày" | Có vùng đỏ đầu cửa sổ (chưa có dữ liệu); trang vẫn mở nhanh | |
| B6 | như B3 | Đổi trang, đổi số dòng/trang | Không lỗi; số trang đúng | |

## C. Cảnh báo demo và nhãn SpO₂ mô phỏng

| # | Thao tác | Kết quả mong đợi | Kết quả |
|---|---|---|---|
| C1 | Tab Trực tiếp khi HR > 120 (kịch bản `mixed`, đoạn 85–90 %) | Cảnh báo "HR cao … cảnh báo demo" | |
| C2 | Cùng thời điểm, SpO₂ < 94 % | Cảnh báo SpO₂ **(mô phỏng)** thấp | |
| C3 | Quan sát toàn bộ giao diện | Mọi chỗ hiện SpO₂ (KPI, biểu đồ, bảng, cảnh báo) đều ghi "mô phỏng"; banner đầu trang có lưu ý | |
| C4 | Đặt `SPO2_SIMULATED=0` rồi chạy lại | Nhãn "(mô phỏng)" biến mất, vẫn còn dòng "Chưa hiệu chuẩn y tế" | |

## D. Lỗi giao diện và hệ thống

| # | Chuẩn bị | Kết quả mong đợi | Kết quả |
|---|---|---|---|
| D1 | `--scenario empty` | Tab Trực tiếp/Lịch sử báo chưa có dữ liệu, không có traceback | |
| D2 | Tắt SQL Server (hoặc sai mật khẩu trong `.env`) | Thông báo lỗi kết nối thân thiện + nút "Thử kết nối lại"; không crash | |
| D3 | Bật lại SQL Server, bấm "Thử kết nối lại" | Dashboard hoạt động bình thường | |
| D4 | Tab Tham chiếu khi chưa nạp bản ghi | Hướng dẫn lệnh nạp dữ liệu, không lỗi | |
| D5 | `--with-reference`, tab So sánh HR | Biểu đồ ước lượng vs tham chiếu; cửa sổ nhiễu tô cam; có banner "DỮ LIỆU TỔNG HỢP" | |
| D6 | Nạp CSV ước lượng có `hr = 0` ở cửa sổ lỗi | Cửa sổ đó thành NULL, bị loại khỏi MAE/RMSE | |
| D7 | Bật/tắt tự làm mới, đổi chu kỳ 2–30 s | Panel trực tiếp cập nhật đúng chu kỳ, không làm mất lựa chọn ở tab khác | |
| D8 | Thu nhỏ cửa sổ trình duyệt | Bố cục không vỡ, biểu đồ co giãn | |

## E. Ghi nhận lỗi phát hiện

| Mã | Mô tả lỗi | Mức độ | Người xử lý | Trạng thái |
|---|---|---|---|---|
| | | | | |
