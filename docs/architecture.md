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

### Phase 1（已实现）：证据层 — 单股研究与 dossier 闭环
- `sm data` / `sm dossier` / `sm score` / `sm research`
- `context.md + dossier.yaml + stock-report.md` 三层研究产物
- 多角色 Prompt 模板 + Cursor 交互 + decision.md 结构化决策

### Phase 2（已实现）：评分体系 — 决策、组合与学习闭环
- `sm trade` / `sm portfolio` / `sm check-buy` / `sm review` / `sm weekly-review`
- YAML 交易记录 + Markdown 叙事日志 + 行为偏差提示
- 研究 → 决策 → 交易 → 复盘 → 学习 追溯链

### Phase 3（已实现）：投研教练 — 组合级多模型建议
- `sm suggest` — 自动刷新已研究股票上下文，并把 `context.md`、`dossier.yaml`、`agents/*.md`、`synthesis.md` 与组合风控一起送入模型
- 三模型独立建议 + GPT-5.4 最终综合报告
- 产物落在 `research/_suggest/{date}/`，不自动改写交易记录或 decision.md
- 继续遵守"AI 给建议、人类拍板"原则

### Phase 4（已实现）：组合风控 — 持仓聚合与风险暴露
- 行业集中度 / 回撤阈值 / 现金比例 / 追涨检测 / 同质检测 / 再平衡建议
- `comprehensive_portfolio_analysis()` 综合风控一键分析
- 观察清单三分类（ready / wait_price / avoid）+ 目标价提醒

### Phase 5（已实现）：提醒系统 — 事件驱动异动检测
- 8 类提醒：公告、业绩预告、资金异动、估值异常、目标价触发、风险预警、再平衡、回撤
- `sm alerts --scan` 全持仓 + 观察清单联合扫描
- 提醒确认机制 `sm alerts --ack <id>`

### Phase 6（已实现）：学习飞轮 — 模拟盘与行为画像
- `sm paper-trade` 模拟盘交易（初始资金 100 万，支持 buy/sell/status/performance）
- `sm profile` 行为画像（胜率、持有天数、优势、常见错误）
- 行为偏差检测（过度交易、追涨杀跌、注意力驱动、频繁换股、补跌、过早止盈）
- `journal/personal_rules.yaml` 个人规则库
- 教学段落（context.md 内嵌指标解读教学）

### 未来规划
- **Web 仪表盘**：`apps/web` + `apps/api`，可视化持仓与风控
- **券商适配器**：真实交易执行（默认关闭，需人工确认 + 风控通过）

---

## 已实现功能清单

| 阶段 | 功能模块 | 关键能力 | 状态 |
|------|----------|----------|------|
| **Phase 1: 证据层** | 数据采集 | AkShare A股/港股行情、基本信息、财务摘要、新闻 | ✅ 已实现 |
| | 扩展数据源 | 资金流向、股东变化、公告、业绩预告、三表数据（利润表/资产负债表/现金流量表） | ✅ 已实现 |
| | 证据覆盖度 | 13 项覆盖度检查（基本信息/行情/估值/财务/新闻/宏观/同行对比/资金流/股东变化/公告/业绩预告/完整财报/估值历史） | ✅ 已实现 |
| | EvidencePack | 标准化多源证据容器（Pydantic 领域模型） | ✅ 已实现 |
| | 研究产物 | context.md + dossier.yaml + stock-report.md 三层结构 | ✅ 已实现 |
| **Phase 2: 评分体系** | 5 维因子评分 | 质量(0.28) + 估值(0.22) + 趋势(0.20) + 风险(0.20) + 催化剂(0.10) | ✅ 已实现 |
| | 子因子解释 | 每个因子含结构化子因子拆解 + 文字摘要 | ✅ 已实现 |
| | 同行分位 | 各因子的同行百分位排名 | ✅ 已实现 |
| | 可信度 | 基于数据覆盖率计算综合可信度 | ✅ 已实现 |
| | 多股对比 | `sm compare` 并排展示多只股票评分 | ✅ 已实现 |
| **Phase 3: 投研教练** | 研究模板 | 10+ 个角色模板（宏观/基本面/财务/风险/技术/行业/资金流/催化剂/公司治理/深度估值） | ✅ 已实现 |
| | 一页式报告 | stock-report.md — 回答 8 个关键投资问题 | ✅ 已实现 |
| | 研究闭环 | research → agents → synthesis → decision 全链路 | ✅ 已实现 |
| | 新手行动建议 | dossier.yaml 内嵌 rookie_action（结论/仓位上限/检查清单） | ✅ 已实现 |
| | 多模型建议 | `sm suggest` — GPT/Claude/Gemini 三模型 + 最终综合 | ✅ 已实现 |
| | 新 CLI 命令 | `sm research` / `sm suggest` / `sm snapshot` / `sm agent-login` | ✅ 已实现 |
| **Phase 4: 组合风控** | 行业集中度 | 按行业分组计算仓位占比，超限报警 | ✅ 已实现 |
| | 回撤阈值 | 单票浮亏 + 组合加权回撤检测 | ✅ 已实现 |
| | 现金比例 | 现金占总资产比例检查（默认下限 20%） | ✅ 已实现 |
| | 追涨检测 | 当前价接近近期高点或短期涨幅过大 | ✅ 已实现 |
| | 同质检测 | 候选股与持仓的行业/概念重叠检查 | ✅ 已实现 |
| | 再平衡建议 | 实际 vs 目标仓位偏离超阈值时提示 | ✅ 已实现 |
| | 综合风控 | `comprehensive_portfolio_analysis()` 一键汇总 | ✅ 已实现 |
| **Phase 5: 提醒系统** | 8 类异动提醒 | 公告 / 业绩预告 / 资金异动 / 估值异常 / 目标价 / 风险预警 / 再平衡 / 回撤 | ✅ 已实现 |
| | 观察清单 | 三分类（ready / wait_price / avoid）+ 目标价提醒 | ✅ 已实现 |
| | 组合约束建议 | 买前检查融合 dossier + 风控 + 失效条件 | ✅ 已实现 |
| **Phase 6: 学习飞轮** | 模拟盘 | `sm paper-trade`（buy/sell/status/performance，初始 100 万） | ✅ 已实现 |
| | 行为画像 | `sm profile`（胜率/持有天数/优势/常见错误/学习建议） | ✅ 已实现 |
| | 行为偏差检测 | 6 类偏差（过度交易/追涨/杀跌/注意力驱动/频繁换股/过早止盈） | ✅ 已实现 |
| | 个人规则库 | `journal/personal_rules.yaml` 自动积累 | ✅ 已实现 |
| | 教学段落 | context.md 内嵌指标解读（PE/PB/ROE 等含义说明） | ✅ 已实现 |
| **未来** | Web 仪表盘 | apps/web + apps/api 可视化 | 🔲 规划中 |
| | 券商适配器 | 真实交易执行（默认关闭） | 🔲 规划中 |

---

## 数据路由架构

Stock Master 使用 `DataRouter` 实现数据获取的三级降级策略，确保即使没有付费数据源也能正常运行。

```
┌──────────────────────────────────────────────┐
│              DataRouter 路由决策              │
│                                              │
│  1. paid（优先）                              │
│     └─ iFinD / Choice / Wind                 │
│     └─ 需设置环境变量：SM_IFIND_TOKEN 等      │
│                                              │
│  2. free（默认降级）                           │
│     └─ AkShare（免费 A 股/港股数据）          │
│     └─ 无需配置，开箱即用                     │
│                                              │
│  3. search（兜底）                            │
│     └─ 联网搜索补充最新事件与外部观点          │
│     └─ 用于填补结构化数据的空白               │
└──────────────────────────────────────────────┘
```

**调用方式**：`DataRouter.fetch_with_fallback(data_type, free_fn, paid_fn, search_fn)` 按 paid → free → search 顺序尝试，任一层成功即返回数据及来源标签。

**已注册数据源**：

| 名称 | 类型 | 说明 | 环境变量 |
|------|------|------|----------|
| akshare | free | 默认免费行情与基础财务数据源 | — |
| web_search | search | 联网搜索补充最新事件与外部观点 | — |
| ifind | paid | 同花顺 iFinD 付费数据 | `SM_IFIND_TOKEN` |
| choice | paid | 东方财富 Choice 付费数据 | `SM_CHOICE_TOKEN` |
| wind | paid | Wind 付费数据 | `SM_WIND_TOKEN` |
