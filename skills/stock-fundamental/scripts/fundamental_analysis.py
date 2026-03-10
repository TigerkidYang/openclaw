#!/usr/bin/env python3
"""A股深度基本面分析脚本 - 财务报表、估值、增长、质量检测"""

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


# ============================================================
# 基本信息 & 估值
# ============================================================

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
        "float_cap": info.get("流通市值", "未知"),
        "total_shares": info.get("总股本", "未知"),
        "float_shares": info.get("流通股", "未知"),
        "listing_date": info.get("上市时间", "未知"),
    }


def get_valuation(code):
    """获取估值数据"""
    spot = ak.stock_zh_a_spot_em()
    target = spot[spot["代码"] == code]
    if target.empty:
        return {"error": "未找到该股票"}
    row = target.iloc[0]
    pe = safe_float(row.get("市盈率-动态"))
    pb = safe_float(row.get("市净率"))

    # PE评价
    pe_eval = None
    if pe is not None:
        if pe < 0:
            pe_eval = "亏损"
        elif pe < 15:
            pe_eval = "低估"
        elif pe < 25:
            pe_eval = "合理"
        elif pe < 40:
            pe_eval = "偏高"
        else:
            pe_eval = "高估"

    # PB评价
    pb_eval = None
    if pb is not None:
        if pb < 1:
            pb_eval = "破净"
        elif pb < 2:
            pb_eval = "低估"
        elif pb < 5:
            pb_eval = "合理"
        else:
            pb_eval = "偏高"

    return {
        "pe": pe,
        "pe_eval": pe_eval,
        "pb": pb,
        "pb_eval": pb_eval,
        "market_cap": safe_float(row.get("总市值")),
        "price": safe_float(row.get("最新价")),
        "change_pct": safe_float(row.get("涨跌幅")),
    }


# ============================================================
# 财务指标
# ============================================================

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
            "roe": safe_float(row.get("净资产收益率(%)")),
            "roa": safe_float(row.get("总资产净利率(%)")),
            "gross_margin": safe_float(row.get("销售毛利率(%)")),
            "profit_margin": safe_float(row.get("营业利润率(%)")),
            "net_margin": safe_float(row.get("销售净利率(%)")),
            "expense_ratio": safe_float(row.get("管理费用率(%)")),
        })
    return records


# ============================================================
# 利润表
# ============================================================

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
            "revenue": safe_float(row.get("TOTAL_OPERATE_INCOME", row.get("营业总收入"))),
            "net_profit": safe_float(row.get("NETPROFIT", row.get("净利润"))),
            "operating_profit": safe_float(row.get("OPERATE_PROFIT", row.get("营业利润"))),
            "total_cost": safe_float(row.get("TOTAL_OPERATE_COST", row.get("营业总成本"))),
        })
    return records


# ============================================================
# 资产负债表
# ============================================================

def get_balance_sheet(code):
    """获取资产负债表关键数据（近8期）"""
    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=code)
        if df.empty:
            return []
        df = df.head(8)
        records = []
        for _, row in df.iterrows():
            total_assets = safe_float(row.get("TOTAL_ASSETS", row.get("资产总计")))
            total_liab = safe_float(row.get("TOTAL_LIABILITIES", row.get("负债合计")))
            total_equity = safe_float(row.get("TOTAL_EQUITY", row.get("股东权益合计")))
            current_assets = safe_float(row.get("TOTAL_CURRENT_ASSETS", row.get("流动资产合计")))
            current_liab = safe_float(row.get("TOTAL_CURRENT_LIABILITIES", row.get("流动负债合计")))

            # 计算比率
            debt_ratio = round(total_liab / total_assets * 100, 2) if total_assets and total_liab else None
            current_ratio = round(current_assets / current_liab, 2) if current_liab and current_assets else None

            records.append({
                "date": str(row.get("REPORT_DATE_NAME", row.get("报告期", ""))),
                "total_assets": total_assets,
                "total_liabilities": total_liab,
                "total_equity": total_equity,
                "current_assets": current_assets,
                "current_liabilities": current_liab,
                "debt_ratio": debt_ratio,
                "current_ratio": current_ratio,
                "accounts_receivable": safe_float(row.get("ACCOUNTS_RECE", row.get("应收账款"))),
                "inventory": safe_float(row.get("INVENTORY", row.get("存货"))),
                "goodwill": safe_float(row.get("GOODWILL", row.get("商誉"))),
            })
        return records
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# 现金流量表
# ============================================================

def get_cashflow(code):
    """获取现金流量表关键数据（近8期）"""
    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
        if df.empty:
            return []
        df = df.head(8)
        records = []
        for _, row in df.iterrows():
            op_cf = safe_float(row.get("NETCASH_OPERATE", row.get("经营活动产生的现金流量净额")))
            inv_cf = safe_float(row.get("NETCASH_INVEST", row.get("投资活动产生的现金流量净额")))
            fin_cf = safe_float(row.get("NETCASH_FINANCE", row.get("筹资活动产生的现金流量净额")))

            records.append({
                "date": str(row.get("REPORT_DATE_NAME", row.get("报告期", ""))),
                "operating_cashflow": op_cf,
                "investing_cashflow": inv_cf,
                "financing_cashflow": fin_cf,
            })
        return records
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# 十大股东
# ============================================================

def get_top10_holders(code):
    """获取十大股东"""
    df = ak.stock_gdfx_top_10_em(symbol=code)
    if df.empty:
        return []
    records = []
    for _, row in df.head(10).iterrows():
        records.append({
            "name": row.get("股东名称", ""),
            "ratio": safe_float(row.get("持股比例")),
            "count": safe_float(row.get("持股数量")),
            "type": row.get("股东性质", ""),
        })
    return records


# ============================================================
# 增长率计算
# ============================================================

def calc_growth(profit_data):
    """计算营收和利润增长率"""
    if not isinstance(profit_data, list) or len(profit_data) < 2:
        return {"status": "数据不足"}

    result = {}
    # 最近一期 vs 上一期（季度环比）
    latest = profit_data[0]
    prev = profit_data[1]

    if latest.get("revenue") and prev.get("revenue") and prev["revenue"] != 0:
        result["revenue_qoq"] = round((latest["revenue"] - prev["revenue"]) / abs(prev["revenue"]) * 100, 2)
    if latest.get("net_profit") and prev.get("net_profit") and prev["net_profit"] != 0:
        result["profit_qoq"] = round((latest["net_profit"] - prev["net_profit"]) / abs(prev["net_profit"]) * 100, 2)

    # 同比（最近一期 vs 4期前，即去年同期）
    if len(profit_data) >= 5:
        yoy_prev = profit_data[4]
        if latest.get("revenue") and yoy_prev.get("revenue") and yoy_prev["revenue"] != 0:
            result["revenue_yoy"] = round((latest["revenue"] - yoy_prev["revenue"]) / abs(yoy_prev["revenue"]) * 100, 2)
        if latest.get("net_profit") and yoy_prev.get("net_profit") and yoy_prev["net_profit"] != 0:
            result["profit_yoy"] = round((latest["net_profit"] - yoy_prev["net_profit"]) / abs(yoy_prev["net_profit"]) * 100, 2)

    # 营收趋势（近4期方向）
    revenues = [p["revenue"] for p in profit_data[:4] if p.get("revenue")]
    if len(revenues) >= 3:
        # 注意: profit_data[0]是最新的，所以reverse看趋势
        revenues_chrono = list(reversed(revenues))
        if all(revenues_chrono[i] <= revenues_chrono[i+1] for i in range(len(revenues_chrono)-1)):
            result["revenue_trend"] = "持续增长"
        elif all(revenues_chrono[i] >= revenues_chrono[i+1] for i in range(len(revenues_chrono)-1)):
            result["revenue_trend"] = "持续下滑"
        else:
            result["revenue_trend"] = "波动"

    # 利润趋势
    profits = [p["net_profit"] for p in profit_data[:4] if p.get("net_profit")]
    if len(profits) >= 3:
        profits_chrono = list(reversed(profits))
        if all(profits_chrono[i] <= profits_chrono[i+1] for i in range(len(profits_chrono)-1)):
            result["profit_trend"] = "持续增长"
        elif all(profits_chrono[i] >= profits_chrono[i+1] for i in range(len(profits_chrono)-1)):
            result["profit_trend"] = "持续下滑"
        else:
            result["profit_trend"] = "波动"

    return result


# ============================================================
# 财务质量检测
# ============================================================

def check_financial_quality(profit_data, cashflow_data, balance_data, indicator_data):
    """检测财务质量，标记潜在风险"""
    warnings = []

    # 1. 利润与现金流背离
    if isinstance(profit_data, list) and isinstance(cashflow_data, list):
        if len(profit_data) > 0 and len(cashflow_data) > 0:
            net_profit = profit_data[0].get("net_profit")
            op_cf = cashflow_data[0].get("operating_cashflow")
            if net_profit and op_cf:
                if net_profit > 0 and op_cf < 0:
                    warnings.append("利润为正但经营现金流为负，盈利质量存疑")
                elif net_profit > 0 and op_cf > 0 and op_cf < net_profit * 0.5:
                    warnings.append("经营现金流远低于净利润（<50%），需关注应收账款")

    # 2. 资产负债率过高
    if isinstance(balance_data, list) and len(balance_data) > 0:
        debt_ratio = balance_data[0].get("debt_ratio")
        if debt_ratio and debt_ratio > 70:
            warnings.append(f"资产负债率{debt_ratio}%偏高（>70%），财务杠杆风险")

        # 商誉占比
        goodwill = balance_data[0].get("goodwill")
        total_assets = balance_data[0].get("total_assets")
        if goodwill and total_assets and total_assets > 0:
            gw_ratio = goodwill / total_assets * 100
            if gw_ratio > 10:
                warnings.append(f"商誉占总资产{round(gw_ratio,1)}%（>10%），存在减值风险")

        # 流动比率
        current_ratio = balance_data[0].get("current_ratio")
        if current_ratio and current_ratio < 1:
            warnings.append(f"流动比率{current_ratio}（<1），短期偿债压力")

    # 3. ROE趋势下滑
    if isinstance(indicator_data, list) and len(indicator_data) >= 3:
        roes = [r.get("roe") for r in indicator_data[:3] if r.get("roe") is not None]
        if len(roes) >= 3:
            roes_chrono = list(reversed(roes))
            if all(roes_chrono[i] > roes_chrono[i+1] for i in range(len(roes_chrono)-1)):
                warnings.append("ROE连续下滑，盈利能力减弱")

    # 4. 毛利率大幅波动
    if isinstance(indicator_data, list) and len(indicator_data) >= 2:
        gm_latest = indicator_data[0].get("gross_margin")
        gm_prev = indicator_data[1].get("gross_margin")
        if gm_latest is not None and gm_prev is not None and gm_prev != 0:
            gm_change = abs(gm_latest - gm_prev)
            if gm_change > 5:
                direction = "上升" if gm_latest > gm_prev else "下降"
                warnings.append(f"毛利率{direction}{round(gm_change,1)}个百分点，需关注原因")

    if not warnings:
        warnings.append("未发现明显财务风险信号")

    return warnings


# ============================================================
# 主函数
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请提供股票代码，如: python fundamental_analysis.py 600519"}, ensure_ascii=False))
        sys.exit(1)

    code = sys.argv[1]

    try:
        info = get_stock_info(code)
        profit_data = safe_call(get_profit_sheet, code)
        cashflow_data = safe_call(get_cashflow, code)
        balance_data = safe_call(get_balance_sheet, code)
        indicator_data = safe_call(get_financial_indicator, code)

        # 增长率计算
        growth = calc_growth(profit_data) if isinstance(profit_data, list) else {"status": "利润数据异常"}

        # 财务质量检测
        quality_warnings = check_financial_quality(profit_data, cashflow_data, balance_data, indicator_data)

        result = {
            "stock_code": code,
            "stock_name": info["name"],
            "industry": info["industry"],
            "company_info": info,
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "valuation": safe_call(get_valuation, code),
            "financial_indicator": indicator_data,
            "profit_sheet": profit_data,
            "balance_sheet": balance_data,
            "cashflow": cashflow_data,
            "growth": growth,
            "quality_warnings": quality_warnings,
            "top10_holders": safe_call(get_top10_holders, code),
        }

        print(json.dumps(result, ensure_ascii=False, indent=2, default=default_serializer))

    except Exception as e:
        print(json.dumps({"error": f"分析失败: {str(e)}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
