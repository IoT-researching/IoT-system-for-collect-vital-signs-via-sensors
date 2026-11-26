"""Nạp dữ liệu tham chiếu BIDMC (numerics) và kết quả ước lượng HR vào CSDL (Ngày 22 và Ngày 24).

1) Nạp tham chiếu từ file numerics của PhysioNet (cột: Time [s], HR, PULSE, RESP, SpO2):
    python -m tools.import_bidmc --numerics data/bidmc_01_Numerics.csv

2) Nạp kết quả ước lượng HR do TV1/TV3 xuất (cột: t_sec, hr_est_bpm, is_valid; có thể có record_id):
    python -m tools.import_bidmc --record bidmc01 --estimates data/hr_estimates_bidmc01.csv

Quy ước t_sec của file ước lượng: thời điểm KẾT THÚC cửa sổ, tính bằng giây từ đầu bản ghi (cần thống nhất
với TV1 và TV5). Tên cột kiểu TV1 (hr, is_valid) cũng được chấp nhận; hr <= 0 hoặc is_valid = false -> NULL.
"""
import argparse
import math
import re
import sys
from pathlib import Path

import pandas as pd

from hrdash import db


def _f(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _to_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes", "y")
    try:
        return bool(value) and not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def read_numerics(path: Path, record_id: str):
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    low = {c.lower(): c for c in df.columns}
    tcol = next((c for k, c in low.items() if k.startswith("time")), None)
    if tcol is None:
        sys.exit("Không tìm thấy cột thời gian (Time [s]) trong file numerics.")
    hrcol, prcol, spcol = low.get("hr"), low.get("pulse"), low.get("spo2")
    if not (hrcol or prcol or spcol):
        sys.exit("File numerics không có cột HR / PULSE / SpO2.")
    rows = []
    for _, r in df.iterrows():
        t = _f(r[tcol])
        if t is None:
            continue

        def val(col):
            v = _f(r[col]) if col else None
            return None if v is None or v <= 0 else v  # 0 hoặc âm là không có số liệu, dùng NULL

        rows.append(dict(record_id=record_id, t_sec=t, hr_ecg_ref_bpm=val(hrcol),
                         pr_ppg_ref_bpm=val(prcol), spo2_ref_percent=val(spcol)))
    return rows


def read_estimates(path: Path, record_id: str):
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "record_id" in df.columns:
        df = df[df["record_id"].astype(str) == record_id]
    tcol = "t_sec" if "t_sec" in df.columns else None
    hcol = "hr_est_bpm" if "hr_est_bpm" in df.columns else ("hr" if "hr" in df.columns else None)
    if tcol is None or hcol is None:
        sys.exit("File ước lượng cần cột t_sec và hr_est_bpm (hoặc hr).")
    vcol = next((c for c in ("is_valid", "measurement_valid") if c in df.columns), None)
    rows = []
    for _, r in df.iterrows():
        t, hr = _f(r[tcol]), _f(r[hcol])
        if t is None:
            continue
        if hr is not None and hr <= 0:
            hr = None
        ok = _to_bool(r[vcol]) if vcol else hr is not None
        if not ok:
            hr = None
        rows.append(dict(record_id=record_id, t_sec=t, hr_est_bpm=hr, is_valid=bool(ok and hr is not None)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--numerics", type=Path, help="file bidmc_XX_Numerics.csv")
    ap.add_argument("--estimates", type=Path, help="file CSV kết quả ước lượng HR")
    ap.add_argument("--record", help="mã bản ghi, ví dụ bidmc01 (mặc định lấy từ tên file numerics)")
    ap.add_argument("--source", default="BIDMC")
    args = ap.parse_args()
    if not args.numerics and not args.estimates:
        ap.error("Cần ít nhất --numerics hoặc --estimates.")

    record = args.record
    if not record and args.numerics:
        m = re.search(r"bidmc[_-]?(\d+)", args.numerics.name, re.I)
        record = f"bidmc{m.group(1)}" if m else args.numerics.stem
    if not record:
        ap.error("Cần --record khi chỉ nạp --estimates.")

    signals = read_numerics(args.numerics, record) if args.numerics else None
    estimates = read_estimates(args.estimates, record) if args.estimates else None
    duration = int(max(r["t_sec"] for r in signals)) if signals else None

    engine = db.get_engine()
    db.init_schema(engine)
    with engine.begin() as conn:
        db.save_reference(conn, record, source=args.source, duration_s=duration,
                          notes="Nạp từ PhysioNet BIDMC (numerics). HR từ ECG, PULSE từ PPG." if signals else None,
                          signals=signals, estimates=estimates)
    if signals is not None:
        print(f"Đã nạp {len(signals)} mẫu tham chiếu cho '{record}'.")
    if estimates is not None:
        print(f"Đã nạp {len(estimates)} kết quả ước lượng HR cho '{record}'.")


if __name__ == "__main__":
    main()
