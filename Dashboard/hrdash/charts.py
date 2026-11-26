"""Biểu đồ Plotly: lịch sử HR/SpO₂ (tô khoảng mất/không hợp lệ), dữ liệu tham chiếu, HR ước lượng vs tham chiếu."""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config, logic

C_INVALID = "rgba(255,159,64,0.30)"  # cam: số đo không hợp lệ
C_GAP = "rgba(220,53,69,0.22)"  # đỏ: mất dữ liệu
C_NOREF = "rgba(120,120,120,0.22)"  # xám: tham chiếu bị thiếu
C_HR, C_PR, C_SPO2, C_EST = "#d62728", "#1f77b4", "#2ca02c", "#9467bd"


def _empty(message: str, height=320) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=16))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def _swatch(fig, color, name, row=1, col=1):
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=name, hoverinfo="skip",
                             marker=dict(size=12, color=color, symbol="square")), row=row, col=col)


def history_chart(df, intervals, window=None, height=560) -> go.Figure:
    """HR (hàng 1) và SpO₂ mô phỏng (hàng 2). Số đo không hợp lệ là NULL nên đường bị ngắt, không vẽ số 0."""
    if df is None or df.empty:
        msg = "Không có dữ liệu trong khoảng thời gian này"
        if window is not None and intervals is not None and len(intervals):
            msg += " (toàn bộ khoảng được coi là mất dữ liệu)"
        return _empty(msg)

    d = logic.downsample(df)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                        subplot_titles=("Nhịp tim HR (bpm)", f"{config.SPO2_LABEL} (%)"))
    fig.add_trace(go.Scatter(x=d["ts"], y=d["heart_rate_bpm"], mode="lines+markers", name="HR (bpm)",
                             connectgaps=False, line=dict(width=1.5, color=C_HR), marker=dict(size=4)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=d["ts"], y=d["spo2_percent"], mode="lines+markers", name=config.SPO2_LABEL,
                             connectgaps=False, line=dict(width=1.5, color=C_SPO2), marker=dict(size=4)),
                  row=2, col=1)

    if intervals is not None and len(intervals):
        shown = intervals.head(config.MAX_SHADES)
        for r in shown.itertuples():
            color = C_INVALID if r.kind == "invalid" else C_GAP
            fig.add_vrect(x0=r.start.to_pydatetime(), x1=r.end.to_pydatetime(), fillcolor=color,
                          line_width=0, layer="below", row="all", col="all")
        if (intervals["kind"] == "invalid").any():
            _swatch(fig, C_INVALID, "Không hợp lệ")
        if (intervals["kind"] == "gap").any():
            _swatch(fig, C_GAP, "Mất dữ liệu")

    fig.update_yaxes(range=[70, 101], row=2, col=1)
    fig.update_yaxes(title_text="bpm", row=1, col=1)
    fig.update_yaxes(title_text="% (mô phỏng)" if config.SPO2_SIMULATED else "%", row=2, col=1)
    if window is not None:
        fig.update_xaxes(range=[window[0], window[1]])
    fig.update_layout(height=height, hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=1.08, x=0))
    return fig


def reference_chart(ref, height=520) -> go.Figure:
    """Ngày 22: dữ liệu tham chiếu (HR từ ECG, PR từ PPG, SpO₂ tham chiếu) theo thời gian từ đầu bản ghi."""
    if ref is None or ref.empty:
        return _empty("Chưa có dữ liệu tham chiếu cho bản ghi này")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=("Nhịp tim tham chiếu (bpm)", "SpO₂ tham chiếu (%)"))
    fig.add_trace(go.Scatter(x=ref["t_sec"], y=ref["hr_ecg_ref_bpm"], mode="lines", connectgaps=False,
                             name="HR từ ECG (numerics HR)", line=dict(color=C_HR, width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=ref["t_sec"], y=ref["pr_ppg_ref_bpm"], mode="lines", connectgaps=False,
                             name="PR từ PPG (numerics PULSE)", line=dict(color=C_PR, width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=ref["t_sec"], y=ref["spo2_ref_percent"], mode="lines", connectgaps=False,
                             name="SpO₂ tham chiếu", line=dict(color=C_SPO2, width=1.6)), row=2, col=1)
    missing = (ref["hr_ecg_ref_bpm"].isna() & ref["pr_ppg_ref_bpm"].isna()).to_numpy()
    runs = logic.mask_runs(ref["t_sec"].to_numpy(), missing)
    for t0, t1 in runs[: config.MAX_SHADES]:
        fig.add_vrect(x0=float(t0), x1=float(t1), fillcolor=C_NOREF, line_width=0, layer="below",
                      row="all", col="all")
    if runs:
        _swatch(fig, C_NOREF, "Tham chiếu bị thiếu")
    fig.update_xaxes(title_text="Thời gian từ đầu bản ghi (giây)", row=2, col=1)
    fig.update_yaxes(title_text="bpm", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_layout(height=height, hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=1.08, x=0))
    return fig


def compare_chart(m, ref_label, height=600) -> go.Figure:
    """Ngày 24: HR ước lượng (thuật toán) và HR tham chiếu cùng trục thời gian + sai số theo thời gian."""
    if m is None or m.empty:
        return _empty("Chưa có dữ liệu ước lượng HR để so sánh")
    t = m["t_sec"].to_numpy()
    est_valid = m["hr_est_bpm"].where(m["is_valid"].astype(bool))
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.68, 0.32],
                        subplot_titles=("HR ước lượng và HR tham chiếu (bpm)", "Sai số = ước lượng − tham chiếu (bpm)"))
    fig.add_trace(go.Scatter(x=t, y=m["ref_bpm"], mode="lines", connectgaps=False, name=ref_label,
                             line=dict(color=C_PR, width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=est_valid, mode="lines+markers", connectgaps=False,
                             name="HR ước lượng (PPG)", line=dict(color=C_EST, width=1.2),
                             marker=dict(size=4)), row=1, col=1)
    usable = m["usable"].to_numpy()
    fig.add_trace(go.Bar(x=t[usable], y=m["err"].to_numpy()[usable], name="Sai số (cặp hợp lệ)",
                         marker_color=C_EST), row=2, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="gray", row=2, col=1)

    bad = (~m["is_valid"].astype(bool) | m["hr_est_bpm"].isna()).to_numpy()
    runs = logic.mask_runs(t, bad)
    for t0, t1 in runs[: config.MAX_SHADES]:
        fig.add_vrect(x0=float(t0), x1=float(t1), fillcolor=C_INVALID, line_width=0, layer="below",
                      row="all", col="all")
    if runs:
        _swatch(fig, C_INVALID, "Cửa sổ ước lượng không hợp lệ")
    noref = m["ref_bpm"].isna().to_numpy() & ~bad
    runs2 = logic.mask_runs(t, noref)
    for t0, t1 in runs2[: config.MAX_SHADES]:
        fig.add_vrect(x0=float(t0), x1=float(t1), fillcolor=C_NOREF, line_width=0, layer="below",
                      row="all", col="all")
    if runs2:
        _swatch(fig, C_NOREF, "Không có tham chiếu tương ứng")
    fig.update_xaxes(title_text="Thời gian từ đầu bản ghi (giây)", row=2, col=1)
    fig.update_yaxes(title_text="bpm", row=1, col=1)
    fig.update_yaxes(title_text="bpm", row=2, col=1)
    fig.update_layout(height=height, hovermode="x unified", margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=1.08, x=0))
    return fig
