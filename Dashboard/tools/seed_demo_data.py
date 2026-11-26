"""Sinh dữ liệu DEMO để thử dashboard (Ngày 22–26). KHÔNG phải số đo thật.

Ví dụ:
    python -m tools.seed_demo_data --scenario mixed --reset --with-reference
    python -m tools.seed_demo_data --scenario offline --reset
    python -m tools.seed_demo_data --scenario empty            # xóa hết measurements để thử trạng thái rỗng
"""
import argparse
import math
import random
from datetime import timedelta

from sqlalchemy import delete, func, select

from hrdash import db
from hrdash.logic import utcnow_naive

SCENARIOS = {
    "normal": "Dữ liệu sạch, node online (bản tin cuối ≈ bây giờ).",
    "stale": "Bản tin cuối cách ≈ 30 giây -> trạng thái DỮ LIỆU CŨ.",
    "offline": "Bản tin cuối cách ≈ 10 phút -> OFFLINE.",
    "gap": "Mất dữ liệu liên tục (~8% thời lượng) và rớt gói lẻ (nhảy sequence).",
    "invalid": "Đoạn không có tín hiệu (invalid, NULL) và đoạn chất lượng trung bình.",
    "mixed": "Gộp gap + invalid + HR cao + SpO₂ thấp (để thử cảnh báo).",
    "empty": "Xóa toàn bộ measurements (thử giao diện khi chưa có dữ liệu).",
}


def _ms(dt):
    """Làm tròn xuống mili giây (cột DATETIME2(3))."""
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


def build_rows(device, scenario, minutes, interval, start_seq, seed):
    rnd = random.Random(seed)
    end = utcnow_naive()
    if scenario == "stale":
        end -= timedelta(seconds=30)
    elif scenario == "offline":
        end -= timedelta(minutes=10)
    n = max(int(minutes * 60 / interval), 1)
    start = end - timedelta(seconds=(n - 1) * interval)
    rows, seq = [], start_seq
    for i in range(n):
        seq += 1  # bản tin bị rớt vẫn chiếm số sequence
        f = i / n
        t = start + timedelta(seconds=i * interval)
        lost = invalid = False
        quality = "good"
        if scenario in ("gap", "mixed"):
            lost = (0.40 <= f < 0.48) or (i > 0 and i % 97 == 0)
        if scenario in ("invalid", "mixed"):
            if 0.65 <= f < 0.72:
                invalid, quality = True, "no_signal"
            elif 0.10 <= f < 0.15:
                quality = "fair"
        if lost:
            continue
        hr = 74 + 6 * math.sin(2 * math.pi * i * interval / 90) + rnd.gauss(0, 1.2)
        sp = 97.5 + rnd.gauss(0, 0.4)
        if scenario == "mixed" and 0.85 <= f < 0.90:
            hr += 55
            sp = 92.5 + rnd.gauss(0, 0.3)
        hr = round(min(max(hr, 40.0), 200.0), 1)
        sp = round(min(max(sp, 70.0), 100.0), 1)
        rows.append(dict(
            device_id=device, measured_at=_ms(t),
            received_at=_ms(t + timedelta(milliseconds=rnd.randint(50, 400))),
            heart_rate_bpm=None if invalid else hr, spo2_percent=None if invalid else sp,
            signal_quality=quality, measurement_valid=not invalid, sequence=seq, error_code=None))
    return rows


def seed_reference(engine, seed=7):
    """Bản ghi tham chiếu TỔNG HỢP (source=SYNTHETIC) để thử biểu đồ D22/D24. Không phải BIDMC."""
    rnd = random.Random(seed)
    rid, n = "demo_synth_01", 480
    hr_ref, pr_ref, signals = [], [], []
    for t in range(n):
        hr = 72 + 8 * math.sin(2 * math.pi * t / 120) + rnd.gauss(0, 0.5)
        pr = hr + rnd.gauss(0, 0.8)
        missing = 300 <= t < 312  # mô phỏng tham chiếu bị thiếu
        hr_ref.append(hr)
        pr_ref.append(pr)
        signals.append(dict(record_id=rid, t_sec=float(t),
                            hr_ecg_ref_bpm=None if missing else round(hr, 1),
                            pr_ppg_ref_bpm=None if missing else round(pr, 1),
                            spo2_ref_percent=round(min(97 + rnd.gauss(0, 0.4), 100.0), 1)))
    estimates = []
    for t in range(4, n, 2):  # cửa sổ 4 s, bước 2 s
        bad = 200 <= t < 216  # cửa sổ nhiễu -> không hợp lệ
        est = pr_ref[t - 1] + rnd.gauss(0, 2.0)
        estimates.append(dict(record_id=rid, t_sec=float(t), hr_est_bpm=None if bad else round(est, 1),
                              is_valid=not bad))
    with engine.begin() as conn:
        db.save_reference(conn, rid, source="SYNTHETIC", duration_s=n,
                          notes="Dữ liệu tổng hợp để thử giao diện, không phải BIDMC.",
                          signals=signals, estimates=estimates)
    print(f"Đã nạp bản ghi tham chiếu tổng hợp '{rid}' ({len(signals)} mẫu, {len(estimates)} ước lượng).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", default="node_01")
    ap.add_argument("--scenario", choices=list(SCENARIOS), default="normal")
    ap.add_argument("--minutes", type=float, default=60, help="thời lượng dữ liệu sinh ra (phút)")
    ap.add_argument("--interval", type=float, default=2, help="chu kỳ bản tin (giây)")
    ap.add_argument("--reset", action="store_true", help="xóa measurements của thiết bị trước khi nạp")
    ap.add_argument("--with-reference", action="store_true", help="nạp thêm bản ghi tham chiếu tổng hợp")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--list", action="store_true", help="liệt kê các kịch bản rồi thoát")
    args = ap.parse_args()

    if args.list:
        for k, v in SCENARIOS.items():
            print(f"{k:8s} {v}")
        return

    engine = db.get_engine()
    db.init_schema(engine)
    m = db.measurements
    with engine.begin() as conn:
        if args.scenario == "empty":
            conn.execute(delete(m))
            print("Đã xóa toàn bộ measurements.")
        else:
            db.ensure_device(conn, args.device)
            if args.reset:
                conn.execute(delete(m).where(m.c.device_id == args.device))
            start_seq = conn.execute(select(func.coalesce(func.max(m.c.sequence), 0))
                                     .where(m.c.device_id == args.device)).scalar_one()
            rows = build_rows(args.device, args.scenario, args.minutes, args.interval, int(start_seq), args.seed)
            if rows:
                conn.execute(m.insert(), rows)
            print(f"Đã nạp {len(rows)} bản ghi cho '{args.device}' (kịch bản: {args.scenario}).")
    if args.with_reference:
        seed_reference(engine)


if __name__ == "__main__":
    main()
