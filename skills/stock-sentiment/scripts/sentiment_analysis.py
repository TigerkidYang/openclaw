#!/usr/bin/env python3
"""A股市场情绪分析脚本 - 基于 akshare 拉取资金流向数据"""

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


def get_stock_name(code):
    """获取股票名称"""
    df = ak.stock_individual_info_em(symbol=code)
    row = df[df["item"] == "股票简称"]
    if not row.empty:
        return str(row.iloc[0]["value"])
    return code


def get_market(code):
    """根据股票代码判断市场"""
    if code.startswith("6"):
        return "sh"
    return "sz"


def get_fund_flow(code, days=10):
    """获取个股资金流向（近N日）"""
    market = get_market(code)
    df = ak.stock_individual_fund_flow(stock=code, market=market)
    df = df.tail(days)
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row.get("日期", "")),
            "main_net_inflow": row.get("主力净流入-净额"),
            "main_net_pct": row.get("主力净流入-净占比"),
            "retail_net_inflow": row.get("小单净流入-净额"),
            "super_large_net": row.get("超大单净流入-净额"),
            "large_net": row.get("大单净流入-净额"),
            "medium_net": row.get("中单净流入-净额"),
        })
    return records


def get_north_flow(days=20):
    """获取北向资金每日流向"""
    df = ak.stock_hsgt_fund_flow_summary_em()
    df = df.tail(days)
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row.get("日期", row.get("trade_date", ""))),
            "north_net": row.get("北向资金", row.get("north_money", None)),
        })
    return records


def get_stock_comments(code):
    """获取千股千评"""
    df = ak.stock_comment_em()
    target = df[df["代码"] == code]
    if target.empty:
        return {"error": "未找到该股票"}
    row = target.iloc[0]
    return {
        "name": row.get("名称", ""),
        "latest_price": row.get("最新价"),
        "change_pct": row.get("涨跌幅"),
        "turnover_rate": row.get("换手率"),
        "pe": row.get("市盈率"),
        "attention_index": row.get("关注指数"),
        "composite_score": row.get("综合得分"),
        "ranking_change": row.get("排名变化"),
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请提供股票代码，如: python sentiment_analysis.py 600519"}, ensure_ascii=False))
        sys.exit(1)

    code = sys.argv[1]

    try:
        name = get_stock_name(code)
        result = {
            "stock_code": code,
            "stock_name": name,
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fund_flow": safe_call(get_fund_flow, code, 10),
            "north_flow": safe_call(get_north_flow, 20),
            "comments": safe_call(get_stock_comments, code),
        }

        print(json.dumps(result, ensure_ascii=False, indent=2, default=default_serializer))

    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
