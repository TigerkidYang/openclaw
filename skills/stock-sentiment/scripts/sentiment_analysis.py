#!/usr/bin/env python3
"""A股深度市场情绪分析脚本 - 资金流向、融资融券、趋势分析、情绪评分"""

import sys
import json
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime


def default_serializer(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    if pd.isna(obj):
        return None
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return {"error": str(e)}


def safe_float(val):
    try:
        v = float(val)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def get_stock_name(code):
    """获取股票名称"""
    df = ak.stock_individual_info_em(symbol=code)
    row = df[df["item"] == "股票简称"]
    if not row.empty:
        return str(row.iloc[0]["value"])
    return code


def get_market(code):
    if code.startswith("6"):
        return "sh"
    return "sz"


# ============================================================
# 资金流向
# ============================================================

def get_fund_flow(code, days=10):
    """获取个股资金流向（近N日）"""
    market = get_market(code)
    df = ak.stock_individual_fund_flow(stock=code, market=market)
    df = df.tail(days)
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row.get("日期", "")),
            "main_net_inflow": safe_float(row.get("主力净流入-净额")),
            "main_net_pct": safe_float(row.get("主力净流入-净占比")),
            "retail_net_inflow": safe_float(row.get("小单净流入-净额")),
            "super_large_net": safe_float(row.get("超大单净流入-净额")),
            "large_net": safe_float(row.get("大单净流入-净额")),
            "medium_net": safe_float(row.get("中单净流入-净额")),
        })
    return records


def analyze_fund_flow(fund_data):
    """分析资金流向趋势"""
    if not isinstance(fund_data, list) or len(fund_data) < 3:
        return {"status": "数据不足"}

    # 主力资金统计
    main_flows = [r["main_net_inflow"] for r in fund_data if r.get("main_net_inflow") is not None]
    retail_flows = [r["retail_net_inflow"] for r in fund_data if r.get("retail_net_inflow") is not None]

    result = {}

    if main_flows:
        result["main_total_5d"] = round(sum(main_flows[:5]), 2) if len(main_flows) >= 5 else round(sum(main_flows), 2)
        result["main_total_10d"] = round(sum(main_flows), 2)

        # 主力连续流入/流出天数
        consecutive = 0
        direction = None
        for f in main_flows:
            if consecutive == 0:
                direction = "in" if f > 0 else "out"
                consecutive = 1
            elif (direction == "in" and f > 0) or (direction == "out" and f < 0):
                consecutive += 1
            else:
                break
        result["main_consecutive_days"] = consecutive
        result["main_consecutive_direction"] = "连续流入" if direction == "in" else "连续流出"

        # 主力趋势（近3日 vs 前3日）
        if len(main_flows) >= 6:
            recent_3 = sum(main_flows[:3])
            prev_3 = sum(main_flows[3:6])
            if recent_3 > 0 and prev_3 > 0 and recent_3 > prev_3:
                result["main_trend"] = "流入加速"
            elif recent_3 > 0 and prev_3 > 0 and recent_3 < prev_3:
                result["main_trend"] = "流入减速"
            elif recent_3 < 0 and prev_3 < 0 and recent_3 < prev_3:
                result["main_trend"] = "流出加速"
            elif recent_3 < 0 and prev_3 < 0 and recent_3 > prev_3:
                result["main_trend"] = "流出减速"
            elif recent_3 > 0 and prev_3 < 0:
                result["main_trend"] = "由流出转流入"
            elif recent_3 < 0 and prev_3 > 0:
                result["main_trend"] = "由流入转流出"
            else:
                result["main_trend"] = "震荡"

        # 超大单占比（机构行为）
        super_large = [r["super_large_net"] for r in fund_data if r.get("super_large_net") is not None]
        if super_large and main_flows:
            total_main = sum(abs(f) for f in main_flows) or 1
            total_super = sum(super_large)
            result["super_large_total"] = round(total_super, 2)
            result["super_large_dominance"] = "超大单主导" if abs(total_super) > abs(sum(main_flows)) * 0.5 else "大单主导"

    if retail_flows:
        result["retail_total_5d"] = round(sum(retail_flows[:5]), 2) if len(retail_flows) >= 5 else round(sum(retail_flows), 2)
        # 主力散户博弈
        if main_flows and retail_flows:
            main_dir = sum(main_flows[:5]) if len(main_flows) >= 5 else sum(main_flows)
            retail_dir = sum(retail_flows[:5]) if len(retail_flows) >= 5 else sum(retail_flows)
            if main_dir > 0 and retail_dir < 0:
                result["battle"] = "主力吸筹散户出逃"
            elif main_dir < 0 and retail_dir > 0:
                result["battle"] = "主力出货散户接盘"
            elif main_dir > 0 and retail_dir > 0:
                result["battle"] = "多方共识（主力散户同向流入）"
            else:
                result["battle"] = "空方共识（主力散户同向流出）"

    return result


# ============================================================
# 北向资金
# ============================================================

def get_north_flow(days=20):
    """获取北向资金每日流向"""
    df = ak.stock_hsgt_fund_flow_summary_em()
    df = df.tail(days)
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row.get("日期", row.get("trade_date", ""))),
            "north_net": safe_float(row.get("北向资金", row.get("north_money", None))),
        })
    return records


def analyze_north_flow(north_data):
    """分析北向资金趋势"""
    if not isinstance(north_data, list) or len(north_data) < 5:
        return {"status": "数据不足"}

    flows = [r["north_net"] for r in north_data if r.get("north_net") is not None]
    if len(flows) < 5:
        return {"status": "数据不足"}

    result = {}
    result["total_5d"] = round(sum(flows[:5]), 2)
    result["total_10d"] = round(sum(flows[:10]), 2) if len(flows) >= 10 else round(sum(flows), 2)
    result["total_20d"] = round(sum(flows), 2)

    # 趋势判断
    positive_days = sum(1 for f in flows[:10] if f > 0)
    if positive_days >= 7:
        result["trend"] = "持续流入（10日中{}日净流入）".format(positive_days)
    elif positive_days <= 3:
        result["trend"] = "持续流出（10日中{}日净流出）".format(10 - positive_days)
    else:
        result["trend"] = "震荡（10日中{}日净流入）".format(positive_days)

    # 近期加速/减速
    if len(flows) >= 10:
        recent_5 = sum(flows[:5])
        prev_5 = sum(flows[5:10])
        if recent_5 > 0 and prev_5 > 0 and recent_5 > prev_5:
            result["momentum"] = "流入加速"
        elif recent_5 > 0 and prev_5 > 0 and recent_5 < prev_5:
            result["momentum"] = "流入减速"
        elif recent_5 < 0 and prev_5 > 0:
            result["momentum"] = "由流入转流出"
        elif recent_5 > 0 and prev_5 < 0:
            result["momentum"] = "由流出转流入"
        elif recent_5 < 0 and prev_5 < 0:
            result["momentum"] = "持续流出"
        else:
            result["momentum"] = "震荡"

    return result


# ============================================================
# 融资融券
# ============================================================

def get_margin_data(code):
    """获取融资融券数据"""
    try:
        df = ak.stock_margin_detail_sse(code=code)
        if df is None or df.empty:
            df = ak.stock_margin_detail_szse(code=code)
        if df is None or df.empty:
            return {"error": "未获取到融资融券数据"}

        df = df.tail(20)
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row.get("日期", row.get("信用交易日期", ""))),
                "margin_buy": safe_float(row.get("融资买入额", row.get("融资买入额(元)", None))),
                "margin_balance": safe_float(row.get("融资余额", row.get("融资余额(元)", None))),
                "short_sell": safe_float(row.get("融券卖出量", row.get("融券卖出量(股)", None))),
                "short_balance": safe_float(row.get("融券余额", row.get("融券余额(元)", None))),
            })
        return records
    except Exception as e:
        return {"error": str(e)}


def analyze_margin(margin_data):
    """分析融资融券趋势"""
    if not isinstance(margin_data, list) or len(margin_data) < 5:
        return {"status": "数据不足"}

    balances = [r["margin_balance"] for r in margin_data if r.get("margin_balance") is not None]
    if len(balances) < 5:
        return {"status": "数据不足"}

    result = {}
    result["latest_balance"] = balances[0] if balances else None

    # 融资余额趋势
    if len(balances) >= 5:
        if balances[0] > balances[4]:
            result["margin_trend"] = "融资余额上升（看多情绪增强）"
        elif balances[0] < balances[4]:
            result["margin_trend"] = "融资余额下降（看多情绪减弱）"
        else:
            result["margin_trend"] = "融资余额持平"

        change_pct = (balances[0] - balances[4]) / balances[4] * 100 if balances[4] else 0
        result["margin_change_5d_pct"] = round(change_pct, 2)

    return result


# ============================================================
# 千股千评
# ============================================================

def get_stock_comments(code):
    """获取千股千评"""
    df = ak.stock_comment_em()
    target = df[df["代码"] == code]
    if target.empty:
        return {"error": "未找到该股票"}
    row = target.iloc[0]
    return {
        "name": row.get("名称", ""),
        "latest_price": safe_float(row.get("最新价")),
        "change_pct": safe_float(row.get("涨跌幅")),
        "turnover_rate": safe_float(row.get("换手率")),
        "pe": safe_float(row.get("市盈率")),
        "attention_index": safe_float(row.get("关注指数")),
        "composite_score": safe_float(row.get("综合得分")),
        "ranking_change": safe_float(row.get("排名变化")),
    }


# ============================================================
# 综合情绪评分
# ============================================================

def calc_sentiment_score(fund_analysis, north_analysis, margin_analysis, comments):
    """多维度情绪评分"""
    scores = {}
    signals = []

    # 1. 主力资金评分 (0-100, 权重35%)
    fund_score = 50
    if isinstance(fund_analysis, dict) and "main_total_5d" in fund_analysis:
        total = fund_analysis["main_total_5d"]
        if total > 0:
            fund_score = min(80, 50 + 30)
            signals.append(f"主力5日净流入{total}(+)")
        else:
            fund_score = max(20, 50 - 30)
            signals.append(f"主力5日净流出{total}(-)")

        trend = fund_analysis.get("main_trend", "")
        if "加速" in trend and "流入" in trend:
            fund_score = min(100, fund_score + 15)
            signals.append("主力流入加速(+)")
        elif "加速" in trend and "流出" in trend:
            fund_score = max(0, fund_score - 15)
            signals.append("主力流出加速(-)")

        battle = fund_analysis.get("battle", "")
        if "吸筹" in battle:
            fund_score = min(100, fund_score + 10)
            signals.append("主力吸筹散户出逃(+)")
        elif "出货" in battle:
            fund_score = max(0, fund_score - 10)
            signals.append("主力出货散户接盘(-)")

    scores["fund_flow"] = fund_score

    # 2. 北向资金评分 (0-100, 权重25%)
    north_score = 50
    if isinstance(north_analysis, dict) and "total_5d" in north_analysis:
        total = north_analysis["total_5d"]
        if total > 0:
            north_score = min(80, 50 + 25)
            signals.append(f"北向5日净流入{total}(+)")
        else:
            north_score = max(20, 50 - 25)
            signals.append(f"北向5日净流出{total}(-)")

        momentum = north_analysis.get("momentum", "")
        if "加速" in momentum and "流入" in momentum:
            north_score = min(100, north_score + 10)
        elif "转流出" in momentum:
            north_score = max(0, north_score - 10)

    scores["north_flow"] = north_score

    # 3. 融资融券评分 (0-100, 权重15%)
    margin_score = 50
    if isinstance(margin_analysis, dict) and "margin_trend" in margin_analysis:
        trend = margin_analysis["margin_trend"]
        if "增强" in trend:
            margin_score = 65
            signals.append("融资余额上升(+)")
        elif "减弱" in trend:
            margin_score = 35
            signals.append("融资余额下降(-)")

    scores["margin"] = margin_score

    # 4. 千股千评评分 (0-100, 权重25%)
    comment_score = 50
    if isinstance(comments, dict) and "composite_score" in comments:
        cs = comments.get("composite_score")
        if cs is not None:
            comment_score = min(100, max(0, cs))
            if cs >= 70:
                signals.append(f"千股千评综合{cs}分(+)")
            elif cs <= 30:
                signals.append(f"千股千评综合{cs}分(-)")

    scores["comments"] = comment_score

    # 加权综合
    weighted = (
        scores["fund_flow"] * 0.35 +
        scores["north_flow"] * 0.25 +
        scores["margin"] * 0.15 +
        scores["comments"] * 0.25
    )
    scores["composite"] = round(weighted, 1)

    # 情绪判定
    if weighted >= 70:
        verdict = "强烈乐观"
    elif weighted >= 55:
        verdict = "偏乐观"
    elif weighted <= 30:
        verdict = "强烈悲观"
    elif weighted <= 45:
        verdict = "偏悲观"
    else:
        verdict = "中性"

    # 情绪周期定位
    if weighted >= 70 and fund_score >= 70:
        cycle = "分布期（情绪高涨，注意过热风险）"
    elif weighted <= 30 and fund_score <= 30:
        cycle = "恐慌期（情绪极度低迷，可能接近底部）"
    elif weighted > 50 and fund_score > 50:
        cycle = "积累期（情绪温和偏多，趋势形成中）"
    else:
        cycle = "调整期（情绪偏弱，等待方向确认）"

    return {
        "scores": scores,
        "composite": scores["composite"],
        "verdict": verdict,
        "cycle": cycle,
        "signals": signals
    }


# ============================================================
# 主函数
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请提供股票代码，如: python sentiment_analysis.py 600519"}, ensure_ascii=False))
        sys.exit(1)

    code = sys.argv[1]

    try:
        name = get_stock_name(code)

        fund_data = safe_call(get_fund_flow, code, 10)
        north_data = safe_call(get_north_flow, 20)
        margin_data = safe_call(get_margin_data, code)
        comments = safe_call(get_stock_comments, code)

        fund_analysis = analyze_fund_flow(fund_data) if isinstance(fund_data, list) else {"status": "数据异常"}
        north_analysis = analyze_north_flow(north_data) if isinstance(north_data, list) else {"status": "数据异常"}
        margin_analysis = analyze_margin(margin_data) if isinstance(margin_data, list) else {"status": "数据异常"}

        sentiment = calc_sentiment_score(fund_analysis, north_analysis, margin_analysis, comments)

        result = {
            "stock_code": code,
            "stock_name": name,
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fund_flow": fund_data,
            "fund_analysis": fund_analysis,
            "north_flow": north_data,
            "north_analysis": north_analysis,
            "margin_data": margin_data,
            "margin_analysis": margin_analysis,
            "comments": comments,
            "sentiment": sentiment,
        }

        print(json.dumps(result, ensure_ascii=False, indent=2, default=default_serializer))

    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
