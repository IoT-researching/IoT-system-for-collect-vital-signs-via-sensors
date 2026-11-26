"""Dashboard Streamlit – TV4 (Database/Dashboard).  Chạy:  streamlit run app.py

Tab 1  Trực tiếp        : trạng thái node, HR, SpO₂ (mô phỏng), cảnh báo demo, biểu đồ 5 phút   (D25, D26)
Tab 2  Lịch sử          : biểu đồ HR/SpO₂, khoảng mất/không hợp lệ, bảng + lọc + CSV           (D23)
Tab 3  Tham chiếu       : biểu đồ dữ liệu tham chiếu BIDMC                                      (D22)
Tab 4  So sánh HR       : HR ước lượng vs tham chiếu, sai số                                    (D24)
"""
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from hrdash import charts, config, db, logic, queries

st.set_page_config(page_title="Dashboard HR/SpO₂", page_icon="🫀", layout="wide")

PRESETS = {"15 phút": 15, "1 giờ": 60, "6 giờ": 360, "24 giờ": 1440, "7 ngày": 10080}
CUSTOM = "Chọn ngày…"


# ----------------------------------------------------------------------------- tiện ích
@st.cache_resource(show_spinner=False)
def get_engine():
    eng = db.get_engine()
    try:
        db.init_schema(eng)  # chỉ tạo bảng còn thiếu; bỏ qua nếu không đủ quyền / chưa kết nối được
    except Exception:  # noqa: BLE001
        pass
    return eng


@st.cache_data(ttl=10, show_spinner=False)
def cached_history(_engine, device_id, since, until):
    return queries.history(_engine, device_id, since, until)


def safe(fn, *args, default=None, what="dữ liệu"):
    """Gọi hàm đọc dữ liệu; lỗi được báo thân thiện thay vì làm sập giao diện."""
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Không đọc được {what}. Kiểm tra kết nối CSDL rồi tải lại trang.")
        with st.expander("Chi tiết kỹ thuật"):
            st.code(f"{type(exc).__name__}: {exc}")
        return default


def fmt(value, nd=0, unit=""):
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.{nd}f}{unit}"


def local_days_to_utc(d0: date, d1: date):
    tz = ZoneInfo(config.DISPLAY_TZ)
    s = datetime.combine(d0, dtime.min, tzinfo=tz)
    e = datetime.combine(d1, dtime.max, tzinfo=tz)
    return (s.astimezone(timezone.utc).replace(tzinfo=None), e.astimezone(timezone.utc).replace(tzinfo=None))


def intervals_table(iv: pd.DataFrame) -> pd.DataFrame:
    if iv is None or iv.empty:
        return pd.DataFrame()
    out = iv.copy()
    out["kind"] = out["kind"].map(logic.KIND_VI)
    out["duration_s"] = out["duration_s"].round(1)
    return out.rename(columns={"kind": "Loại", "start": "Bắt đầu", "end": "Kết thúc",
                               "duration_s": "Thời lượng (s)", "n_samples": "Số bản tin", "detail": "Ghi chú"})


# ----------------------------------------------------------------------------- khởi động
engine = get_engine()
ok, err = queries.ping(engine)
st.title("🫀 Dashboard HR / SpO₂")
st.warning(f"{config.DISCLAIMER}  \n{config.SPO2_NOTE}")

if not ok:
    st.error("Không kết nối được CSDL. Kiểm tra SQL Server đang chạy, ODBC Driver đã cài và file `.env`.")
    st.code(err)
    st.info("Muốn xem thử nhanh không cần SQL Server: đặt `DB_BACKEND=sqlite` trong `.env`, chạy "
            "`python -m tools.seed_demo_data --scenario mixed --reset --with-reference`.")
    if st.button("Thử kết nối lại"):
        st.cache_resource.clear()
        st.rerun()
    st.stop()

# ----------------------------------------------------------------------------- thanh bên
st.sidebar.header("Điều khiển")
devices = safe(queries.list_devices, engine, default=[], what="danh sách thiết bị")
device_id = st.sidebar.selectbox("Thiết bị (device_id)", devices) if devices else None
auto = st.sidebar.toggle("Tự động làm mới (tab Trực tiếp)", value=True)
refresh_s = st.sidebar.slider("Chu kỳ làm mới (giây)", 2, 30, 5)
if st.sidebar.button("Xóa bộ nhớ đệm & tải lại"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption(f"CSDL: {'SQLite (demo)' if config.is_sqlite() else 'SQL Server'} · "
                   f"Múi giờ hiển thị: {config.DISPLAY_TZ}")
with st.sidebar.expander("Ngưỡng đang dùng"):
    st.markdown(
        f"- Online ≤ **{config.ONLINE_MAX_AGE_S:.0f} s**; dữ liệu cũ ≤ **{config.STALE_MAX_AGE_S:.0f} s**; "
        "quá mức đó: offline\n"
        f"- Mất dữ liệu: khoảng cách > **{config.GAP_FACTOR} × {config.EXPECTED_INTERVAL_S:.0f} s** "
        "hoặc nhảy số `sequence`\n"
        f"- Cảnh báo demo: HR < {config.HR_LOW:.0f} hoặc > {config.HR_HIGH:.0f} bpm; "
        f"SpO₂ < {config.SPO2_WARN:.0f}% (rất thấp < {config.SPO2_CRIT:.0f}%)")


# ----------------------------------------------------------------------------- Tab 1: trực tiếp
def tab_live():
    if not device_id:
        st.info("Chưa có dữ liệu trong bảng `measurements`. Nạp dữ liệu mẫu: "
                "`python -m tools.seed_demo_data --scenario normal --reset`.")
        return

    @st.fragment(run_every=(refresh_s if auto else None))
    def panel():
        last_seen = safe(queries.last_seen, engine, device_id, what="thời điểm nhận bản tin cuối")
        status, age = logic.node_status(last_seen)
        icon, label = logic.STATUS_META[status]
        latest = safe(queries.latest_measurement, engine, device_id, what="số đo mới nhất")
        last_ok = safe(queries.latest_valid_measurement, engine, device_id, what="số đo hợp lệ gần nhất")

        stale = status in ("stale", "offline")
        suffix = " · dữ liệu cũ" if stale else ""
        cur_valid = bool(latest and latest.get("measurement_valid"))
        hr = latest.get("heart_rate_bpm") if cur_valid else None
        sp = latest.get("spo2_percent") if cur_valid else None
        quality = (latest or {}).get("signal_quality")

        c0, c1, c2, c3, c4 = st.columns([1.3, 1, 1.1, 1, 1])
        c0.markdown(f"#### {icon} {label}")
        c0.caption(f"Bản tin cuối: {logic.humanize_age(age)}")
        c1.metric("HR (bpm)" + suffix, fmt(hr, 0))
        c2.metric(config.SPO2_LABEL + suffix, fmt(sp, 1, " %"))
        c2.caption(config.SPO2_BADGE)
        c3.metric("Chất lượng tín hiệu", logic.QUALITY_VI.get(quality, quality or "—"))
        c4.metric("Trạng thái số đo", "Hợp lệ" if cur_valid else ("Không hợp lệ" if latest else "—"))

        if latest and not cur_valid and last_ok:
            st.caption(f"Số đo hợp lệ gần nhất lúc {last_ok['ts']:%H:%M:%S %d/%m} (không phải giá trị hiện tại): "
                       f"HR {fmt(last_ok.get('heart_rate_bpm'), 0)} bpm · "
                       f"{config.SPO2_LABEL} {fmt(last_ok.get('spo2_percent'), 1)} %")

        alerts = logic.evaluate_alerts(latest, status)
        if not alerts:
            st.success("Không có cảnh báo (ngưỡng demo).")
        for level, msg in alerts:
            {"error": st.error, "warning": st.warning}.get(level, st.info)(msg)

        until = logic.utcnow_naive()
        since = until - timedelta(minutes=5)
        window = (logic.utc_to_local(since), logic.utc_to_local(until))
        df = safe(queries.history, engine, device_id, since, until, default=pd.DataFrame(),
                  what="biểu đồ 5 phút gần nhất")
        iv = logic.detect_intervals(df, window=window)
        st.caption("5 phút gần nhất tính đến hiện tại · vùng cam: không hợp lệ · vùng đỏ: mất dữ liệu")
        st.plotly_chart(charts.history_chart(df, iv, window=window, height=480), key="live_chart")

    panel()


# ----------------------------------------------------------------------------- Tab 2: lịch sử
def tab_history():
    if not device_id:
        st.info("Chưa có dữ liệu lịch sử.")
        return
    c1, c2 = st.columns([2, 3])
    choice = c1.selectbox("Khoảng thời gian", list(PRESETS) + [CUSTOM], index=1)
    if choice == CUSTOM:
        today = logic.utc_to_local(logic.utcnow_naive()).date()
        picked = c2.date_input("Từ ngày – đến ngày (giờ địa phương)", value=(today - timedelta(days=1), today))
        if not (isinstance(picked, (tuple, list)) and len(picked) == 2):
            st.info("Chọn đủ ngày bắt đầu và ngày kết thúc.")
            return
        since, until = local_days_to_utc(picked[0], picked[1])
    else:
        until = logic.utcnow_naive().replace(microsecond=0)
        since = until - timedelta(minutes=PRESETS[choice])

    df = safe(cached_history, engine, device_id, since, until, default=pd.DataFrame(), what="lịch sử đo")
    window = (logic.utc_to_local(since), logic.utc_to_local(until))
    iv = logic.detect_intervals(df, window=window)
    q = logic.summarize_quality(df, iv)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Số bản ghi", q["total"])
    m2.metric("Tỷ lệ hợp lệ", fmt(q["pct_valid"], 1, " %"))
    m3.metric("Không hợp lệ", q["invalid"])
    m4.metric("Số lần mất dữ liệu", q["gap_count"])
    m5.metric("Bản tin thiếu (ước tính)", q["missing_packets"])
    if len(df) >= config.MAX_ROWS:
        st.warning(f"Chỉ hiển thị {config.MAX_ROWS:,} bản ghi gần nhất trong khoảng đã chọn.")

    st.plotly_chart(charts.history_chart(df, iv, window=window), key="hist_chart")
    st.caption(f"{config.SPO2_LABEL}: {config.SPO2_BADGE}. Số đo không hợp lệ là NULL nên đường biểu đồ bị ngắt "
               "(không vẽ số 0). Tô màu: cam = không hợp lệ, đỏ = mất dữ liệu.")

    with st.expander(f"Khoảng không hợp lệ / mất dữ liệu ({len(iv)})", expanded=len(iv) > 0):
        tbl = intervals_table(iv)
        if tbl.empty:
            st.success("Không phát hiện khoảng không hợp lệ hoặc mất dữ liệu.")
        else:
            st.dataframe(tbl, hide_index=True)
            st.download_button("Tải danh sách khoảng (CSV)", tbl.to_csv(index=False).encode("utf-8-sig"),
                               file_name="khoang_mat_khong_hop_le.csv", mime="text/csv")

    st.subheader("Bảng dữ liệu")
    f1, f2, f3 = st.columns([1, 2, 1])
    valid_only = f1.checkbox("Chỉ số đo hợp lệ", value=False)
    options = sorted(df["signal_quality"].dropna().unique().tolist()) if len(df) else []
    picked_q = f2.multiselect("Chất lượng tín hiệu", options, default=options)
    page_size = f3.selectbox("Số dòng / trang", [25, 50, 100], index=1)

    view = df.copy()
    if valid_only:
        view = view[view["measurement_valid"]]
    if options:
        view = view[view["signal_quality"].isin(picked_q)]
    view = view.sort_values("ts", ascending=False)
    pages = max((len(view) - 1) // page_size + 1, 1)
    page = st.number_input("Trang", min_value=1, max_value=pages, value=1, step=1)
    shown = view.iloc[(page - 1) * page_size: page * page_size]
    table = pd.DataFrame({
        "Thời gian": shown["ts"], "device_id": shown["device_id"],
        "HR (bpm)": shown["heart_rate_bpm"], f"{config.SPO2_LABEL} (%)": shown["spo2_percent"],
        "Chất lượng": shown["signal_quality"].map(lambda v: logic.QUALITY_VI.get(v, v)),
        "Hợp lệ": shown["measurement_valid"].map({True: "✔", False: "✘"}), "sequence": shown["sequence"],
    })
    if table.empty:
        st.info("Không có bản ghi nào khớp bộ lọc.")
    else:
        st.dataframe(table, hide_index=True)
        st.caption(f"Trang {page}/{pages} · {len(view):,} bản ghi khớp bộ lọc. Ô trống = NULL (không có số đo hợp lệ).")
        st.download_button("Tải dữ liệu đã lọc (CSV)",
                           view.drop(columns=["ts"]).to_csv(index=False).encode("utf-8-sig"),
                           file_name="lich_su_do.csv", mime="text/csv")


# ----------------------------------------------------------------------------- Tab 3 & 4: tham chiếu
def pick_record(key):
    recs = safe(queries.list_reference_records, engine, default=pd.DataFrame(), what="danh sách bản ghi tham chiếu")
    if recs is None or recs.empty:
        st.info("Chưa có dữ liệu tham chiếu. Nạp bản ghi BIDMC: "
                "`python -m tools.import_bidmc --numerics duong_dan/bidmc_01_Numerics.csv`  \n"
                "hoặc dữ liệu tổng hợp để thử giao diện: "
                "`python -m tools.seed_demo_data --scenario normal --with-reference`.")
        return None, None
    rid = st.selectbox("Bản ghi tham chiếu", recs["record_id"].tolist(), key=key,
                       format_func=lambda r: f"{r}  ({recs.loc[recs['record_id'] == r, 'source'].iloc[0]})")
    meta = recs[recs["record_id"] == rid].iloc[0]
    if str(meta["source"]).upper() != "BIDMC":
        st.warning("⚠️ DỮ LIỆU TỔNG HỢP (không phải BIDMC thật) – chỉ để thử giao diện, "
                   "không dùng làm kết quả nghiên cứu.")
    return rid, meta


def tab_reference():
    rid, meta = pick_record("ref_rec")
    if rid is None:
        return
    ref = safe(queries.reference_signals, engine, rid, default=pd.DataFrame(), what="tín hiệu tham chiếu")
    st.plotly_chart(charts.reference_chart(ref), key="ref_chart")
    n = len(ref)
    miss = int((ref["hr_ecg_ref_bpm"].isna() & ref["pr_ppg_ref_bpm"].isna()).sum()) if n else 0
    st.caption(f"{n} mẫu (numerics, tần số xấp xỉ 1 Hz) · thiếu cả HR lẫn PR: {miss} mẫu · "
               f"thời lượng: {fmt(meta.get('duration_s'), 0, ' s')}")
    st.info("**Lưu ý khi dùng BIDMC làm tham chiếu:** BIDMC không phải tín hiệu đo trực tiếp từ MAX30102. "
            "HR suy ra từ ECG khác với PR suy ra từ PPG; với thuật toán dựa trên PPG nên so với **PR (PPG)** "
            "trước, và ghi rõ loại tham chiếu đã dùng.")


def tab_compare():
    rid, meta = pick_record("cmp_rec")
    if rid is None:
        return
    c1, c2 = st.columns([2, 1])
    kind = c1.radio("Loại tham chiếu", ["PR từ PPG (numerics PULSE)", "HR từ ECG (numerics HR)"], horizontal=True)
    tol = c2.slider("Dung sai ghép thời gian (giây)", 0.5, 5.0, 1.0, 0.5)
    col = "pr_ppg_ref_bpm" if kind.startswith("PR") else "hr_ecg_ref_bpm"
    ref = safe(queries.reference_signals, engine, rid, default=pd.DataFrame(), what="tín hiệu tham chiếu")
    est = safe(queries.hr_estimates, engine, rid, default=pd.DataFrame(), what="kết quả ước lượng HR")
    if est is None or est.empty:
        st.info("Bản ghi này chưa có kết quả ước lượng HR. Nạp file CSV do TV1/TV3 xuất: "
                "`python -m tools.import_bidmc --record bidmc01 --estimates hr_estimates.csv` "
                "(cột: `t_sec, hr_est_bpm, is_valid`).")
        return
    m = logic.align_reference(est, ref, col, tol)
    st.plotly_chart(charts.compare_chart(m, kind), key="cmp_chart")
    s = logic.error_stats(m)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Số cặp hợp lệ", s["n"])
    k2.metric("MAE (bpm)", fmt(s["mae"], 2))
    k3.metric("RMSE (bpm)", fmt(s["rmse"], 2))
    k4.metric("Sai số trung bình (bpm)", fmt(s["bias"], 2))
    st.caption("Chỉ số tham khảo, tính trên các cặp (ước lượng hợp lệ, tham chiếu có sẵn) đã ghép thời gian trong "
               "dung sai. Cửa sổ không hợp lệ bị loại, không tính thành sai số. Số liệu đánh giá chính thức do TV5 công bố.")


# ----------------------------------------------------------------------------- bố cục
t1, t2, t3, t4 = st.tabs(["📡 Trực tiếp", "📈 Lịch sử", "📚 Dữ liệu tham chiếu", "⚖️ So sánh HR"])
with t1:
    tab_live()
with t2:
    tab_history()
with t3:
    tab_reference()
with t4:
    tab_compare()

st.divider()
st.caption(f"{config.DISCLAIMER} · BIDMC (PhysioNet) chỉ là nguồn dữ liệu tham chiếu cho nghiên cứu.")
