#!/usr/bin/env python3
"""A股深度技术分析脚本 - 多时间框架、K线形态、量价背离、斐波那契等"""

import sys
import json
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ============================================================
# 数据获取
# ============================================================

def fetch_stock_data(code: str, days: int = 250) -> pd.DataFrame:
    """拉取日K线数据（前复权），默认250个交易日（约1年）"""
    df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
    df = df.tail(days).reset_index(drop=True)
    df.columns = ["date", "stock_code", "open", "close", "high", "low", "volume", "turnover",
                   "amplitude", "change_pct", "change_amt", "turnover_rate"]
    for col in ["open", "close", "high", "low", "volume", "turnover", "turnover_rate"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_weekly_data(code: str, days: int = 120) -> pd.DataFrame:
    """拉取周K线数据"""
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="weekly", adjust="qfq")
        df = df.tail(days).reset_index(drop=True)
        df.columns = ["date", "stock_code", "open", "close", "high", "low", "volume", "turnover",
                       "amplitude", "change_pct", "change_amt", "turnover_rate"]
        for col in ["open", "close", "high", "low", "volume", "turnover"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return None


def get_stock_name(code: str) -> str:
    """获取股票名称"""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        row = df[df["item"] == "股票简称"]
        if not row.empty:
            return str(row.iloc[0]["value"])
    except Exception:
        pass
    return code


# ============================================================
# 趋势指标
# ============================================================

def calc_ma(df: pd.DataFrame) -> dict:
    """计算均线系统（含MA5/10/20/60/120/250）"""
    result = {}
    for period in [5, 10, 20, 60, 120, 250]:
        key = f"ma{period}"
        if len(df) < period:
            continue
        df[key] = df["close"].rolling(period).mean()
        val = df[key].iloc[-1]
        prev = df[key].iloc[-2] if len(df) > 1 else val
        result[key] = {
            "value": round(val, 2),
            "direction": "up" if val > prev else "down",
            "vs_price": round((df["close"].iloc[-1] / val - 1) * 100, 2)
        }

    # 判断排列
    available = [f"ma{p}" for p in [5, 10, 20, 60] if f"ma{p}" in result]
    ma_vals = [result[k]["value"] for k in available]
    if len(ma_vals) >= 4:
        if ma_vals == sorted(ma_vals, reverse=True):
            trend = "多头排列"
        elif ma_vals == sorted(ma_vals):
            trend = "空头排列"
        else:
            trend = "交叉排列"
    else:
        trend = "数据不足"

    # 金叉/死叉 (MA5 vs MA10)
    if "ma5" in df.columns and "ma10" in df.columns and len(df) > 1:
        ma5_prev, ma10_prev = df["ma5"].iloc[-2], df["ma10"].iloc[-2]
        ma5_now, ma10_now = df["ma5"].iloc[-1], df["ma10"].iloc[-1]
        if ma5_prev <= ma10_prev and ma5_now > ma10_now:
            signal = "金叉"
        elif ma5_prev >= ma10_prev and ma5_now < ma10_now:
            signal = "死叉"
        else:
            signal = "无明显信号"
    else:
        signal = "数据不足"

    # MA200 趋势（牛熊分界线）
    ma200_trend = None
    if "ma250" in result:
        close = df["close"].iloc[-1]
        ma250_val = result["ma250"]["value"]
        if close > ma250_val:
            ma200_trend = "价格在年线上方（偏多）"
        else:
            ma200_trend = "价格在年线下方（偏空）"

    result["trend"] = trend
    result["signal"] = signal
    result["ma200_trend"] = ma200_trend
    return result


def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> dict:
    """计算MACD（含背离检测）"""
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

    # MACD柱趋势（连续放大/缩小）
    recent_macd = macd.tail(5).tolist()
    if len(recent_macd) >= 3:
        diffs = [recent_macd[i] - recent_macd[i-1] for i in range(1, len(recent_macd))]
        if all(d > 0 for d in diffs):
            histogram_trend = "红柱放大" if recent_macd[-1] > 0 else "绿柱缩小"
        elif all(d < 0 for d in diffs):
            histogram_trend = "红柱缩小" if recent_macd[-1] > 0 else "绿柱放大"
        else:
            histogram_trend = "震荡"
    else:
        histogram_trend = "数据不足"

    # 背离检测
    divergence = detect_macd_divergence(df, dif)

    return {
        "dif": round(dif_now, 3),
        "dea": round(dea_now, 3),
        "macd": round(macd_now, 3),
        "signal": sig,
        "histogram_trend": histogram_trend,
        "divergence": divergence
    }


def detect_macd_divergence(df: pd.DataFrame, dif: pd.Series, lookback: int = 60) -> str:
    """检测MACD顶背离/底背离"""
    if len(df) < lookback:
        return "数据不足"

    recent_df = df.tail(lookback)
    recent_dif = dif.tail(lookback)

    # 找近期两个价格高点
    highs_idx = []
    prices = recent_df["high"].values
    dif_vals = recent_dif.values
    for i in range(2, len(prices) - 2):
        if prices[i] > prices[i-1] and prices[i] > prices[i-2] and prices[i] > prices[i+1] and prices[i] > prices[i+2]:
            highs_idx.append(i)

    # 找近期两个价格低点
    lows_idx = []
    low_prices = recent_df["low"].values
    for i in range(2, len(low_prices) - 2):
        if low_prices[i] < low_prices[i-1] and low_prices[i] < low_prices[i-2] and low_prices[i] < low_prices[i+1] and low_prices[i] < low_prices[i+2]:
            lows_idx.append(i)

    # 顶背离：价格新高但DIF未新高
    if len(highs_idx) >= 2:
        h1, h2 = highs_idx[-2], highs_idx[-1]
        if prices[h2] > prices[h1] and dif_vals[h2] < dif_vals[h1]:
            return "顶背离（价格新高但MACD未新高，看跌信号）"

    # 底背离：价格新低但DIF未新低
    if len(lows_idx) >= 2:
        l1, l2 = lows_idx[-2], lows_idx[-1]
        if low_prices[l2] < low_prices[l1] and dif_vals[l2] > dif_vals[l1]:
            return "底背离（价格新低但MACD未新低，看涨信号）"

    return "无背离"


# ============================================================
# 动量指标
# ============================================================

def calc_rsi(df: pd.DataFrame) -> dict:
    """计算RSI（含背离检测）"""
    result = {}
    for period in [6, 12, 24]:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        val = round(rsi.iloc[-1], 1)
        result[f"rsi{period}"] = val

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

    # RSI趋势（近5日方向）
    rsi_series = 100 - (100 / (1 + (df["close"].diff().where(lambda x: x > 0, 0).rolling(6).mean() /
                                     (-df["close"].diff().where(lambda x: x < 0, 0)).rolling(6).mean().replace(0, np.nan))))
    recent_rsi = rsi_series.tail(5).dropna().tolist()
    if len(recent_rsi) >= 3:
        if recent_rsi[-1] > recent_rsi[0]:
            rsi_trend = "上升"
        elif recent_rsi[-1] < recent_rsi[0]:
            rsi_trend = "下降"
        else:
            rsi_trend = "横盘"
    else:
        rsi_trend = "数据不足"

    result["status"] = status
    result["trend"] = rsi_trend
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

    # J值极端判断
    j_status = None
    if j_now > 100:
        j_status = "J值超买（>100），短期回调风险"
    elif j_now < 0:
        j_status = "J值超卖（<0），短期反弹机会"

    return {
        "k": round(k_now, 1),
        "d": round(d_now, 1),
        "j": round(j_now, 1),
        "signal": signal,
        "j_status": j_status
    }


def calc_cci(df: pd.DataFrame, period: int = 14) -> dict:
    """计算CCI（顺势指标）"""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma_tp = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - ma_tp) / (0.015 * md)

    val = round(cci.iloc[-1], 1)
    if val > 200:
        status = "极度超买"
    elif val > 100:
        status = "超买区间"
    elif val < -200:
        status = "极度超卖"
    elif val < -100:
        status = "超卖区间"
    else:
        status = "正常区间"

    return {"value": val, "status": status}


# ============================================================
# 波动率指标
# ============================================================

def calc_bollinger(df: pd.DataFrame, period=20, std_dev=2) -> dict:
    """计算布林带（含带宽和%B）"""
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
        if pos_ratio > 0.8:
            position = "上轨附近"
        elif pos_ratio < 0.2:
            position = "下轨附近"
        else:
            position = "中轨附近"
    else:
        position = "收口"

    # 带宽百分比（衡量波动率）
    bandwidth_pct = round(band_width / middle_val * 100, 2) if middle_val > 0 else 0
    # %B 指标
    pct_b = round(pos_ratio * 100, 1) if band_width > 0 else 50

    # 布林带收口/张口判断
    bw_series = ((upper - lower) / middle * 100).tail(20)
    if len(bw_series.dropna()) >= 10:
        bw_recent = bw_series.iloc[-1]
        bw_avg = bw_series.mean()
        if bw_recent < bw_avg * 0.7:
            squeeze = "收口（波动率低，可能即将突破）"
        elif bw_recent > bw_avg * 1.3:
            squeeze = "张口（波动率高，趋势进行中）"
        else:
            squeeze = "正常"
    else:
        squeeze = "数据不足"

    return {
        "upper": upper_val,
        "middle": middle_val,
        "lower": lower_val,
        "position": position,
        "bandwidth_pct": bandwidth_pct,
        "pct_b": pct_b,
        "squeeze": squeeze
    }


def calc_atr(df: pd.DataFrame, period: int = 14) -> dict:
    """计算ATR（真实波幅均值）"""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    atr_val = round(atr.iloc[-1], 2)
    close = df["close"].iloc[-1]
    atr_pct = round(atr_val / close * 100, 2)

    # ATR趋势
    atr_prev = atr.iloc[-6] if len(atr) > 5 else atr.iloc[0]
    if atr.iloc[-1] > atr_prev * 1.1:
        atr_trend = "波动率上升"
    elif atr.iloc[-1] < atr_prev * 0.9:
        atr_trend = "波动率下降"
    else:
        atr_trend = "波动率平稳"

    return {
        "atr": atr_val,
        "atr_pct": atr_pct,
        "trend": atr_trend,
        "stop_loss_ref": round(close - 2 * atr_val, 2)
    }


# ============================================================
# 成交量指标
# ============================================================

def calc_obv(df: pd.DataFrame) -> dict:
    """计算OBV（能量潮）"""
    obv = [0]
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i-1]:
            obv.append(obv[-1] + df["volume"].iloc[i])
        elif df["close"].iloc[i] < df["close"].iloc[i-1]:
            obv.append(obv[-1] - df["volume"].iloc[i])
        else:
            obv.append(obv[-1])

    obv_series = pd.Series(obv, index=df.index)
    obv_ma5 = obv_series.rolling(5).mean()

    # OBV趋势
    obv_recent = obv_series.tail(10)
    if obv_recent.iloc[-1] > obv_recent.iloc[0]:
        obv_trend = "上升（资金流入）"
    elif obv_recent.iloc[-1] < obv_recent.iloc[0]:
        obv_trend = "下降（资金流出）"
    else:
        obv_trend = "横盘"

    # 量价背离检测
    price_up = df["close"].iloc[-1] > df["close"].iloc[-10] if len(df) >= 10 else None
    obv_up = obv_series.iloc[-1] > obv_series.iloc[-10] if len(obv_series) >= 10 else None
    if price_up is not None and obv_up is not None:
        if price_up and not obv_up:
            divergence = "量价顶背离（价涨量缩，上涨动力不足）"
        elif not price_up and obv_up:
            divergence = "量价底背离（价跌量增，可能筑底）"
        else:
            divergence = "量价同步"
    else:
        divergence = "数据不足"

    return {
        "value": round(obv_series.iloc[-1], 0),
        "trend": obv_trend,
        "divergence": divergence
    }


def calc_volume_analysis(df: pd.DataFrame) -> dict:
    """成交量深度分析"""
    vol = df["volume"]
    vol_ma5 = vol.rolling(5).mean()
    vol_ma20 = vol.rolling(20).mean()

    latest_vol = vol.iloc[-1]
    ma5_val = vol_ma5.iloc[-1]
    ma20_val = vol_ma20.iloc[-1]

    # 量比
    vol_ratio = round(latest_vol / ma5_val, 2) if ma5_val > 0 else 0

    # 放量/缩量判断
    if vol_ratio > 2:
        vol_status = "显著放量"
    elif vol_ratio > 1.5:
        vol_status = "温和放量"
    elif vol_ratio < 0.5:
        vol_status = "显著缩量"
    elif vol_ratio < 0.8:
        vol_status = "温和缩量"
    else:
        vol_status = "正常"

    # 近5日量能趋势
    recent_vol = vol.tail(5).tolist()
    if len(recent_vol) >= 3:
        if all(recent_vol[i] >= recent_vol[i-1] for i in range(1, len(recent_vol))):
            vol_trend = "连续放量"
        elif all(recent_vol[i] <= recent_vol[i-1] for i in range(1, len(recent_vol))):
            vol_trend = "连续缩量"
        else:
            vol_trend = "量能不规则"
    else:
        vol_trend = "数据不足"

    # 换手率分析
    turnover = df["turnover_rate"].iloc[-1] if "turnover_rate" in df.columns else None
    turnover_status = None
    if turnover is not None:
        if turnover > 10:
            turnover_status = "高换手（>10%，交投活跃）"
        elif turnover > 5:
            turnover_status = "较高换手（5-10%）"
        elif turnover < 1:
            turnover_status = "低换手（<1%，交投清淡）"
        else:
            turnover_status = "正常换手"

    return {
        "latest_volume": round(latest_vol, 0),
        "vol_ma5": round(ma5_val, 0),
        "vol_ma20": round(ma20_val, 0),
        "vol_ratio": vol_ratio,
        "vol_status": vol_status,
        "vol_trend": vol_trend,
        "turnover_rate": round(turnover, 2) if turnover else None,
        "turnover_status": turnover_status
    }


# ============================================================
# K线形态识别
# ============================================================

def detect_candlestick_patterns(df: pd.DataFrame) -> list:
    """识别近期K线形态"""
    patterns = []
    if len(df) < 5:
        return patterns

    # 取最近5根K线
    recent = df.tail(5)
    idx = recent.index

    for i in range(len(recent)):
        row = recent.iloc[i]
        o, c, h, l = row["open"], row["close"], row["high"], row["low"]
        body = abs(c - o)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        total_range = h - l
        if total_range == 0:
            continue

        # 锤子线 / 上吊线
        if lower_shadow > body * 2 and upper_shadow < body * 0.5 and body > 0:
            if i >= 2:
                prev_trend = recent.iloc[i-1]["close"] < recent.iloc[i-2]["close"]
                if prev_trend:
                    patterns.append({"name": "锤子线", "type": "看涨反转", "position": str(row["date"])[:10], "reliability": "中"})
                else:
                    patterns.append({"name": "上吊线", "type": "看跌反转", "position": str(row["date"])[:10], "reliability": "中"})

        # 十字星
        if body < total_range * 0.1 and total_range > 0:
            patterns.append({"name": "十字星", "type": "变盘信号", "position": str(row["date"])[:10], "reliability": "中"})

        # 大阳线 / 大阴线
        if body > total_range * 0.7:
            if c > o:
                patterns.append({"name": "大阳线", "type": "强势", "position": str(row["date"])[:10], "reliability": "高"})
            else:
                patterns.append({"name": "大阴线", "type": "弱势", "position": str(row["date"])[:10], "reliability": "高"})

    # 组合形态（需要至少3根K线）
    if len(recent) >= 3:
        # 看涨吞没
        for i in range(1, len(recent)):
            prev = recent.iloc[i-1]
            curr = recent.iloc[i]
            if prev["close"] < prev["open"] and curr["close"] > curr["open"]:
                if curr["close"] > prev["open"] and curr["open"] < prev["close"]:
                    patterns.append({"name": "看涨吞没", "type": "看涨反转", "position": str(curr["date"])[:10], "reliability": "高"})

        # 看跌吞没
        for i in range(1, len(recent)):
            prev = recent.iloc[i-1]
            curr = recent.iloc[i]
            if prev["close"] > prev["open"] and curr["close"] < curr["open"]:
                if curr["open"] > prev["close"] and curr["close"] < prev["open"]:
                    patterns.append({"name": "看跌吞没", "type": "看跌反转", "position": str(curr["date"])[:10], "reliability": "高"})

        # 晨星（三K线看涨反转）
        if len(recent) >= 3:
            for i in range(2, len(recent)):
                k1, k2, k3 = recent.iloc[i-2], recent.iloc[i-1], recent.iloc[i]
                k1_bear = k1["close"] < k1["open"]
                k2_small = abs(k2["close"] - k2["open"]) < abs(k1["close"] - k1["open"]) * 0.3
                k3_bull = k3["close"] > k3["open"] and k3["close"] > (k1["open"] + k1["close"]) / 2
                if k1_bear and k2_small and k3_bull:
                    patterns.append({"name": "晨星", "type": "看涨反转", "position": str(k3["date"])[:10], "reliability": "高"})

        # 黄昏星（三K线看跌反转）
        if len(recent) >= 3:
            for i in range(2, len(recent)):
                k1, k2, k3 = recent.iloc[i-2], recent.iloc[i-1], recent.iloc[i]
                k1_bull = k1["close"] > k1["open"]
                k2_small = abs(k2["close"] - k2["open"]) < abs(k1["close"] - k1["open"]) * 0.3
                k3_bear = k3["close"] < k3["open"] and k3["close"] < (k1["open"] + k1["close"]) / 2
                if k1_bull and k2_small and k3_bear:
                    patterns.append({"name": "黄昏星", "type": "看跌反转", "position": str(k3["date"])[:10], "reliability": "高"})

    return patterns


# ============================================================
# 支撑阻力 & 斐波那契
# ============================================================

def find_support_resistance(df: pd.DataFrame) -> dict:
    """多维度支撑阻力位识别"""
    close = df["close"].iloc[-1]
    recent = df.tail(60)

    lows = recent["low"].nsmallest(8).unique()
    highs = recent["high"].nlargest(8).unique()
    support_points = sorted([round(v, 2) for v in lows if v < close], reverse=True)[:3]
    resistance_points = sorted([round(v, 2) for v in highs if v > close])[:3]

    # 均线支撑阻力
    ma_levels = {}
    for period in [20, 60, 120, 250]:
        key = f"ma{period}"
        if key in df.columns:
            ma_val = round(df[key].iloc[-1], 2)
            if not np.isnan(ma_val):
                ma_levels[f"MA{period}"] = ma_val

    return {
        "support": support_points,
        "resistance": resistance_points,
        "ma_levels": ma_levels
    }


def calc_fibonacci(df: pd.DataFrame) -> dict:
    """计算斐波那契回撤位"""
    recent = df.tail(120)
    high_idx = recent["high"].idxmax()
    low_idx = recent["low"].idxmin()
    high_val = recent["high"].max()
    low_val = recent["low"].min()
    close = df["close"].iloc[-1]
    diff = high_val - low_val

    if diff == 0:
        return {"status": "价格无波动"}

    if high_idx > low_idx:
        direction = "上涨回撤"
        levels = {
            "fib_0": round(high_val, 2),
            "fib_236": round(high_val - diff * 0.236, 2),
            "fib_382": round(high_val - diff * 0.382, 2),
            "fib_500": round(high_val - diff * 0.5, 2),
            "fib_618": round(high_val - diff * 0.618, 2),
            "fib_786": round(high_val - diff * 0.786, 2),
            "fib_1000": round(low_val, 2),
        }
    else:
        direction = "下跌反弹"
        levels = {
            "fib_0": round(low_val, 2),
            "fib_236": round(low_val + diff * 0.236, 2),
            "fib_382": round(low_val + diff * 0.382, 2),
            "fib_500": round(low_val + diff * 0.5, 2),
            "fib_618": round(low_val + diff * 0.618, 2),
            "fib_786": round(low_val + diff * 0.786, 2),
            "fib_1000": round(high_val, 2),
        }

    # 判断当前价格所在区间
    fib_values = sorted(levels.values())
    current_zone = "区间外"
    for i in range(len(fib_values) - 1):
        if fib_values[i] <= close <= fib_values[i + 1]:
            current_zone = f"{fib_values[i]}-{fib_values[i+1]}"
            break

    return {
        "direction": direction,
        "high": round(high_val, 2),
        "low": round(low_val, 2),
        "levels": levels,
        "current_zone": current_zone
    }


# ============================================================
# 多时间框架分析
# ============================================================

def analyze_weekly(df_weekly: pd.DataFrame) -> dict:
    """周线级别趋势分析"""
    if df_weekly is None or len(df_weekly) < 20:
        return {"status": "周线数据不足"}

    close = df_weekly["close"].iloc[-1]
    ma5 = df_weekly["close"].rolling(5).mean().iloc[-1]
    ma10 = df_weekly["close"].rolling(10).mean().iloc[-1]
    ma20 = df_weekly["close"].rolling(20).mean().iloc[-1]

    if ma5 > ma10 > ma20:
        weekly_trend = "周线多头排列"
    elif ma5 < ma10 < ma20:
        weekly_trend = "周线空头排列"
    else:
        weekly_trend = "周线交叉整理"

    # 周线MACD
    ema12 = df_weekly["close"].ewm(span=12, adjust=False).mean()
    ema26 = df_weekly["close"].ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()

    if dif.iloc[-1] > dea.iloc[-1]:
        weekly_macd = "周线MACD金叉" if dif.iloc[-2] <= dea.iloc[-2] else "周线MACD多头"
    else:
        weekly_macd = "周线MACD死叉" if dif.iloc[-2] >= dea.iloc[-2] else "周线MACD空头"

    # 周线RSI
    delta = df_weekly["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(6).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(6).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).iloc[-1]

    return {
        "trend": weekly_trend,
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "macd_signal": weekly_macd,
        "rsi6": round(rsi, 1),
        "close": round(close, 2)
    }


# ============================================================
# 综合信号评估
# ============================================================

def calc_signal_summary(ma_data, macd_data, rsi_data, kdj_data, boll_data, obv_data, vol_data, patterns) -> dict:
    """多指标交叉验证，生成综合信号"""
    bullish = 0
    bearish = 0
    signals = []

    # 均线
    if ma_data.get("trend") == "多头排列":
        bullish += 2; signals.append("均线多头排列(+2)")
    elif ma_data.get("trend") == "空头排列":
        bearish += 2; signals.append("均线空头排列(-2)")
    if ma_data.get("signal") == "金叉":
        bullish += 1; signals.append("均线金叉(+1)")
    elif ma_data.get("signal") == "死叉":
        bearish += 1; signals.append("均线死叉(-1)")
    if ma_data.get("ma200_trend") and "上方" in ma_data["ma200_trend"]:
        bullish += 1; signals.append("年线上方(+1)")
    elif ma_data.get("ma200_trend") and "下方" in ma_data["ma200_trend"]:
        bearish += 1; signals.append("年线下方(-1)")

    # MACD
    if "金叉" in macd_data.get("signal", ""):
        bullish += 1; signals.append("MACD金叉(+1)")
    elif "死叉" in macd_data.get("signal", ""):
        bearish += 1; signals.append("MACD死叉(-1)")
    if "底背离" in macd_data.get("divergence", ""):
        bullish += 2; signals.append("MACD底背离(+2)")
    elif "顶背离" in macd_data.get("divergence", ""):
        bearish += 2; signals.append("MACD顶背离(-2)")

    # RSI
    if rsi_data.get("status") == "超买":
        bearish += 1; signals.append("RSI超买(-1)")
    elif rsi_data.get("status") == "超卖":
        bullish += 1; signals.append("RSI超卖(+1)")

    # KDJ
    if kdj_data.get("signal") == "金叉":
        bullish += 1; signals.append("KDJ金叉(+1)")
    elif kdj_data.get("signal") == "死叉":
        bearish += 1; signals.append("KDJ死叉(-1)")
    elif kdj_data.get("signal") == "低位钝化":
        bullish += 1; signals.append("KDJ低位钝化(+1)")
    elif kdj_data.get("signal") == "高位钝化":
        bearish += 1; signals.append("KDJ高位钝化(-1)")

    # 布林带
    if boll_data.get("position") == "下轨附近":
        bullish += 1; signals.append("布林带下轨(+1)")
    elif boll_data.get("position") == "上轨附近":
        bearish += 1; signals.append("布林带上轨(-1)")

    # OBV
    if "流入" in obv_data.get("trend", ""):
        bullish += 1; signals.append("OBV资金流入(+1)")
    elif "流出" in obv_data.get("trend", ""):
        bearish += 1; signals.append("OBV资金流出(-1)")
    if "底背离" in obv_data.get("divergence", ""):
        bullish += 1; signals.append("量价底背离(+1)")
    elif "顶背离" in obv_data.get("divergence", ""):
        bearish += 1; signals.append("量价顶背离(-1)")

    # 成交量
    if vol_data.get("vol_status") == "显著放量":
        signals.append("显著放量(趋势确认)")

    # K线形态
    for p in patterns:
        if "看涨" in p.get("type", ""):
            bullish += 1; signals.append(f"{p['name']}(+1)")
        elif "看跌" in p.get("type", ""):
            bearish += 1; signals.append(f"{p['name']}(-1)")

    total = bullish + bearish
    if total == 0:
        score = 50
    else:
        score = round(bullish / total * 100)

    if score >= 70:
        verdict = "强烈看多"
    elif score >= 55:
        verdict = "偏多"
    elif score <= 30:
        verdict = "强烈看空"
    elif score <= 45:
        verdict = "偏空"
    else:
        verdict = "中性震荡"

    confidence = "高" if total >= 8 else ("中" if total >= 4 else "低")

    return {
        "bullish_count": bullish,
        "bearish_count": bearish,
        "score": score,
        "verdict": verdict,
        "confidence": confidence,
        "signals": signals
    }


# ============================================================
# 主函数
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请提供股票代码，如: python technical_analysis.py 600519"}, ensure_ascii=False))
        sys.exit(1)

    code = sys.argv[1]

    def default_serializer(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    try:
        stock_name = get_stock_name(code)
        df = fetch_stock_data(code, days=250)
        df_weekly = fetch_weekly_data(code, days=120)

        latest = df.iloc[-1]
        prev_close = df.iloc[-2]["close"] if len(df) > 1 else latest["close"]
        change_pct = round((latest["close"] - prev_close) / prev_close * 100, 2)

        # 计算所有指标
        ma_data = calc_ma(df)
        macd_data = calc_macd(df)
        rsi_data = calc_rsi(df)
        kdj_data = calc_kdj(df)
        cci_data = calc_cci(df)
        boll_data = calc_bollinger(df)
        atr_data = calc_atr(df)
        obv_data = calc_obv(df)
        vol_data = calc_volume_analysis(df)
        patterns = detect_candlestick_patterns(df)
        levels = find_support_resistance(df)
        fib_data = calc_fibonacci(df)
        weekly_data = analyze_weekly(df_weekly)
        summary = calc_signal_summary(ma_data, macd_data, rsi_data, kdj_data, boll_data, obv_data, vol_data, patterns)

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
                "change_pct": change_pct,
                "turnover_rate": round(latest["turnover_rate"], 2) if "turnover_rate" in df.columns else None
            },
            "ma": ma_data,
            "macd": macd_data,
            "rsi": rsi_data,
            "kdj": kdj_data,
            "cci": cci_data,
            "bollinger": boll_data,
            "atr": atr_data,
            "obv": obv_data,
            "volume_analysis": vol_data,
            "candlestick_patterns": patterns,
            "levels": levels,
            "fibonacci": fib_data,
            "weekly": weekly_data,
            "signal_summary": summary
        }

        print(json.dumps(result, ensure_ascii=False, indent=2, default=default_serializer))

    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
