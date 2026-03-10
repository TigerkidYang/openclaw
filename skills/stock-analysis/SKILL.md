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
- `bollinger`: 上中下轨、当前价格位置
- `levels`: 支撑位、压力位

## 报告格式要求

执行脚本获取数据后，你必须严格按照以下格式输出最终报告：

```
# 技术面分析: {股票名称} ({代码})

## 价格概览
最新价: xxx | 涨跌幅: xx% | 成交量: xxx万手

## 均线系统
MA5: xxx | MA10: xxx | MA20: xxx | MA60: xxx
排列状态: 多头排列/空头排列/交叉
信号: 金叉/死叉/无

## MACD
DIF: xx | DEA: xx | MACD柱: xx | 信号: 金叉/死叉

## RSI
RSI6: xx | RSI12: xx | RSI24: xx | 状态: 超买/超卖/中性

## KDJ
K: xx | D: xx | J: xx | 信号: 金叉/死叉

## 布林带
上轨: xxx | 中轨: xxx | 下轨: xxx | 当前位置: 上轨附近/中轨/下轨附近

## 关键价位
支撑位: xxx, xxx
压力位: xxx, xxx

## 深度发现
(如果有异常发现写在这里，没有则写"无异常发现")

## 结论
趋势判断: 看多/看空/中性
置信度: 高/中/低
总结: (一段话的专业判断)
```

## 示例

```bash
python3 {baseDir}/scripts/technical_analysis.py 600519
```
