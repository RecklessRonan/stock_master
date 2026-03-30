# Stock Master 股票大师

本地优先的个人股票投资决策系统。

## 设计理念

- **事实 / 判断 / 行动 三层分离**：数据与证据 → 多模型分角色研究 → 人类最终裁决
- **本地优先**：研究、决策、交易数据保存在本地仓库与 SQLite
- **半自动研究**：Python 数据引擎 + Cursor 工作台 + 人工拍板
- **可追溯**：每笔交易可回链到原始调研、决策逻辑与复盘记录

## 快速开始

```bash
# 安装（推荐用 uv）
uv pip install -e .

# 拉取股票数据并生成研究上下文
sm data 002273

# 五维量化评分
sm score 002273

# 多股对比
sm compare 002273 300346 603501

# 导入每日持仓截图
sm snapshot ~/Desktop/持仓.png

# 查看截图列表
sm snapshot
```

## 工作流

1. `sm data <code>` — 拉数据、生成统一上下文包 `context.md`
2. 在 Cursor 中用角色模板做多视角调研，产出存入 `research/`
3. 强模型综合生成共识/分歧矩阵与投资论点
4. 人工确认决策：仓位、触发条件、失效条件、复盘日期
5. 交易后写入 `journal/`，复盘时回链调研

## 目录结构

```
src/stock_master/   — Python 核心引擎（数据、分析、编排、持仓）
prompts/            — AI 调研角色模板
research/           — 调研产物（按股票/日期）
journal/            — 交易记录与复盘
  trades/           — 单笔交易 YAML
  entries/          — 交易叙事日志
  reviews/          — 复盘记录
  snapshots/        — 每日持仓截图（按日期命名）
strategies/         — 策略模板与仓位纪律
storage/            — SQLite 缓存与本地数据库
artifacts/          — 图表、截图等导出文件
.cursor/rules/      — Cursor AI 规则
```

## 风险声明

本系统仅为个人投资研究辅助工具，不构成任何投资建议。所有交易决策由使用者本人负责。
系统默认不执行真实交易，任何真实下单必须经过人工确认。
