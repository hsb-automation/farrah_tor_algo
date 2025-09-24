import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Win Ratio — Threshold Filter (Per Timeframe Tables)", layout="wide")

EXCEL_PATH = "data.xlsx"  # same folder

TIMEFRAME_ORDER = ["5m","30m","1h","6h","12h","24h"]
COLOR_MAP = {
    3.0: "pink",
    2.5: "blue",
    2.0: "green",
    1.5: "yellow",
    1.0: "orange",
    0.5: "red",
}
DEFAULT_COLOR = "gray"

@st.cache_data
def load_data(path):
    xls = pd.ExcelFile(path)
    df_buy = pd.read_excel(xls, "Prob_Buy_with_Ratio")
    df_sell = pd.read_excel(xls, "Prob_Sell_with_Ratio")
    tf_buy_above  = pd.read_excel(xls, "TF_Buy_Above")
    tf_buy_below  = pd.read_excel(xls, "TF_Buy_Below")
    tf_sell_above = pd.read_excel(xls, "TF_Sell_Above")
    tf_sell_below = pd.read_excel(xls, "TF_Sell_Below")
    return df_buy, df_sell, tf_buy_above, tf_buy_below, tf_sell_above, tf_sell_below

df_buy, df_sell, tf_buy_above, tf_buy_below, tf_sell_above, tf_sell_below = load_data(EXCEL_PATH)

# Ensure timeframe order for the chart
for d in (df_buy, df_sell):
    d["Timeframe"] = pd.Categorical(d["Timeframe"], categories=TIMEFRAME_ORDER, ordered=True)

st.title("Win Ratio by Timeframe")

with st.sidebar:
    st.header("Chart Filters")
    direction = st.radio("Direction", ["Buy","Sell"], horizontal=True, index=0)
    side = st.radio("Condition", ["above", "below"], horizontal=True, index=0)
    show_all = st.checkbox("Show ALL thresholds (multi-line)", value=False)
    show_ci = st.checkbox("Show 95% Wilson CI", value=True)

    table = df_buy if direction == "Buy" else df_sell
    thresholds_available = sorted(table["Threshold"].dropna().unique().tolist())
    threshold = st.selectbox("Threshold", thresholds_available, index=0, disabled=show_all)

# ---------- Chart ----------
data = df_buy if direction == "Buy" else df_sell
fig = go.Figure()

if show_all:
    for thr in thresholds_available:
        sel = (data["Threshold"] == thr) & (data["Side"] == side)
        d = data.loc[sel].sort_values("Timeframe")
        if d.empty: 
            continue
        x = d["Timeframe"].astype(str)
        y = d["Prob"]
        err_plus  = (d["Wilson_U"] - d["Prob"]).clip(lower=0)
        err_minus = (d["Prob"] - d["Wilson_L"]).clip(lower=0)
        color = COLOR_MAP.get(float(thr), DEFAULT_COLOR)
        err_cfg = dict(type="data", array=err_plus, arrayminus=err_minus, visible=True) if show_ci else None

        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines+markers",
            name=f"{thr:g}",
            line=dict(color=color, width=2),
            marker=dict(color=color),
            error_y=err_cfg
        ))
else:
    sel = (data["Threshold"] == threshold) & (data["Side"] == side)
    d = data.loc[sel].sort_values("Timeframe")
    x = d["Timeframe"].astype(str)
    y = d["Prob"]
    err_plus  = (d["Wilson_U"] - d["Prob"]).clip(lower=0)
    err_minus = (d["Prob"] - d["Wilson_L"]).clip(lower=0)
    color = COLOR_MAP.get(float(threshold), DEFAULT_COLOR)
    err_cfg = dict(type="data", array=err_plus, arrayminus=err_minus, visible=True) if show_ci else None

    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines+markers",
        name=f"{direction} — {side} {threshold:g}",
        line=dict(color=color, width=3),
        marker=dict(color=color),
        error_y=err_cfg
    ))

title_txt = f"{direction} Win Ratio — Answer5 " + (">=" if side=="above" else "<") + f" {'ALL' if show_all else f'{float(threshold):g}'}"
fig.update_layout(
    title=title_txt,
    xaxis_title="Timeframe",
    yaxis_title="Win Ratio (Probability to Profit)",
    yaxis=dict(range=[0,1]),
    margin=dict(l=30, r=20, t=60, b=30),
    legend_title="Threshold" if show_all else None
)
fig.update_xaxes(showgrid=True, gridcolor="#d0d0d0", gridwidth=1, griddash="dash", zeroline=False)
fig.update_yaxes(showgrid=True, gridcolor="#d0d0d0", gridwidth=1, griddash="dash", zeroline=False)
st.plotly_chart(fig, use_container_width=True)

# ---------- Per-timeframe tables ----------
st.divider()
st.header("Per-Timeframe Threshold Summary Table")

col1, col2, col3 = st.columns([1,1,2])
with col1:
    tf_choice = st.selectbox("Timeframe", TIMEFRAME_ORDER, index=0)
with col2:
    tbl_direction = st.radio("Table Direction", ["Buy","Sell"], horizontal=True, index=0)
with col3:
    tbl_side = st.radio("Table Condition", ["above","below"], horizontal=True, index=0)

# Pick the right dataframe
if tbl_direction == "Buy" and tbl_side == "above":
    tbl = tf_buy_above
elif tbl_direction == "Buy" and tbl_side == "below":
    tbl = tf_buy_below
elif tbl_direction == "Sell" and tbl_side == "above":
    tbl = tf_sell_above
else:
    tbl = tf_sell_below

view = tbl[tbl["Timeframe"] == tf_choice].copy()

# Pretty formatting
def pretty(df):
    return df.style.format({
        "Win_Ratio": "{:.2%}",
        "Wilson_L": "{:.2%}",
        "Wilson_U": "{:.2%}",
        "Base_Win_Ratio": "{:.2%}",
        "Lift_vs_Base": "{:.3f}"
    })

st.dataframe(pretty(view), use_container_width=True)
