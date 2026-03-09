#!/usr/bin/env python3
"""A股技术分析脚本 - 基于 akshare 拉取数据并计算技术指标"""

import sys
import json
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime


def fetch_stock_data(code: str, days: int = 120) -> pd.DataFrame:
    """拉取日K线数据（前复权）"""
    df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    df = df.tail(days).reset_index(drop=True)
    df.columns = ["date", "stock_code", "open", "close", "high", "low", "volume", "turnover",
                   "amplitude", "change_pct", "change_amt", "turnover_rate"]
    for col in ["open", "close", "high", "low", "volume", "turnover"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def calc_ma(df: pd.DataFrame) -> dict:
    """计算均线"""
    result = {}
    for period in [5, 10, 20, 60]:
        key = f"ma{period}"
        df[key] = df["close"].rolling(period).mean()
        val = df[key].iloc[-1]
        prev = df[key].iloc[-2] if len(df) > 1 else val
        result[key] = {
            "value": round(val, 2),
            "direction": "↑" if val > prev else "↓"
        }

    # 判断排列
    ma_vals = [result[f"ma{p}"]["value"] for p in [5, 10, 20, 60]]
    if ma_vals == sorted(ma_vals, reverse=True):
        trend = "多头排列"
    elif ma_vals == sorted(ma_vals):
        trend = "空头排列"
    else:
        trend = "交叉排列"

    # 金叉/死叉 (MA5 vs MA10)
    ma5_prev = df["ma5"].iloc[-2]
    ma10_prev = df["ma10"].iloc[-2]
    ma5_now = df["ma5"].iloc[-1]
    ma10_now = df["ma10"].iloc[-1]
    if ma5_prev <= ma10_prev and ma5_now > ma10_now:
        signal = "金叉"
    elif ma5_prev >= ma10_prev and ma5_now < ma10_now:
        signal = "死叉"
    else:
        signal = "无明显信号"

    result["trend"] = trend
    result["signal"] = signal
    return result


def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> dict:
    """计算MACD"""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = 2 * (dif - dea)

    dif_now, dea_now, macd_now = dif.iloc[-1], dea.iloc[-1], macd.iloc[-1]
    dif_prev, dea_prev = dif.iloc[-2], dea.iloc[-2]

    if dif_prev <= dea_prev and dif_now > dea_now:
        sig = "金叉"
    elif dif_prev >= dea_prev and dif_now < dea_now:
        sig = "死叉"
    else:
        sig = "金叉持续" if dif_now > dea_now else "死叉持续"

    return {
        "dif": round(dif_now, 2),
        "dea": round(dea_now, 2),
        "macd": round(macd_now, 2),
        "signal": sig
    }


def calc_rsi(df: pd.DataFrame) -> dict:
    """计算RSI"""
    result = {}
    for period in [6, 12, 24]:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        val = round(rsi.iloc[-1], 1)
        result[f"rsi{period}"] = val

    # 判断状态
    rsi6 = result["rsi6"]
    if rsi6 > 80:
        status = "超买"
    elif rsi6 < 20:
        status = "超卖"
    elif rsi6 > 60:
        status = "偏强"
    elif rsi6 < 40:
        status = "偏弱"
    else:
        status = "中性"

    result["status"] = status
    return result


def calc_kdj(df: pd.DataFrame, n=9, m1=3, m2=3) -> dict:
    """计算KDJ"""
    low_n = df["low"].rolling(n).min()
    high_n = df["high"].rolling(n).max()
    rsv = (df["close"] - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)

    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d

    k_now, d_now, j_now = k.iloc[-1], d.iloc[-1], j.iloc[-1]
    k_prev, d_prev = k.iloc[-2], d.iloc[-2]

    if k_prev <= d_prev and k_now > d_now:
        signal = "金叉"
    elif k_prev >= d_prev and k_now < d_now:
        signal = "死叉"
    elif k_now > 80 and d_now > 80:
        signal = "高位钝化"
    elif k_now < 20 and d_now < 20:
        signal = "低位钝化"
    else:
        signal = "运行中"

    return {
        "k": round(k_now, 1),
        "d": round(d_now, 1),
        "j": round(j_now, 1),
        "signal": signal
    }


def calc_bollinger(df: pd.DataFrame, period=20, std_dev=2) -> dict:
    """计算布林带"""
    middle = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std

    close = df["close"].iloc[-1]
    upper_val = round(upper.iloc[-1], 2)
    middle_val = round(middle.iloc[-1], 2)
    lower_val = round(lower.iloc[-1], 2)

    # 判断位置
    band_width = upper_val - lower_val
    if band_width > 0:
        pos_ratio = (close - lower_val) / band_width
        if pos_ratio > 0.8:
            position = "上轨附近"
        elif pos_ratio < 0.2:
            position = "下轨附近"
        else:
            position = "中轨附近"
    else:
        position = "收口"

    return {
        "upper": upper_val,
        "middle": middle_val,
        "lower": lower_val,
        "position": position
    }


def find_support_resistance(df: pd.DataFrame) -> dict:
    """简单识别支撑位和压力位（近期高低点）"""
    recent = df.tail(30)
    close = df["close"].iloc[-1]

    lows = recent["low"].nsmallest(5).unique()
    highs = recent["high"].nlargest(5).unique()

    support = sorted([round(v, 2) for v in lows if v < close], reverse=True)[:2]
    resistance = sorted([round(v, 2) for v in highs if v > close])[:2]

    return {"support": support, "resistance": resistance}


def get_stock_name(code: str) -> str:
    """获取股票名称（通过个股信息接口）"""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        row = df[df["item"] == "股票简称"]
        if not row.empty:
            return str(row.iloc[0]["value"])
    except Exception:
        pass
    return code


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请提供股票代码，如: python technical_analysis.py 600519"}, ensure_ascii=False))
        sys.exit(1)

    code = sys.argv[1]

    try:
        stock_name = get_stock_name(code)
        df = fetch_stock_data(code)

        latest = df.iloc[-1]
        prev_close = df.iloc[-2]["close"] if len(df) > 1 else latest["close"]
        change_pct = round((latest["close"] - prev_close) / prev_close * 100, 2)

        result = {
            "stock_code": code,
            "stock_name": stock_name,
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "price": {
                "latest": round(latest["close"], 2),
                "open": round(latest["open"], 2),
                "high": round(latest["high"], 2),
                "low": round(latest["low"], 2),
                "volume": round(latest["volume"], 0),
                "change_pct": change_pct
            },
            "ma": calc_ma(df),
            "macd": calc_macd(df),
            "rsi": calc_rsi(df),
            "kdj": calc_kdj(df),
            "bollinger": calc_bollinger(df),
            "levels": find_support_resistance(df)
        }

        def default_serializer(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        print(json.dumps(result, ensure_ascii=False, indent=2, default=default_serializer))

    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
