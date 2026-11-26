"""Lớp CSDL: định nghĩa bảng (SQLAlchemy Core), kết nối và hàm ghi dùng chung.

Bảng chính thức trên SQL Server nên tạo bằng sql/01_create_schema.sql + sql/03_reference_tables.sql.
Hàm init_schema() chỉ tạo các bảng còn thiếu (an toàn khi chạy lại) và là đường tắt cho chế độ demo SQLite.
"""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index,
    Integer, MetaData, String, Table, UniqueConstraint, and_, create_engine, delete, select, update,
)
from sqlalchemy.dialects.mssql import DATETIME2

from . import config


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


metadata = MetaData()
PK = BigInteger().with_variant(Integer, "sqlite")
TS = DateTime().with_variant(DATETIME2(3), "mssql")

devices = Table(
    "devices", metadata,
    Column("device_id", String(50), primary_key=True),
    Column("display_name", String(100)),
    Column("created_at", TS, nullable=False, default=utcnow_naive),
)

measurements = Table(
    "measurements", metadata,
    Column("id", PK, primary_key=True, autoincrement=True),
    Column("device_id", String(50), ForeignKey("devices.device_id"), nullable=False),
    Column("measured_at", TS, nullable=False),  # JSON "timestamp" (UTC, đồng hồ thiết bị)
    Column("received_at", TS, nullable=False, default=utcnow_naive),  # UTC, đồng hồ server
    Column("heart_rate_bpm", Float),  # NULL khi không hợp lệ (không dùng số 0)
    Column("spo2_percent", Float),  # NULL khi không hợp lệ
    Column("signal_quality", String(20), nullable=False),
    Column("measurement_valid", Boolean, nullable=False),
    Column("sequence", BigInteger, nullable=False),
    Column("error_code", Integer),  # tùy chọn: mã lỗi từ thuật toán TV1 (0 = không lỗi)
    UniqueConstraint("device_id", "sequence", name="UQ_measurements_device_seq"),
    CheckConstraint("heart_rate_bpm IS NULL OR (heart_rate_bpm >= 40 AND heart_rate_bpm <= 200)",
                    name="CK_measurements_hr"),
    CheckConstraint("spo2_percent IS NULL OR (spo2_percent >= 70 AND spo2_percent <= 100)",
                    name="CK_measurements_spo2"),
    CheckConstraint("measurement_valid = 1 OR (heart_rate_bpm IS NULL AND spo2_percent IS NULL)",
                    name="CK_measurements_invalid_null"),
    Index("IX_measurements_device_time", "device_id", "measured_at"),
)

reference_records = Table(
    "reference_records", metadata,
    Column("record_id", String(30), primary_key=True),
    Column("source", String(30), nullable=False),  # BIDMC | SYNTHETIC
    Column("duration_s", Integer),
    Column("notes", String(500)),
    Column("imported_at", TS, nullable=False, default=utcnow_naive),
)

reference_signals = Table(
    "reference_signals", metadata,
    Column("id", PK, primary_key=True, autoincrement=True),
    Column("record_id", String(30), ForeignKey("reference_records.record_id"), nullable=False),
    Column("t_sec", Float, nullable=False),
    Column("hr_ecg_ref_bpm", Float),  # numerics HR (suy ra từ ECG)
    Column("pr_ppg_ref_bpm", Float),  # numerics PULSE (suy ra từ PPG)
    Column("spo2_ref_percent", Float),
    UniqueConstraint("record_id", "t_sec", name="UQ_refsig_record_t"),
)

hr_estimates = Table(
    "hr_estimates", metadata,
    Column("id", PK, primary_key=True, autoincrement=True),
    Column("record_id", String(30), ForeignKey("reference_records.record_id"), nullable=False),
    Column("t_sec", Float, nullable=False),  # thời điểm kết thúc cửa sổ, tính từ đầu bản ghi
    Column("hr_est_bpm", Float),  # NULL khi cửa sổ không hợp lệ
    Column("is_valid", Boolean, nullable=False),
    UniqueConstraint("record_id", "t_sec", name="UQ_hrest_record_t"),
)


def get_engine():
    url = config.build_db_url()
    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url)
    kwargs = {"pool_pre_ping": True}
    if url.startswith("mssql+pyodbc"):
        kwargs["fast_executemany"] = True
    return create_engine(url, **kwargs)


def init_schema(engine) -> None:
    metadata.create_all(engine)  # chỉ tạo bảng còn thiếu


def parse_ts(value) -> datetime:
    """Chuỗi ISO-8601 (có thể kết thúc bằng 'Z') -> datetime UTC không múi giờ."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def ensure_device(conn, device_id: str) -> None:
    row = conn.execute(select(devices.c.device_id).where(devices.c.device_id == device_id)).first()
    if row is None:
        conn.execute(devices.insert().values(device_id=device_id, display_name=device_id))


def insert_measurement(conn, m: dict) -> bool:
    """Ghi một payload JSON chuẩn. Trả về False nếu trùng (device_id, sequence). TV3 có thể dùng lại."""
    ensure_device(conn, m["device_id"])
    dup = conn.execute(
        select(measurements.c.id).where(and_(
            measurements.c.device_id == m["device_id"], measurements.c.sequence == m["sequence"]))
    ).first()
    if dup is not None:
        return False
    valid = bool(m["measurement_valid"])
    conn.execute(measurements.insert().values(
        device_id=m["device_id"],
        measured_at=parse_ts(m["timestamp"]),
        heart_rate_bpm=m.get("heart_rate_bpm") if valid else None,
        spo2_percent=m.get("spo2_percent") if valid else None,
        signal_quality=m.get("signal_quality") or "unknown",
        measurement_valid=valid,
        sequence=int(m["sequence"]),
        error_code=m.get("error_code"),
    ))
    return True


def save_reference(conn, record_id, source=None, duration_s=None, notes=None, signals=None, estimates=None):
    """Tạo/cập nhật bản ghi tham chiếu; thay thế tín hiệu và/hoặc ước lượng nếu được truyền vào."""
    row = conn.execute(select(reference_records.c.record_id)
                       .where(reference_records.c.record_id == record_id)).first()
    if row is None:
        conn.execute(reference_records.insert().values(
            record_id=record_id, source=source or "BIDMC", duration_s=duration_s, notes=notes))
    else:
        values = {k: v for k, v in dict(source=source, duration_s=duration_s, notes=notes).items()
                  if v is not None}
        if values:
            conn.execute(update(reference_records).where(reference_records.c.record_id == record_id)
                         .values(**values))
    if signals is not None:
        conn.execute(delete(reference_signals).where(reference_signals.c.record_id == record_id))
        if signals:
            conn.execute(reference_signals.insert(), signals)
    if estimates is not None:
        conn.execute(delete(hr_estimates).where(hr_estimates.c.record_id == record_id))
        if estimates:
            conn.execute(hr_estimates.insert(), estimates)
