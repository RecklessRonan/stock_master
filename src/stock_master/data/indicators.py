"""技术指标计算."""

from __future__ import annotations

import pandas as pd


def add_ma(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """添加移动平均线."""
    if periods is None:
        periods = [5, 10, 20, 60, 120]
    for p in periods:
        df[f"MA{p}"] = df["收盘"].rolling(window=p).mean()
    return df


def add_macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """添加 MACD 指标."""
    ema_fast = df["收盘"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["收盘"].ewm(span=slow, adjust=False).mean()
    df["MACD_DIF"] = ema_fast - ema_slow
    df["MACD_DEA"] = df["MACD_DIF"].ewm(span=signal, adjust=False).mean()
    df["MACD_HIST"] = 2 * (df["MACD_DIF"] - df["MACD_DEA"])
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """添加 RSI 指标."""
    delta = df["收盘"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df[f"RSI{period}"] = 100 - (100 / (1 + rs))
    return df


def add_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """添加布林带."""
    mid = df["收盘"].rolling(window=period).mean()
    std = df["收盘"].rolling(window=period).std()
    df["BOLL_MID"] = mid
    df["BOLL_UP"] = mid + std_dev * std
    df["BOLL_DN"] = mid - std_dev * std
    return df


def add_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """添加 KDJ 指标."""
    low_min = df["最低"].rolling(window=n).min()
    high_max = df["最高"].rolling(window=n).max()
    rsv = (df["收盘"] - low_min) / (high_max - low_min).replace(0, float("nan")) * 100

    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d

    df["KDJ_K"] = k
    df["KDJ_D"] = d
    df["KDJ_J"] = j
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """一次性添加所有技术指标."""
    df = add_ma(df)
    df = add_macd(df)
    df = add_rsi(df)
    df = add_bollinger(df)
    df = add_kdj(df)
    return df
