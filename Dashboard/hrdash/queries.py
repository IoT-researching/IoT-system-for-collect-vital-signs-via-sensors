"""Truy vấn CSDL cho dashboard. Câu SQL dùng cú pháp chung để chạy được trên SQL Server (chính) và SQLite (demo).

Tên cột theo bảng measurements: measured_at (JSON "timestamp"), received_at, heart_rate_bpm, spo2_percent,
signal_quality, measurement_valid, sequence. Nếu bảng của nhóm dùng tên khác, chỉnh tại SELECT_COLS.
"""
import pandas as pd
from sqlalchemy import DateTime, bindparam, text

from . import config

SELECT_COLS = ("device_id, measured_at, received_at, heart_rate_bpm, spo2_percent, "
               "signal_quality, measurement_valid, sequence")


def _read(engine, stmt, **params) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(stmt, conn, params=params)


def _to_local(series) -> pd.Series:
    s = pd.to_datetime(series)
    return s.dt.tz_localize("UTC").dt.tz_convert(config.DISPLAY_TZ).dt.tz_localize(None)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa kiểu dữ liệu giữa các hệ CSDL và thêm cột ts (giờ hiển thị, không múi giờ)."""
    if df.empty:
        df = df.copy()
        df["ts"] = pd.Series(dtype="datetime64[ns]")
        return df
    df = df.copy()
    df["measured_at"] = pd.to_datetime(df["measured_at"])
    df["received_at"] = pd.to_datetime(df["received_at"])
    df["measurement_valid"] = df["measurement_valid"].astype(bool)
    for c in ("heart_rate_bpm", "spo2_percent"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ts"] = _to_local(df["measured_at"])
    return df


def _row_to_dict(df: pd.DataFrame):
    if df.empty:
        return None
    row = _normalize(df).sort_values(["measured_at", "sequence"]).iloc[-1]
    return {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}


def ping(engine):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def list_devices(engine) -> list:
    df = _read(engine, text("SELECT DISTINCT device_id FROM measurements ORDER BY device_id"))
    return df["device_id"].tolist()


def last_seen(engine, device_id):
    """Thời điểm server nhận bản tin cuối (UTC). Dự phòng: measured_at nếu received_at rỗng."""
    df = _read(engine, text("SELECT MAX(received_at) AS r, MAX(measured_at) AS m "
                            "FROM measurements WHERE device_id = :d"), d=device_id)
    if df.empty:
        return None
    r, m = df.iloc[0]["r"], df.iloc[0]["m"]
    val = r if pd.notna(r) else m
    return None if pd.isna(val) else pd.to_datetime(val)


def latest_measurement(engine, device_id):
    sql = text(f"SELECT {SELECT_COLS} FROM measurements WHERE device_id = :d AND measured_at = "
               "(SELECT MAX(measured_at) FROM measurements WHERE device_id = :d)")
    return _row_to_dict(_read(engine, sql, d=device_id))


def latest_valid_measurement(engine, device_id):
    sql = text(f"SELECT {SELECT_COLS} FROM measurements WHERE device_id = :d AND measurement_valid = 1 "
               "AND measured_at = (SELECT MAX(measured_at) FROM measurements "
               "WHERE device_id = :d AND measurement_valid = 1)")
    return _row_to_dict(_read(engine, sql, d=device_id))


def history(engine, device_id, since, until) -> pd.DataFrame:
    """Lịch sử trong [since, until] (UTC không múi giờ), sắp xếp tăng dần theo thời gian."""
    stmt = text(f"SELECT {SELECT_COLS} FROM measurements WHERE device_id = :d "
                "AND measured_at >= :since AND measured_at <= :until "
                "ORDER BY measured_at, sequence").bindparams(
        bindparam("since", type_=DateTime), bindparam("until", type_=DateTime))
    df = _normalize(_read(engine, stmt, d=device_id, since=since, until=until))
    return df.tail(config.MAX_ROWS).reset_index(drop=True)


def list_reference_records(engine) -> pd.DataFrame:
    return _read(engine, text("SELECT record_id, source, duration_s, notes FROM reference_records "
                              "ORDER BY record_id"))


def reference_signals(engine, record_id) -> pd.DataFrame:
    return _read(engine, text("SELECT t_sec, hr_ecg_ref_bpm, pr_ppg_ref_bpm, spo2_ref_percent "
                              "FROM reference_signals WHERE record_id = :r ORDER BY t_sec"), r=record_id)


def hr_estimates(engine, record_id) -> pd.DataFrame:
    df = _read(engine, text("SELECT t_sec, hr_est_bpm, is_valid FROM hr_estimates "
                            "WHERE record_id = :r ORDER BY t_sec"), r=record_id)
    if not df.empty:
        df["is_valid"] = df["is_valid"].astype(bool)
    return df
