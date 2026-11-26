"""Cấu hình trung tâm cho Dashboard TV4 (đọc từ biến môi trường hoặc file .env)."""
import os
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv là tùy chọn
    pass


def _s(name, default):
    return os.getenv(name, default)


def _f(name, default):
    return float(os.getenv(name, default))


# ---------------------------------------------------------------- CSDL
DB_BACKEND = _s("DB_BACKEND", "mssql").lower()  # mssql | sqlite (sqlite chỉ để demo nhanh)
SQLITE_PATH = _s("SQLITE_PATH", "data/demo.db")


def build_db_url() -> str:
    explicit = _s("DB_URL", "")
    if explicit:
        return explicit
    if DB_BACKEND == "sqlite":
        return f"sqlite:///{SQLITE_PATH}"
    driver = _s("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    server = _s("SQL_SERVER", "localhost")
    database = _s("SQL_DATABASE", "HRSpO2Db")
    if _s("SQL_TRUSTED", "0") == "1":
        auth = "Trusted_Connection=yes;"
    else:
        auth = f"UID={_s('SQL_USER', 'sa')};PWD={_s('SQL_PASSWORD', '')};"
    odbc = (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};{auth}"
        "TrustServerCertificate=yes;Connection Timeout=5;"
    )
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


def is_sqlite() -> bool:
    return build_db_url().startswith("sqlite")


# ---------------------------------------------------------------- Hiển thị
DISPLAY_TZ = _s("DISPLAY_TZ", "Asia/Ho_Chi_Minh")
MAX_ROWS = int(_f("MAX_ROWS", 100000))  # số bản ghi tối đa đọc cho một lần xem lịch sử
MAX_PLOT_POINTS = 5000  # giảm mẫu khi vẽ (khoảng mất/không hợp lệ vẫn tính trên dữ liệu đầy đủ)
MAX_SHADES = 150  # số vùng tô màu tối đa trên một biểu đồ

# ---------------------------------------------------------------- Trạng thái node / khoảng mất dữ liệu
EXPECTED_INTERVAL_S = _f("EXPECTED_INTERVAL_S", 2)  # chu kỳ gửi bản tin dự kiến của ESP32
GAP_FACTOR = _f("GAP_FACTOR", 2.5)  # khoảng cách > GAP_FACTOR x chu kỳ => coi là mất dữ liệu
ONLINE_MAX_AGE_S = _f("ONLINE_MAX_AGE_S", 10)  # <= 10 s kể từ bản tin cuối: online
STALE_MAX_AGE_S = _f("STALE_MAX_AGE_S", 60)  # <= 60 s: dữ liệu cũ; lớn hơn: offline

# ---------------------------------------------------------------- Ngưỡng cảnh báo DEMO (không phải ngưỡng chẩn đoán)
HR_LOW = _f("ALERT_HR_LOW", 50)
HR_HIGH = _f("ALERT_HR_HIGH", 120)
SPO2_WARN = _f("ALERT_SPO2_WARN", 94)
SPO2_CRIT = _f("ALERT_SPO2_CRIT", 90)

# ---------------------------------------------------------------- Nhãn SpO2 mô phỏng (Ngày 25)
SPO2_SIMULATED = _s("SPO2_SIMULATED", "1") == "1"
SPO2_LABEL = "SpO₂ (mô phỏng)" if SPO2_SIMULATED else "SpO₂"
SPO2_BADGE = "⚠️ Giá trị MÔ PHỎNG – chỉ minh họa pipeline" if SPO2_SIMULATED else "Chưa hiệu chuẩn y tế"
SPO2_NOTE = (
    "SpO₂ trên dashboard được tính từ nguồn RED/IR **mô phỏng bằng phần mềm** (công thức hồi quy bậc 2 "
    "mượn từ MAX30102_by_RF). Giá trị này chỉ dùng để minh họa pipeline, **chưa được hiệu chuẩn** "
    "và không có độ chính xác y tế."
)
DISCLAIMER = (
    "Nguyên mẫu nghiên cứu – không phải thiết bị y tế. Các cảnh báo là cảnh báo demo, "
    "không dùng để chẩn đoán hay quyết định điều trị."
)
