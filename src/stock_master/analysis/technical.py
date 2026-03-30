"""技术面辅助分析."""

from __future__ import annotations

import pandas as pd


def detect_trend(df: pd.DataFrame) -> str:
    """基于均线排列判断趋势."""
    if df.empty or len(df) < 60:
        return "数据不足，无法判断趋势"

    latest = df.iloc[-1]
    ma_cols = ["MA5", "MA10", "MA20", "MA60"]
    available = [c for c in ma_cols if c in df.columns and pd.notna(latest.get(c))]

    if len(available) < 3:
        return "均线数据不足"

    values = [latest[c] for c in available]

    if all(values[i] >= values[i + 1] for i in range(len(values) - 1)):
        return "多头排列（上升趋势）"
    elif all(values[i] <= values[i + 1] for i in range(len(values) - 1)):
        return "空头排列（下降趋势）"
    else:
        return "震荡整理"


def detect_support_resistance(df: pd.DataFrame, lookback: int = 60) -> dict:
    """简单的支撑/阻力位识别."""
    if df.empty or len(df) < lookback:
        return {"support": None, "resistance": None}

    tail = df.tail(lookback)
    return {
        "support": round(tail["最低"].min(), 2),
        "resistance": round(tail["最高"].max(), 2),
    }


def volume_analysis(df: pd.DataFrame) -> str:
    """量价分析."""
    if df.empty or len(df) < 20:
        return "数据不足"

    vol_5 = df["成交量"].iloc[-5:].mean()
    vol_20 = df["成交量"].iloc[-20:].mean()
    ratio = vol_5 / vol_20 if vol_20 > 0 else 1

    price_up = df["收盘"].iloc[-1] > df["收盘"].iloc[-5]

    if ratio > 1.5 and price_up:
        return "放量上涨，多头信号"
    elif ratio > 1.5 and not price_up:
        return "放量下跌，注意风险"
    elif ratio < 0.7 and price_up:
        return "缩量上涨，持续性存疑"
    elif ratio < 0.7 and not price_up:
        return "缩量下跌，可能接近底部"
    else:
        return "量价正常"
