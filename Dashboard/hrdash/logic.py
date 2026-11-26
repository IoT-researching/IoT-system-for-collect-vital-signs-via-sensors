"""Logic thuần (không phụ thuộc Streamlit/CSDL): trạng thái node, khoảng mất dữ liệu, cảnh báo, ghép tham chiếu."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config

STATUS_META = {
    "online": ("🟢", "ONLINE"),
    "stale": ("🟡", "DỮ LIỆU CŨ"),
    "offline": ("🔴", "OFFLINE"),
    "no_data": ("⚪", "CHƯA CÓ DỮ LIỆU"),
}
QUALITY_VI = {"good": "Tốt", "fair": "Trung bình", "poor": "Kém", "no_signal": "Mất tín hiệu"}
INTERVAL_COLS = ["kind", "start", "end", "duration_s", "n_samples", "detail"]
KIND_VI = {"invalid": "Không hợp lệ", "gap": "Mất dữ liệu"}


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_to_local(dt) -> pd.Timestamp:
    return pd.Timestamp(dt).tz_localize("UTC").tz_convert(config.DISPLAY_TZ).tz_localize(None)


def humanize_age(age_s) -> str:
    if age_s is None:
        return "chưa có dữ liệu"
    if age_s < 60:
        return f"{int(age_s)} giây trước"
    if age_s < 3600:
        return f"{int(age_s // 60)} phút {int(age_s % 60)} giây trước"
    return f"{age_s / 3600:.1f} giờ trước"


def node_status(last_seen, now=None, online_s=None, stale_s=None):
    """Trả về (trạng thái, tuổi bản tin tính bằng giây). Dùng thời gian nhận phía server (UTC)."""
    online_s = config.ONLINE_MAX_AGE_S if online_s is None else online_s
    stale_s = config.STALE_MAX_AGE_S if stale_s is None else stale_s
    if last_seen is None or pd.isna(last_seen):
        return "no_data", None
    now = now or utcnow_naive()
    age = max((now - pd.Timestamp(last_seen).to_pydatetime()).total_seconds(), 0.0)  # chống lệch đồng hồ
    if age <= online_s:
        return "online", age
    if age <= stale_s:
        return "stale", age
    return "offline", age


def detect_intervals(df, expected_s=None, gap_factor=None, window=None) -> pd.DataFrame:
    """Tìm các khoảng KHÔNG HỢP LỆ và MẤT DỮ LIỆU.

    df: cột ts (giờ hiển thị), sequence, measurement_valid.
    window: (đầu, cuối) cùng múi giờ với ts; nếu có, khoảng trống ở đầu/cuối cửa sổ cũng được tính.
    Mất dữ liệu = khoảng cách thời gian > gap_factor * chu kỳ, hoặc nhảy số sequence (>= 1 bản tin thiếu).
    """
    expected_s = expected_s or config.EXPECTED_INTERVAL_S
    gap_factor = gap_factor or config.GAP_FACTOR
    thr = gap_factor * expected_s
    rows = []

    def add_gap(a, b, missing=None):
        secs = (b - a).total_seconds()
        miss = missing if missing is not None else max(int(round(secs / expected_s)) - 1, 1)
        rows.append(("gap", a, b, secs, miss, f"thiếu ~{miss} bản tin"))

    if df is None or df.empty:
        if window is not None:
            add_gap(pd.Timestamp(window[0]), pd.Timestamp(window[1]))
        return pd.DataFrame(rows, columns=INTERVAL_COLS)

    d = df.sort_values("ts").reset_index(drop=True)
    ts = d["ts"]
    valid = d["measurement_valid"].astype(bool).to_numpy()
    seq = d["sequence"].to_numpy().astype("float64")
    n = len(d)

    i = 0
    while i < n:  # đoạn không hợp lệ liên tiếp
        if not valid[i]:
            j = i
            while j + 1 < n and not valid[j + 1]:
                j += 1
            start = ts.iloc[i]
            end = ts.iloc[j + 1] if j + 1 < n else ts.iloc[j] + pd.Timedelta(seconds=expected_s)
            rows.append(("invalid", start, end, (end - start).total_seconds(), j - i + 1,
                         f"{j - i + 1} bản tin không hợp lệ"))
            i = j + 1
        else:
            i += 1

    dt = ts.diff().dt.total_seconds().to_numpy()
    dseq = np.diff(seq, prepend=np.nan) - 1  # số bản tin thiếu theo sequence (âm = thiết bị khởi động lại)
    for k in range(1, n):
        seq_loss = dseq[k] >= 1
        if dt[k] > thr or seq_loss:
            add_gap(ts.iloc[k - 1], ts.iloc[k], int(dseq[k]) if seq_loss else None)

    if window is not None:
        w0, w1 = pd.Timestamp(window[0]), pd.Timestamp(window[1])
        if (ts.iloc[0] - w0).total_seconds() > thr:
            add_gap(w0, ts.iloc[0])
        if (w1 - ts.iloc[-1]).total_seconds() > thr:
            add_gap(ts.iloc[-1], w1)

    out = pd.DataFrame(rows, columns=INTERVAL_COLS)
    return out.sort_values("start").reset_index(drop=True)


def summarize_quality(df, intervals) -> dict:
    total = int(len(df))
    valid = int(df["measurement_valid"].astype(bool).sum()) if total else 0
    gaps = intervals[intervals["kind"] == "gap"] if len(intervals) else intervals
    return {
        "total": total,
        "valid": valid,
        "invalid": total - valid,
        "pct_valid": (100.0 * valid / total) if total else None,
        "gap_count": int(len(gaps)),
        "missing_packets": int(gaps["n_samples"].sum()) if len(gaps) else 0,
    }


def evaluate_alerts(latest, status):
    """Cảnh báo DEMO theo ngưỡng cấu hình. Trả về list[(mức, nội dung)], mức: error|warning|info."""
    if status == "no_data":
        return [("info", "Chưa có bản tin nào từ thiết bị này.")]
    out = []
    if status == "offline":
        out.append(("error", f"Node OFFLINE: quá {config.STALE_MAX_AGE_S:.0f} giây không nhận được bản tin mới."))
    elif status == "stale":
        out.append(("warning", f"Dữ liệu cũ: quá {config.ONLINE_MAX_AGE_S:.0f} giây chưa có bản tin mới. "
                               "Các giá trị hiển thị không phải giá trị hiện tại."))
    if not latest:
        return out
    if not latest.get("measurement_valid"):
        out.append(("warning", "Số đo gần nhất không hợp lệ (nhiễu, chưa đặt tay hoặc mất tín hiệu). "
                               "Giá trị này không được đưa vào biểu đồ HR/SpO₂."))
        return out
    hr, sp = latest.get("heart_rate_bpm"), latest.get("spo2_percent")
    if hr is not None and hr > config.HR_HIGH:
        out.append(("warning", f"HR cao: {hr:.0f} bpm (> {config.HR_HIGH:.0f}) – cảnh báo demo."))
    if hr is not None and hr < config.HR_LOW:
        out.append(("warning", f"HR thấp: {hr:.0f} bpm (< {config.HR_LOW:.0f}) – cảnh báo demo."))
    if sp is not None:
        tag = " (mô phỏng)" if config.SPO2_SIMULATED else ""
        if sp < config.SPO2_CRIT:
            out.append(("error", f"SpO₂{tag} rất thấp: {sp:.1f}% (< {config.SPO2_CRIT:.0f}) – cảnh báo demo."))
        elif sp < config.SPO2_WARN:
            out.append(("warning", f"SpO₂{tag} thấp: {sp:.1f}% (< {config.SPO2_WARN:.0f}) – cảnh báo demo."))
    if latest.get("signal_quality") in ("poor", "no_signal"):
        out.append(("warning", "Chất lượng tín hiệu kém – kết quả đo kém tin cậy."))
    return out


def downsample(df, max_points=None):
    max_points = max_points or config.MAX_PLOT_POINTS
    if len(df) <= max_points:
        return df
    step = int(np.ceil(len(df) / max_points))
    return df.iloc[::step]


def mask_runs(t, mask):
    """Các đoạn liên tiếp mask=True -> list[(t0, t1)]; t1 là thời điểm mẫu kế tiếp (hoặc mẫu cuối)."""
    runs, n, i = [], len(t), 0
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]:
                j += 1
            runs.append((t[i], t[j + 1] if j + 1 < n else t[j]))
            i = j + 1
        else:
            i += 1
    return runs


def align_reference(est, ref, ref_col, tol_s=1.0) -> pd.DataFrame:
    """Ghép ước lượng HR với tham chiếu theo t_sec (gần nhất, trong dung sai tol_s)."""
    cols = ["t_sec", "hr_est_bpm", "is_valid", "ref_bpm", "usable", "err"]
    if est is None or est.empty or ref is None or ref.empty:
        return pd.DataFrame(columns=cols)
    e = est[["t_sec", "hr_est_bpm", "is_valid"]].copy()
    e["t_sec"] = e["t_sec"].astype(float)
    e = e.sort_values("t_sec")
    r = ref[["t_sec", ref_col]].dropna().copy()
    r["t_sec"] = r["t_sec"].astype(float)
    r = r.sort_values("t_sec")
    if r.empty:
        m = e.assign(ref_bpm=np.nan)
    else:
        m = pd.merge_asof(e, r.rename(columns={ref_col: "ref_bpm"}), on="t_sec",
                          direction="nearest", tolerance=tol_s)
    m["usable"] = m["is_valid"].astype(bool) & m["hr_est_bpm"].notna() & m["ref_bpm"].notna()
    m["err"] = m["hr_est_bpm"] - m["ref_bpm"]
    return m[cols].reset_index(drop=True)


def error_stats(m) -> dict:
    """MAE/RMSE/bias chỉ trên các cặp hợp lệ đã ghép thời gian. Số liệu chính thức do TV5 chốt."""
    u = m[m["usable"]] if len(m) else m
    if len(u) == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    err = u["err"].to_numpy(dtype=float)
    return {"n": int(len(u)), "mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err ** 2))), "bias": float(np.mean(err))}
