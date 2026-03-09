#!/usr/bin/env python3
"""股票分析共享工具库 - 封装 akshare API + 技术指标计算，供三个子 agent 共用"""

import json
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime


# ============================================================
# 通用工具
# ============================================================

def to_json(obj):
    """JSON 序列化，自动处理 numpy/pandas 类型"""
    def _default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, pd.Timestamp):
            return str(o)
        if isinstance(o, pd.DataFrame):
            return o.to_dict(orient="records")
        if isinstance(o, pd.Series):
            return o.tolist()
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")
    return json.dumps(obj, ensure_ascii=False, indent=2, default=_default)


def safe_call(func, *args, default=None, **kwargs):
    """安全调用 wrapper，API 失败返回 default"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return default if default is not None else {"error": str(e)}


# ============================================================
# 行情数据
# ============================================================

def fetch_stock_name(code: str) -> str:
    """获取股票名称"""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        row = df[df["item"] == "股票简称"]
        if not row.empty:
            return str(row.iloc[0]["value"])
    except Exception:
        pass
    return code


def fetch_daily_kline(code: str, days: int = 120) -> pd.DataFrame:
    """拉取日K线数据（前复权）"""
    df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    df = df.tail(days).reset_index(drop=True)
    df.columns = ["date", "stock_code", "open", "close", "high", "low", "volume", "turnover",
                   "amplitude", "change_pct", "change_amt", "turnover_rate"]
    for col in ["open", "close", "high", "low", "volume", "turnover"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def fetch_weekly_kline(code: str, days: int = 120) -> pd.DataFrame:
    """拉取周K线数据（前复权）"""
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="weekly", adjust="qfq")
        df = df.tail(days).reset_index(drop=True)
        df.columns = ["date", "stock_code", "open", "close", "high", "low", "volume", "turnover",
                       "amplitude", "change_pct", "change_amt", "turnover_rate"]
        for col in ["open", "close", "high", "low", "volume", "turnover"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as e:
        return None


# ============================================================
# 技术指标计算（从 technical_analysis.py 提取）
# ============================================================

def get_latest_price(df: pd.DataFrame) -> dict:
    """获取最新价格信息"""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    change_pct = round((latest["close"] - prev["close"]) / prev["close"] * 100, 2) if prev["close"] != 0 else 0
    return {
        "latest": round(latest["close"], 2),
        "open": round(latest["open"], 2),
        "high": round(latest["high"], 2),
        "low": round(latest["low"], 2),
        "volume": round(latest["volume"], 0),
        "change_pct": change_pct
    }


def calc_ma(df: pd.DataFrame) -> dict:
    """计算均线 MA5/10/20/60"""
    result = {}
    for period in [5, 10, 20, 60]:
        key = f"ma{period}"
        df[key] = df["close"].rolling(period).mean()
        val = df[key].iloc[-1]
        prev = df[key].iloc[-2] if len(df) > 1 else val
        result[key] = {"value": round(val, 2), "direction": "↑" if val > prev else "↓"}

    ma_vals = [result[f"ma{p}"]["value"] for p in [5, 10, 20, 60]]
    if ma_vals == sorted(ma_vals, reverse=True):
        trend = "多头排列"
    elif ma_vals == sorted(ma_vals):
        trend = "空头排列"
    else:
        trend = "交叉排列"

    ma5_prev, ma10_prev = df["ma5"].iloc[-2], df["ma10"].iloc[-2]
    ma5_now, ma10_now = df["ma5"].iloc[-1], df["ma10"].iloc[-1]
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
    """计算 MACD"""
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

    return {"dif": round(dif_now, 2), "dea": round(dea_now, 2), "macd": round(macd_now, 2), "signal": sig}


def calc_rsi(df: pd.DataFrame) -> dict:
    """计算 RSI6/12/24"""
    result = {}
    for period in [6, 12, 24]:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        result[f"rsi{period}"] = round(rsi.iloc[-1], 1)

    rsi6 = result["rsi6"]
    if rsi6 > 80: status = "超买"
    elif rsi6 < 20: status = "超卖"
    elif rsi6 > 60: status = "偏强"
    elif rsi6 < 40: status = "偏弱"
    else: status = "中性"
    result["status"] = status
    return result


def calc_kdj(df: pd.DataFrame, n=9, m1=3, m2=3) -> dict:
    """计算 KDJ"""
    low_n = df["low"].rolling(n).min()
    high_n = df["high"].rolling(n).max()
    rsv = (df["close"] - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)

    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d

    k_now, d_now, j_now = k.iloc[-1], d.iloc[-1], j.iloc[-1]
    k_prev, d_prev = k.iloc[-2], d.iloc[-2]

    if k_prev <= d_prev and k_now > d_now: signal = "金叉"
    elif k_prev >= d_prev and k_now < d_now: signal = "死叉"
    elif k_now > 80 and d_now > 80: signal = "高位钝化"
    elif k_now < 20 and d_now < 20: signal = "低位钝化"
    else: signal = "运行中"

    return {"k": round(k_now, 1), "d": round(d_now, 1), "j": round(j_now, 1), "signal": signal}


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

    band_width = upper_val - lower_val
    if band_width > 0:
        pos_ratio = (close - lower_val) / band_width
        if pos_ratio > 0.8: position = "上轨附近"
        elif pos_ratio < 0.2: position = "下轨附近"
        else: position = "中轨附近"
    else:
        position = "收口"

    return {"upper": upper_val, "middle": middle_val, "lower": lower_val, "position": position}


def find_support_resistance(df: pd.DataFrame) -> dict:
    """识别支撑位和压力位（近期高低点）"""
    recent = df.tail(30)
    close = df["close"].iloc[-1]
    lows = recent["low"].nsmallest(5).unique()
    highs = recent["high"].nlargest(5).unique()
    support = sorted([round(v, 2) for v in lows if v < close], reverse=True)[:2]
    resistance = sorted([round(v, 2) for v in highs if v > close])[:2]
    return {"support": support, "resistance": resistance}


# ============================================================
# 基本面数据
# ============================================================

def fetch_financial_summary(code: str) -> dict:
    """获取最新财务摘要（利润表+资产负债表关键指标）"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            return {"error": "无财务数据"}
        latest = df.iloc[0]
        return {col: latest[col] for col in df.columns}
    except Exception as e:
        return {"error": str(e)}


def fetch_financial_history(code: str, n: int = 8) -> list:
    """获取近N期财务摘要（用于趋势分析）"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            return []
        df = df.head(n)
        return df.to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


def fetch_valuation(code: str) -> dict:
    """获取估值数据（PE/PB/市值等）"""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        result = {}
        for _, row in df.iterrows():
            result[row["item"]] = row["value"]
        return result
    except Exception as e:
        return {"error": str(e)}


def fetch_top10_holders(code: str) -> list:
    """获取十大股东"""
    try:
        df = ak.stock_main_stock_holder(stock=code)
        if df is None or df.empty:
            return []
        return df.head(10).to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


def fetch_profit_forecast(code: str) -> list:
    """获取机构盈利预测"""
    try:
        df = ak.stock_profit_forecast_ths(symbol=code, indicator="预测年报每股收益")
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


# ============================================================
# 资金与情绪
# ============================================================

def fetch_fund_flow(code: str, days: int = 10) -> list:
    """获取个股资金流向（主力/散户/超大单）"""
    try:
        df = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
        if df is None or df.empty:
            return []
        return df.tail(days).to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


def fetch_north_flow_daily(days: int = 20) -> list:
    """获取北向资金每日净流入"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df is None or df.empty:
            return []
        return df.tail(days).to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


def fetch_sector_fund_flow() -> list:
    """获取板块资金流向"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
        if df is None or df.empty:
            return []
        return df.head(20).to_dict(orient="records")
    except Exception as e:
        return [{"error": str(e)}]


def fetch_stock_comments(code: str) -> dict:
    """获取千股千评（综合评分）"""
    try:
        df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=code)
        if df is None or df.empty:
            return {"error": "无千股千评数据"}
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}
