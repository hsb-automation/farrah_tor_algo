import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Win Ratio, ML & Descriptive", layout="wide")
EXCEL_PATH = "data2.xlsx"

TIMEFRAME_ORDER = ["5m","30m","1h","6h","12h","24h"]
COLOR_MAP = {3.0:"pink", 2.5:"blue", 2.0:"green", 1.5:"yellow", 1.0:"orange", 0.5:"red"}
DEFAULT_COLOR = "gray"

@st.cache_data
def load_all(path: str):
    xls = pd.ExcelFile(path)
    ml_all = pd.read_excel(xls, "ML_Predictions_All")
    prob_buy  = pd.read_excel(xls, "Prob_Buy_with_Ratio")  if "Prob_Buy_with_Ratio"  in xls.sheet_names else None
    prob_sell = pd.read_excel(xls, "Prob_Sell_with_Ratio") if "Prob_Sell_with_Ratio" in xls.sheet_names else None
    desc_all  = pd.read_excel(xls, "Descriptive_All")      if "Descriptive_All"      in xls.sheet_names else None
    return ml_all, prob_buy, prob_sell, desc_all

def attach_ci(df_ml, direction, condition, prob_buy, prob_sell):
    src = prob_buy if direction=="Buy" else prob_sell
    if src is None:
        return df_ml
    ci = src[src["Side"].str.lower()==condition.lower()].copy()
    ci = ci[["Timeframe","Threshold","N","Prob","Wilson_L","Wilson_U"]]
    ci = ci.sort_values(["Timeframe","Threshold","N"], ascending=[True,True,False]).drop_duplicates(["Timeframe","Threshold"])
    out = df_ml.merge(ci, on=["Timeframe","Threshold"], how="left", suffixes=("","_ci"))
    if {"Wilson_L","Wilson_U"}.issubset(out.columns):
        out["Margin_of_Error"] = (out["Wilson_U"] - out["Wilson_L"]) / 2.0
    return out

def attach_descriptive(df_ml, desc_all, direction, condition):
    if desc_all is None: 
        return df_ml
    d = desc_all[(desc_all["Direction"]==direction) & (desc_all["Condition"]==condition)].copy()
    d = d[["Timeframe","Threshold","N","Avg_Profit_%","Min_Profit_%","Max_Profit_%","Status","Win_Ratio"]]
    d = d.sort_values(["Timeframe","Threshold","N"], ascending=[True,True,False]).drop_duplicates(["Timeframe","Threshold"])
    out = df_ml.merge(d, on=["Timeframe","Threshold"], how="left", suffixes=("","_desc"))
    return out

def confidence_from_N(n):
    if pd.isna(n): return "Unknown"
    n = float(n)
    if n >= 1000: return "High"
    if n >= 300:  return "Medium"
    if n > 0:     return "Low"
    return "None"

def verdict(signal_strength, avg_pct):
    if pd.isna(signal_strength) and pd.isna(avg_pct): return "Insufficient data"
    s = 0.0 if pd.isna(signal_strength) else signal_strength
    a = 0.0 if pd.isna(avg_pct) else avg_pct
    if s >= 0.03 or a >= 0.25:  
        return "👍 Favourable"
    if s >= 0.00 and a >= 0.00:
        return "⚠️ Marginal"
    return "👎 Unfavourable"

def regime_label(condition):
    return "Trend (Vol ↑)" if condition.lower()=="above" else "Range (Vol ↓)"

@st.cache_data
def prep(EXCEL_PATH):
    ml_all, prob_buy, prob_sell, desc_all = load_all(EXCEL_PATH)
    ml_all["Timeframe"] = pd.Categorical(ml_all["Timeframe"], categories=TIMEFRAME_ORDER, ordered=True)
    return ml_all, prob_buy, prob_sell, desc_all

ml_all, prob_buy, prob_sell, desc_all = prep(EXCEL_PATH)

st.title("Win Ratio, ML & Descriptive")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Filters")
    direction = st.radio("Direction", ["Buy","Sell"], horizontal=True)
    condition = st.radio("Condition", ["above","below"], horizontal=True)
    show_ci = st.checkbox("Show 95% CI (historical)", value=True)

    thresholds_available = sorted(ml_all["Threshold"].dropna().unique().tolist())
    show_all = st.checkbox("Show all thresholds", value=False)  # default unchecked
    threshold = None if show_all else st.selectbox("Threshold", thresholds_available, index=0)

# ---------------- Data slice ----------------
base = ml_all[(ml_all["Direction"]==direction) & (ml_all["Condition"]==condition)].copy()
base = attach_ci(base, direction, condition, prob_buy, prob_sell) if show_ci else base
base = attach_descriptive(base, desc_all, direction, condition)

base["Timeframe"] = pd.Categorical(base["Timeframe"], categories=TIMEFRAME_ORDER, ordered=True)
base = base.sort_values(["Timeframe","Threshold"])

# Derived columns
base["Confidence"] = base.get("N", np.nan).apply(confidence_from_N)
base["Signal_Strength"] = base["ML_Pred_Prob"] - base["Historical_Win_Ratio"]
base["Volatility_Regime"] = regime_label(condition)
base["Verdict"] = base.apply(lambda r: verdict(r["Signal_Strength"], r.get("Avg_Profit_%", np.nan)), axis=1)

# ---------------- Verdict filter as checkboxes ----------------
st.subheader("Verdict Filter")

verdict_options = ["👍 Favourable","⚠️ Marginal","👎 Unfavourable","Insufficient data"]
selected_verdicts = []

col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.checkbox("👍 Favourable", value=True): selected_verdicts.append("👍 Favourable")
with col2:
    if st.checkbox("⚠️ Marginal", value=True): selected_verdicts.append("⚠️ Marginal")
with col3:
    if st.checkbox("👎 Unfavourable", value=True): selected_verdicts.append("👎 Unfavourable")
with col4:
    if st.checkbox("Insufficient data", value=True): selected_verdicts.append("Insufficient data")

# Apply verdict filter
base = base[base["Verdict"].isin(selected_verdicts)]

# ---------------- Visualization ----------------
st.subheader("Win Ratio vs ML Prediction")

fig = go.Figure()
thr_list = thresholds_available if show_all else [threshold]

for thr in thr_list:
    d = base[base["Threshold"]==thr]
    if d.empty: 
        continue
    color = COLOR_MAP.get(float(thr), DEFAULT_COLOR)

    fig.add_trace(go.Scatter(
        x=d["Timeframe"].astype(str),
        y=d["Historical_Win_Ratio"],
        mode="lines+markers",
        name=f"Hist {thr:g}",
        line=dict(color=color, width=2),
        marker=dict(color=color, symbol="circle"),
    ))
    fig.add_trace(go.Scatter(
        x=d["Timeframe"].astype(str),
        y=d["ML_Pred_Prob"],
        mode="lines+markers",
        name=f"ML {thr:g}",
        line=dict(color=color, width=2, dash="dot"),
        marker=dict(color=color, symbol="x"),
    ))

fig.update_layout(
    title=f"{direction} — {condition} " + ("(all thresholds)" if show_all else f"(threshold {float(threshold):g})"),
    xaxis_title="Timeframe",
    yaxis_title="Probability",
    yaxis=dict(range=[0,1]),
    margin=dict(l=30, r=30, t=60, b=30),
    legend_title="Series"
)
st.plotly_chart(fig, use_container_width=True)

# ---------------- Manager Table ----------------
st.subheader("Descriptive Table")

cols = [
    "Direction","Condition","Timeframe","Threshold",
    "Historical_Win_Ratio","ML_Pred_Prob","Signal_Strength",
    "Wilson_L","Wilson_U","Margin_of_Error",
    "N","Confidence",
    "Avg_Profit_%","Min_Profit_%","Max_Profit_%",
    "Volatility_Regime","Verdict"
]
present_cols = [c for c in cols if c in base.columns]
view = base[present_cols].copy().sort_values(["Timeframe","Threshold"])

fmt = {
    "Historical_Win_Ratio": "{:.2%}",
    "ML_Pred_Prob": "{:.2%}",
    "Signal_Strength": "{:+.2%}",
    "Wilson_L": "{:.2%}",
    "Wilson_U": "{:.2%}",
    "Margin_of_Error": "{:.2%}",
    "Avg_Profit_%": "{:.2f}%",
    "Min_Profit_%": "{:.2f}%",
    "Max_Profit_%": "{:.2f}%",
    "N": "{:.0f}",
}

st.dataframe(view.style.format(fmt), use_container_width=True)
