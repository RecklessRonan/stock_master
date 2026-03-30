# Stock Master 架构文档

## 系统概述

Stock Master 是一个本地优先的个人股票投资决策系统，采用「Python 核心引擎 + Cursor 工作台 + 文件/数据库双存储」的混合架构。

## 核心原则

1. **事实/判断/行动分层**：数据与证据 → 多模型分角色研究 → 人类最终裁决
2. **本地优先**：所有数据保存在本地，不依赖云端服务
3. **人工确认**：真实交易必须经过人工确认
4. **可追溯**：每笔交易可回链到原始调研与决策逻辑

## 模块边界

```
src/stock_master/
├── data/           # 数据采集与缓存（AkShare + SQLite）
├── analysis/       # 量化评分与辅助分析
├── pipeline/       # 研究编排与上下文构建
├── portfolio/      # 交易记录、持仓与复盘
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

### Phase 1（当前）：单股研究与决策闭环 MVP
- `sm data` / `sm score` / `sm research`
- 多角色 Prompt 模板 + Cursor 交互
- decision.md 结构化决策

### Phase 2（当前）：决策与交易日志
- `sm trade` / `sm portfolio` / `sm review`
- YAML 交易记录 + Markdown 叙事日志
- 研究 → 决策 → 交易 → 复盘 追溯链

### Phase 3（未来）：组合与风险视图
- 持仓聚合与风险暴露计算
- 观察清单与提醒
- 简易 Web 仪表盘（apps/web + apps/api）

### Phase 4（未来）：自动化扩展
- ModelProvider 多模型自动调度
- Paper Trading 与模拟盘
- 券商适配器（默认关闭）
