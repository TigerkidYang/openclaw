---
name: stock_sentiment
description: "获取A股股票的市场情绪数据，包括个股资金流向、北向资金、千股千评。输出JSON格式。"
metadata:
  openclaw:
    emoji: "💰"
    requires:
      bins: ["python3"]
    always: false
---

# 市场情绪数据工具

获取A股股票的资金流向和市场情绪数据。

## 使用方法

```bash
python3 {baseDir}/scripts/sentiment_analysis.py <股票代码>
```

## 参数

- `股票代码`: 6位A股代码，如 `600519`（贵州茅台）

## 输出

JSON 格式，包含:
- `stock_name`: 股票名称
- `fund_flow`: 近10日个股资金流向（主力净流入、散户净流入、超大单等）
- `north_flow`: 近20日北向资金每日净流入
- `comments`: 千股千评数据（综合评分、关注指数等）

## 示例

```bash
python3 {baseDir}/scripts/sentiment_analysis.py 600519
```
