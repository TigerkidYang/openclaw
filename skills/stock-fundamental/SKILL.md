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

## 报告格式要求

执行脚本获取数据后，你必须严格按照以下格式输出最终报告：

```
# 基本面分析: {股票名称} ({代码})

## 公司概况
行业: xxx | 市值: xxx亿

## 核心财务数据
营收: xxx亿 (同比 +xx%)
净利润: xxx亿 (同比 +xx%)
ROE: xx% | 毛利率: xx%

## 财务趋势
(近几个季度的营收和利润变化趋势)

## 估值分析
PE: xx (偏高/合理/偏低)
PB: xx (偏高/合理/偏低)

## 十大股东
(列出主要股东及持股比例)

## 深度发现
(如果有异常发现写在这里，没有则写"无异常发现")

## 近期重要事件
- xxx

## 竞争优势
- xxx

## 风险因素
- xxx

## 结论
评级: 优秀/良好/一般/较差
置信度: 高/中/低
总结: (一段话的专业判断)
```

## 示例

```bash
python3 {baseDir}/scripts/fundamental_analysis.py 600519
```
