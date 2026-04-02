# Stock Master 架构文档

## 系统概述

Stock Master 是一个本地优先的个人股票投资决策与学习系统，采用「Python 核心引擎 + Cursor 工作台 + 文件/数据库双存储」的混合架构。

## 核心原则

1. **事实/判断/行动分层**：数据与证据 → 多模型分角色研究 → 人类最终裁决
2. **本地优先**：所有数据保存在本地，不依赖云端服务
3. **人工确认**：真实交易必须经过人工确认
4. **可追溯**：每笔交易可回链到原始调研与决策逻辑

## 模块边界

```
src/stock_master/
├── data/           # 数据采集与缓存（AkShare + SQLite）
├── analysis/       # 多因子评分与报告生成
├── pipeline/       # dossier、研究编排与 suggest 闭环
├── portfolio/      # 交易记录、组合风控、观察清单与学习报告
└── models/         # 核心领域对象（Pydantic）
```

## 数据边界

| 存储方式 | 内容 | 特点 |
|----------|------|------|
| Git (Markdown/YAML) | 研究报告、决策文档、Prompt 模板、策略、复盘 | 慢变、可 diff、可审阅 |
| SQLite | 行情缓存、研究索引 | 高频、可派生、不入 Git |
| artifacts/ | 图表、截图、导出文件 | 二进制、按需保留 |

## Cursor 定位

Cursor 是**研究工作台**，负责：
- 角色规则（Rules）与 Prompt 模板管理
- 多 Tab/Composer 分角色调研
- 上下文 @ 引用仓库内数据
- 交互式策略讨论

Cursor **不负责**：
- 行情数据 ETL
- 定时任务与监控
- 风控规则自动执行
- 券商 API 真实交易

## 分阶段路线

### Phase 1（当前）：单股研究与 dossier 闭环
- `sm data` / `sm dossier` / `sm score` / `sm research`
- `context.md + dossier.yaml + stock-report.md` 三层研究产物
- 多角色 Prompt 模板 + Cursor 交互 + decision.md 结构化决策

### Phase 2（当前）：决策、组合与学习闭环
- `sm trade` / `sm portfolio` / `sm check-buy` / `sm review` / `sm weekly-review`
- YAML 交易记录 + Markdown 叙事日志 + 行为偏差提示
- 研究 → 决策 → 交易 → 复盘 → 学习 追溯链

### Phase 2.5（当前）：组合级多模型建议
- `sm suggest` — 自动刷新已研究股票上下文，并把 `context.md`、`dossier.yaml`、`agents/*.md`、`synthesis.md` 与组合风控一起送入模型
- 三模型独立建议 + GPT-5.4 最终综合报告
- 产物落在 `research/_suggest/{date}/`，不自动改写交易记录或 decision.md
- 继续遵守"AI 给建议、人类拍板"原则

### Phase 3（进行中）：组合与风险视图
- 持仓聚合与风险暴露计算
- 观察清单与目标价提醒
- 简易 Web 仪表盘（apps/web + apps/api）

### Phase 4（未来）：自动化扩展
- ModelProvider 与 DataProvider 多源自动调度（free / paid / search）
- Paper Trading 与模拟盘
- 券商适配器（默认关闭）
