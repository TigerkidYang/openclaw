#!/usr/bin/env python3
"""A股基本面分析脚本 - 基于 akshare 拉取财务数据"""

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


def get_stock_info(code):
    """获取股票基本信息"""
    df = ak.stock_individual_info_em(symbol=code)
    info = {}
    for _, row in df.iterrows():
        info[row["item"]] = row["value"]
    return {
        "name": info.get("股票简称", code),
        "industry": info.get("行业", "未知"),
        "market_cap": info.get("总市值", "未知"),
    }


def get_valuation(code):
    """获取估值数据"""
    spot = ak.stock_zh_a_spot_em()
    target = spot[spot["代码"] == code]
    if target.empty:
        return {"error": "未找到该股票"}
    row = target.iloc[0]
    return {
        "pe": row.get("市盈率-动态"),
        "pb": row.get("市净率"),
        "market_cap": row.get("总市值"),
        "price": row.get("最新价"),
        "change_pct": row.get("涨跌幅"),
    }


def get_financial_indicator(code):
    """获取主要财务指标（近8期）"""
    df = ak.stock_financial_analysis_indicator(symbol=code)
    if df.empty:
        return []
    df = df.head(8)
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row.get("日期", "")),
            "roe": row.get("净资产收益率(%)"),
            "roa": row.get("总资产净利率(%)"),
            "gross_margin": row.get("销售毛利率(%)"),
            "profit_margin": row.get("营业利润率(%)"),
        })
    return records


def get_profit_sheet(code):
    """获取利润表（近8期）"""
    df = ak.stock_profit_sheet_by_report_em(symbol=code)
    if df.empty:
        return []
    df = df.head(8)
    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row.get("REPORT_DATE_NAME", row.get("报告期", ""))),
            "revenue": row.get("TOTAL_OPERATE_INCOME", row.get("营业总收入")),
            "net_profit": row.get("NETPROFIT", row.get("净利润")),
            "operating_profit": row.get("OPERATE_PROFIT", row.get("营业利润")),
        })
    return records


def get_top10_holders(code):
    """获取十大股东"""
    df = ak.stock_gdfx_top_10_em(symbol=code)
    if df.empty:
        return []
    records = []
    for _, row in df.head(10).iterrows():
        records.append({
            "name": row.get("股东名称", ""),
            "ratio": row.get("持股比例", ""),
            "count": row.get("持股数量", ""),
            "type": row.get("股东性质", ""),
        })
    return records


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请提供股票代码，如: python fundamental_analysis.py 600519"}, ensure_ascii=False))
        sys.exit(1)

    code = sys.argv[1]

    try:
        info = get_stock_info(code)
        result = {
            "stock_code": code,
            "stock_name": info["name"],
            "industry": info["industry"],
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "valuation": safe_call(get_valuation, code),
            "financial_indicator": safe_call(get_financial_indicator, code),
            "profit_sheet": safe_call(get_profit_sheet, code),
            "top10_holders": safe_call(get_top10_holders, code),
        }

        print(json.dumps(result, ensure_ascii=False, indent=2, default=default_serializer))

    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
