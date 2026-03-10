---
name: stock_fundamental
description: "获取A股股票的基本面数据，包括财务指标、利润表、估值、十大股东。输出JSON格式。"
metadata:
  openclaw:
    emoji: "📊"
    requires:
      bins: ["python3"]
    always: false
---

# 股票基本面数据工具

获取A股股票的基本面财务数据。

## 使用方法

```bash
python3 {baseDir}/scripts/fundamental_analysis.py <股票代码>
```

## 参数

- `股票代码`: 6位A股代码，如 `600519`（贵州茅台）

## 输出

JSON 格式，包含:
- `stock_name`: 股票名称
- `industry`: 所属行业
- `valuation`: 估值数据（PE、PB、市值、最新价）
- `financial_indicator`: 近8期财务指标（ROE、ROA、毛利率、营业利润率）
- `profit_sheet`: 近8期利润表（营收、净利润、营业利润）
- `top10_holders`: 十大股东（名称、持股比例、性质）

## 示例

```bash
python3 {baseDir}/scripts/fundamental_analysis.py 600519
```
