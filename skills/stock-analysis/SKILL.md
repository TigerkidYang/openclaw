---
name: stock_analysis
description: "当用户要求分析某只A股股票时使用。提供技术分析数据拉取和指标计算能力，支持均线、MACD、RSI、KDJ、布林带等指标。"
metadata:
  openclaw:
    emoji: "📈"
    requires:
      bins: ["python3"]
    always: false
---

# 股票技术分析工具

用于获取A股股票的技术分析数据。

## 使用方法

```bash
python3 {baseDir}/scripts/technical_analysis.py <股票代码>
```

## 参数

- `股票代码`: 6位A股代码，如 `600519`（贵州茅台）、`000001`（平安银行）

## 输出

JSON 格式，包含:
- `price`: 最新价格、开高低收、成交量、涨跌幅
- `ma`: MA5/10/20/60 均线值、方向、排列状态、金叉/死叉信号
- `macd`: DIF、DEA、MACD柱、金叉/死叉信号
- `rsi`: RSI6/12/24、超买超卖状态
- `kdj`: K/D/J值、金叉/死叉/钝化信号
- `bollinger`: 上中���轨、当前价格位置
- `levels`: 支撑位、压力位

## 示例

```bash
python3 {baseDir}/scripts/technical_analysis.py 600519
```
