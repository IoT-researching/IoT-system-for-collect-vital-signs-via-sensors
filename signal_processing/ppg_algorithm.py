import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
import matplotlib.pyplot as plt
import json
import math
import time

# ==========================================
# TẠO DỮ LIỆU MẪU
# ==========================================
def generate_ppg_sample(target_hr, fs=100, duration=4, noise_level=0.0, no_finger=False):
    """
    Tạo dữ liệu giả lập RED và IR cho 400 mẫu (fs=100Hz, duration=4s)
    """
    n_samples = fs * duration
    t = np.arange(n_samples) / fs
    
    if no_finger:
        # Trường hợp không có ngón tay: giá trị thấp và chỉ có nhiễu nền
        ir_signal = np.random.normal(5000, 100, n_samples)
        red_signal = np.random.normal(4500, 100, n_samples)
        return red_signal.astype(np.uint32), ir_signal.astype(np.uint32)

    freq_hr = target_hr / 60.0  # Đổi bpm sang Hz
    
    # Thành phần DC (nền tĩnh) và AC (dao động mạch máu)
    dc_ir, ac_ir = 100000, 1500
    dc_red, ac_red = 95000, 600  # Tỷ số R ~ 0.421 -> SpO2 chuẩn ~ 99.5%
    
    # Tạo sóng PPG cơ bản (kết hợp sóng sin chính + sóng hài bậc 2 tạo dáng sóng mạch)
    pulse_wave = np.sin(2 * np.pi * freq_hr * t) + 0.3 * np.sin(4 * np.pi * freq_hr * t)
    
    ir_signal = dc_ir + ac_ir * pulse_wave
    red_signal = dc_red + ac_red * pulse_wave
    
    # Thêm nhiễu nếu cần test kịch bản Noisy (nhiễu trắng + trôi đường nền 0.15Hz)
    if noise_level > 0:
        baseline_wander = 800 * np.sin(2 * np.pi * 0.15 * t)
        ir_signal += baseline_wander + np.random.normal(0, noise_level, n_samples)
        red_signal += baseline_wander + np.random.normal(0, noise_level, n_samples)
        
    return red_signal.astype(np.uint32), ir_signal.astype(np.uint32)

# ==========================================
# TIỀN KIỂM & ĐÓNG GÓI JSON 
# ========================================
def validate_output(result):
    """
    Kiểm tra an toàn kết quả HR/SpO2 trước khi đóng gói gửi qua mạng.
    Chặn NaN, Inf, sai kiểu dữ liệu hoặc vượt ngưỡng sinh lý.
    """
    if not isinstance(result, dict):
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2}

    hr = result.get("hr", 0.0)
    spo2 = result.get("spo2", 0.0)
    is_valid = bool(result.get("is_valid", False))
    error_code = int(result.get("error_code", 2))

    if not (math.isfinite(hr) and math.isfinite(spo2)):
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2}

    if is_valid:
        if not (40.0 <= hr <= 200.0) or not (70.0 <= spo2 <= 100.0):
            return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2}

    return {
        "hr": round(float(hr), 1),
        "spo2": round(float(spo2), 1),
        "is_valid": is_valid,
        "error_code": error_code
    }
# ==========================================
#Trả về JSON phù hợp
# ==========================================
def process_ppg_json(red_buffer, ir_buffer, fs=100):
    raw_result = process_ppg(red_buffer, ir_buffer, fs)
    clean_output = validate_output(raw_result)
    return json.dumps(clean_output)
                      
# ==========================================
#LÕI THUẬT TOÁN XỬ LÝ
# ==========================================
def bandpass_filter(signal, lowcut=0.5, highcut=4.0, fs=100, order=2):
    """
    Bộ lọc thông dải Butterworth (0.5Hz - 4.0Hz tương ứng 30 - 240 bpm)
    Giúp loại bỏ trôi đường nền (DC/thở) và nhiễu tần số cao.
    """
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, signal)

def process_ppg(red_buffer, ir_buffer, fs=100):
    """
    Hàm chính giao tiếp với Backend (TV3) & Dashboard (TV4)
    Input: red_buffer, ir_buffer (list hoặc numpy array độ dài 400)
    Output: dict {"hr": float, "spo2": float, "is_valid": bool, "error_code": int}
    """
    red = np.array(red_buffer, dtype=np.float64)
    ir = np.array(ir_buffer, dtype=np.float64)

    # nếu mất mạng giữa chừng thì hàm trả về err =2
    if len(red) < 2 * fs or len(ir) < 2 * fs or len(red) != len(ir):
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2}
    
    # 1. Kiểm tra điều kiện có ngón tay (DC_IR phải đủ lớn)
    dc_ir = np.mean(ir)
    dc_red = np.mean(red)
    
    if dc_ir < 50000 or dc_red < 50000:
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 1} # NO_FINGER

    # 2. Lọc nhiễu & Khử DC để lấy thành phần AC
    ac_ir_filtered = bandpass_filter(ir, lowcut=0.5, highcut=4.0, fs=fs)
    ac_red_filtered = bandpass_filter(red, lowcut=0.5, highcut=4.0, fs=fs)

    # nếu nhiễu gấp > 3 lần biên độ sóng mạch -> báo lỗi nhiễu
    high_freq_noise = np.std((ir - dc_ir) - ac_ir_filtered)
    if high_freq_noise > 1.5 * np.std(ac_ir_filtered):
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2}

    # 3. Phát hiện đỉnh (Peak Detection) trên kênh IR để tính HR
    # distance=30 mẫu (0.3s) -> chặn nhịp tim tối đa 200 bpm, tránh bắt nhầm đỉnh phụ
    # prominence -> độ nhô tối thiểu của đỉnh để tránh bắt nhầm nhiễu nhỏ
    min_prominence = 0.3 * np.std(ac_ir_filtered)
    peaks, _ = find_peaks(ac_ir_filtered, distance=int(0.3 * fs), prominence=min_prominence)

    # Cần ít nhất 2 đỉnh (tương đương >= 30 bpm trong 4 giây) để tính khoảng cách
    if len(peaks) < 2:
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2} # NOISY_SIGNAL

    # Tính khoảng cách trung bình giữa các đỉnh (RR intervals)
    peak_intervals = np.diff(peaks) / fs  # Đổi sang giây
    
    # Kiểm tra độ ổn định của nhịp (nếu các đỉnh cách nhau quá lộn xộn -> do nhiễu rung tay)
    if np.std(peak_intervals) > 0.25:
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2} # NOISY_SIGNAL

    avg_interval = np.mean(peak_intervals)
    hr = 60.0 / avg_interval

    # Kiểm tra ngưỡng sinh lý hợp lệ của HR
    if hr < 40.0 or hr > 200.0:
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2}

    # 4. Tính toán SpO2 qua giá trị hiệu dụng (RMS) của thành phần AC
    rms_ac_ir = np.sqrt(np.mean(ac_ir_filtered ** 2))
    rms_ac_red = np.sqrt(np.mean(ac_red_filtered ** 2))

    # Tỷ số hấp thụ R
    R = (rms_ac_red / dc_red) / (rms_ac_ir / dc_ir)

    # Công thức hiệu chuẩn chuẩn (Maxim / RF approximation)
    # Có thể dùng công thức bậc 2 của RF: -45.060*R*R + 30.354*R + 94.845
    spo2 = -45.060 * (R ** 2) + 30.354 * R + 94.845

    # Giới hạn giá trị SpO2 hợp lệ
    if spo2 < 70.0 or spo2 > 105.0:
        return {"hr": 0.0, "spo2": 0.0, "is_valid": False, "error_code": 2}
    
    spo2 = min(spo2, 100.0) # Chặn trần 100%

    return {
        "hr": round(float(hr), 1),
        "spo2": round(float(spo2), 1),
        "is_valid": True,
        "error_code": 0,
        "debug_peaks": peaks,                 # Dùng để vẽ biểu đồ kiểm tra
        "debug_filtered_ir": ac_ir_filtered   # Dùng để vẽ biểu đồ kiểm tra
    }


# ==========================================
# CHẠY THỬ NGHIỆM & VẼ BIỂU ĐỒ
# ==========================================
if __name__ == "__main__":
    test_cases = [
        ("Clean 60 bpm",  60, 0, False),
        ("Clean 75 bpm",  75, 0, False),
        ("Clean 90 bpm",  90, 0, False),
        ("Noisy 75 bpm",  75, 250, False),
        ("No Finger",     75, 0, True),
        ("Heavy Noise",   75, 4000, False),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(10, 8))
    plot_idx = 0

    sample_inputs = []
    sample_outputs = []

    for name, target_hr, noise, no_finger in test_cases:
        red, ir = generate_ppg_sample(target_hr, fs=100, duration=4, noise_level=noise, no_finger=no_finger)
        raw_result = process_ppg(red, ir, fs=100)
        res = validate_output(raw_result)

        print(f"[{name:14s}] -> HR: {res['hr']:5.1f} bpm | SpO2: {res['spo2']:5.1f}% | Valid: {res['is_valid']} (Err: {res['error_code']})")

        if name in ["Clean 60 bpm", "Clean 75 bpm", "Noisy 75 bpm"] and raw_result.get("is_valid"):
            ax = axes[plot_idx]
            filtered = raw_result["debug_filtered_ir"]
            peaks = raw_result["debug_peaks"]

            ax.plot(filtered, label="Tín hiệu IR sau lọc (AC)", color="blue")
            ax.plot(peaks, filtered[peaks], "rx", markersize=10, label=f"Đỉnh phát hiện ({len(peaks)} đỉnh)")
            ax.set_title(f"{name} -> Kết quả đo: HR = {res['hr']} bpm, SpO2 = {res['spo2']}%")
            ax.legend(loc="upper right")
            ax.grid(True, alpha=0.3)
            plot_idx += 1

        sample_inputs.append({
            "case": name,
            "fs": 100,
            "red": [int(x) for x in red],
            "ir": [int(x) for x in ir]
        })

        sample_outputs.append({
            "case": name,
            "hr": res["hr"],
            "spo2": res["spo2"],
            "is_valid": res["is_valid"],
            "error_code": res["error_code"]
        })

    with open("sample_input.json", "w", encoding="utf-8") as f:
        json.dump(sample_inputs, f, indent=2)

    with open("sample_output.json", "w", encoding="utf-8") as f:
        json.dump(sample_outputs, f, indent=2, ensure_ascii=False)

    base_ts = int(time.time())
    hr_profile = [72, 74, 75, 77, 79, 80, 78, 76, 74, 73, 72, 73, 75, 76, 74]
    timeseries_outputs = []

    for seq, target_hr in enumerate(hr_profile, start=1):
        red, ir = generate_ppg_sample(target_hr, fs=100, duration=4, noise_level=100)
        res = validate_output(process_ppg(red, ir, fs=100))
        timeseries_outputs.append({
            "device_id": "esp32_01",
            "sequence": seq,
            "timestamp": base_ts + (seq - 1) * 4,
            "hr": res["hr"],
            "spo2": res["spo2"],
            "is_valid": res["is_valid"],
            "error_code": res["error_code"]
        })

    with open("timeseries_sample.json", "w", encoding="utf-8") as f:
        json.dump(timeseries_outputs, f, indent=2, ensure_ascii=False)

    print("Đã xuất thành công 3 file JSON!")
    plt.tight_layout()
    plt.show()