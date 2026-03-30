---
name: Stock Master 架构与工作流设计方案
overview: 构建一个高度结构化的本地仓库，集成 AkShare 数据获取脚本，并利用 Cursor IDE 的多 Agent 能力和自定义规则（Rules）进行半自动化投研与混合格式日志记录。
todos:
  - id: init_dirs
    content: 初始化目录结构 (data, research, strategies, journal, scripts, .cursor/rules)
    status: pending
  - id: create_rules
    content: 创建各个 AI 角色的 Cursor Rules (技术面、基本面、风险、总结)
    status: pending
  - id: write_fetch_script
    content: 编写基于 AkShare 的基础数据获取脚本 (fetch_stock.py)
    status: pending
  - id: create_journal_templates
    content: 创建混合模式的 Journal 模板 (trade_ledger.json 和 Markdown 模板)
    status: pending
isProject: false
---

# Stock Master 架构与工作流设计方案

根据你的需求与选择，由于 Cursor CLI 本身不支持后台多模型自动化编排，我们将充分利用 **Cursor IDE 的 Composer/Agent 能力**，结合 **Python 数据抓取脚本** 和 **结构化目录**，打造一个高效的半自动化股票投研与复盘系统。

## 一、 核心目录结构设计

建议在当前仓库建立如下目录结构：

- `**.cursor/rules/`**：存放不同 AI 角色的 prompt 规则文件（如 `technical_analyst.md` 关注K线, `fundamental_analyst.md` 关注财报, `summary_agent.md` 用于最终决策）。在 Cursor 中对话时可随时 @ 对应规则。
- `**scripts/`**：存放基于 **AkShare** 的 Python 脚本。用于一键获取某只股票的最新K线、财报、市盈率等数据，并自动生成 AI 易读的 Markdown/CSV 数据片段。
- `**data/`**：由 scripts 自动抓取并存放的原始数据缓存（按股票代码分类，如 `data/002273/`）。
- `**research/`**：个股深度调研报告目录。沿用你之前的优秀结构，但进行标准化：
  - `research/002273/agents-drafts/`：存放各 AI 模型的初步分析结论。
  - `research/002273/00-final-decision.md`：存放最终由强模型总结的投资决策。
- `**strategies/`**：存放各类型股票策略的讨论和固化规则（例如：`strategies/dividend_strategy.md`，`strategies/breakout.md`）。
- `**journal/`**：交易行为与决策记录（**混合模式**）：
  - `journal/trade_ledger.json`（或 CSV）：纯数据记录（时间、代码、买卖方向、价格、股数、手续费），方便未来做可视化 PnL 统计。
  - `journal/entries/`：Markdown 日志，记录每次交易的“决策逻辑、当时情绪、AI 的建议”（如 `20260330-buy-002273.md`）。

## 二、 改进后的工作流 (Workflow)

我们将你之前的流程优化为标准化、可复用的 5 步：

### Step 1: 数据准备 (Data Fetching)

在终端运行类似 `python scripts/fetch_stock.py 002273` 的脚本。脚本通过 **AkShare** 获取该股票近1年的K线、最新财报核心指标及近期新闻，并输出到 `data/002273/` 目录下。

### Step 2: 多维分析 (Multi-Agent Drafts)

利用 Cursor 的多 Tab 或 Composer，分别 @ 不同的模型和规则进行基础分析：

- **Tab 1 (模型A + @technical_rule)**: 读取 `data/002273/kline.csv`，输出技术面分析至 `research/002273/agents-drafts/tech.md`。
- **Tab 2 (模型B + @fundamental_rule)**: 读取财务数据，输出基本面分析至 `fundamental.md`。
- **Tab 3 (模型C + @risk_rule)**: 输出风险与舆情分析至 `risk.md`。

### Step 3: 强模型汇总 (Synthesis)

使用最强模型（如 Claude 3.5 Sonnet / GPT-4o），在 Cursor Composer 中 @整个 `agents-drafts/` 目录，并 @`summary_agent_rule`，让它提炼矛盾点、总结共识，输出 `00-final-decision.md`。

### Step 4: 策略讨论与辩论 (Interactive Chat)

基于 `00-final-decision.md` 和 `strategies/` 里的既定策略，在 Cursor 中继续与 AI 对话：“你觉得现价买入符合我的左侧建仓策略吗？” 这一步完全由你主导，AI 充当陪练。

### Step 5: 决策执行与记录 (Logging)

交易完成后，通过预设的模板，在 `journal/trade_ledger.json` 记下客观数据，在 `journal/entries/` 写下主观复盘。也可让 Cursor 帮你从对话中自动提取出 json 数据和 Markdown 总结并写入文件。

## 三、 接下来的实施步骤

如果你同意此方案，我们将按以下步骤在当前仓库开始构建：

1. **初始化目录结构**并生成 `.cursor/rules` 中的核心 AI 角色提示词模板。
2. **编写 `scripts/fetch_stock.py`**，接入 AkShare 跑通第一个股票（例如 002273）的数据抓取。
3. **建立 Journal 模板**，包括 JSON 数据结构示例和 Markdown 复盘模板。
4. **实战演练**：我们用一个新的股票代码走一遍完整流程，验证效果。

