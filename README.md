# Stock Master 股票大师

本地优先的个人股票投资决策与学习系统，面向“稳健增值”的股票小白。

## 设计理念

- **事实 / 判断 / 行动 三层分离**：数据与证据 → 多模型分角色研究 → 人类最终裁决
- **本地优先**：研究、决策、交易数据保存在本地仓库与 SQLite
- **半自动研究**：Python 数据引擎 + Cursor 工作台 + 人工拍板
- **可追溯**：每笔交易可回链到原始调研、决策逻辑与复盘记录

## 快速开始

```bash
# 安装（推荐用 uv）
uv pip install -e .

# 拉取股票数据并生成研究上下文 + dossier
sm data 002273

# 结构化 dossier（含证据覆盖度与新手行动建议）
sm dossier 002273

# 多因子评分
sm score 002273

# 多股对比
sm compare 002273 300346 603501

# 买入前检查
sm check-buy 002273 --position-pct 8

# 观察清单
sm watchlist --action add --code 002273 --bucket wait_price --target-price 18.5

# 导入每日持仓截图
sm snapshot ~/Desktop/持仓.png

# 查看截图列表
sm snapshot

# 多模型智能投资建议（需要 agent CLI）
sm suggest

# 跳过数据刷新，仅用现有上下文
sm suggest --no-refresh

# 只分析指定股票
sm suggest -c 002273 -c 09988

# 生成带行为偏差提示的周复盘
sm weekly-review
```

## 工作流

1. `sm dossier <code>` — 生成 `context.md + dossier.yaml`，先看证据是否够，再决定要不要研究
2. `sm score <code>` / `sm compare ...` — 用质量 / 估值 / 趋势 / 风险 / 催化剂查看排序与可信度
3. 在 Cursor 中用角色模板做多视角调研，产出存入 `research/`
4. `sm suggest` — 把 context、dossier、agents、synthesis 和组合风控一起送入模型综合
5. `sm check-buy <code>` — 下单前先检查仓位、集中度和 dossier 建议是否冲突
6. `sm trade` / `sm weekly-review` — 交易留痕、复盘偏差、逐步形成个人投资规则

## 目录结构

```
src/stock_master/   — Python 核心引擎（数据、分析、编排、持仓）
prompts/            — AI 调研角色模板
research/           — 调研产物（按股票/日期）
  dossier.yaml      — 结构化事实包（每次研究目录下）
  _suggest/         — 组合级多模型投资建议（sm suggest 产出）
journal/            — 交易记录与复盘
  trades/           — 单笔交易 YAML
  entries/          — 交易叙事日志
  reviews/          — 复盘记录
  snapshots/        — 每日持仓截图（按日期命名）
  watchlist.yaml    — 观察清单与目标价
strategies/         — 策略模板与仓位纪律
storage/            — SQLite 缓存与本地数据库
artifacts/          — 图表、截图等导出文件
.cursor/rules/      — Cursor AI 规则
```

## 风险声明

本系统仅为个人投资研究辅助工具，不构成任何投资建议。所有交易决策由使用者本人负责。
系统默认不执行真实交易，任何真实下单必须经过人工确认。
