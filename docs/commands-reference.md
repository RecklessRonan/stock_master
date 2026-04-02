# Stock Master 命令参考手册

> 所有命令都以 `sm` 开头。运行 `sm --help` 可查看总览，运行 `sm <命令> --help` 可查看单个命令的详细参数。

---

## 命令总览

| 命令 | 功能 | 适用场景 |
|------|------|----------|
| `sm data` | 拉取数据并生成研究上下文包 | 只想拉数据，不需要完整调研目录 |
| `sm dossier` | 生成结构化个股 dossier | 快速查看事实档案和新手建议 |
| `sm score` | 查看多因子评分 | 快速了解一只股票的综合状况 |
| `sm compare` | 多股对比评分 | 在几只候选股之间做比较 |
| `sm research` | 一键准备完整调研 | 认真研究一只股票时的起点 |
| `sm suggest` | 多模型智能投资建议 | 需要 AI 综合决策参考时 |
| `sm trade` | 记录一笔交易 | 实盘买卖后记录 |
| `sm portfolio` | 查看当前持仓 | 日常查看持仓状态 |
| `sm check-buy` | 买前风控检查 | 买入前的最后一道关卡 |
| `sm watchlist` | 管理观察清单 | 跟踪感兴趣但还没买的股票 |
| `sm weekly-review` | 生成周复盘模板 | 每周回顾交易和学习 |
| `sm review` | 创建复盘模板 | 个股或月度复盘 |
| `sm alerts` | 查看和管理投资提醒 | 每天检查异动提醒 |
| `sm paper-trade` | 模拟盘交易 | 不花真钱练手 |
| `sm profile` | 查看行为画像 | 了解自己的交易风格和偏差 |
| `sm snapshot` | 导入持仓截图 | 从券商截图自动更新持仓 |
| `sm agent-login` | 登录 Cursor Agent CLI | `suggest` 和 `snapshot` 的前置步骤 |

---

## 详细命令说明

### sm data

拉取股票数据并生成研究上下文包（context.md + dossier.yaml）。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `CODE` | 位置参数 | 是 | 股票代码，如 `002273` |
| `--output, -o` | 字符串 | 否 | 指定输出目录（默认为 `research/<code>/<date>/`） |

**示例：**

```bash
# 基本用法
sm data 002273

# 指定输出目录
sm data 002273 --output ./my-research/
```

**产物：**
- `context.md` — 包含行情、估值、财务、新闻等原始数据的上下文文件
- `dossier.yaml` — 结构化事实档案

---

### sm dossier

生成结构化个股 dossier。功能与 `sm data` 相同，但命令名更直观。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `CODE` | 位置参数 | 是 | 股票代码 |
| `--output, -o` | 字符串 | 否 | 指定输出目录 |

**示例：**

```bash
sm dossier 600519
```

---

### sm score

查看股票的多因子评分（质量/估值/趋势/风险/催化剂 + 综合分 + 可信度）。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `CODE` | 位置参数 | 是 | 股票代码 |

**示例：**

```bash
sm score 002273
```

**输出示例：**

```
     水晶光电 (002273) 多因子评分
┌────────┬──────┬────────────┐
│ 维度   │ 评分 │ 图示       │
├────────┼──────┼────────────┤
│ 质量   │ 65.3 │ ██████░░░░ │
│ 估值   │ 48.1 │ ████░░░░░░ │
│ 趋势   │ 72.0 │ ███████░░░ │
│ 风险   │ 55.7 │ █████░░░░░ │
│ 催化剂 │ 60.0 │ ██████░░░░ │
│ 综合   │ 60.5 │ ██████░░░░ │
│ 可信度 │ 78.2 │ ███████░░░ │
└────────┴──────┴────────────┘
```

---

### sm compare

在多只股票之间并排对比评分，帮助你做选择。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `CODES` | 位置参数（多个） | 是 | 要对比的股票代码列表 |

**示例：**

```bash
# 对比三只股票
sm compare 002273 600519 000858
```

---

### sm research

一键准备完整调研：自动拉取数据、生成上下文包、创建调研目录和各角色模板。这是做深入研究时的推荐起点。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `CODE` | 位置参数 | 是 | 股票代码 |

**示例：**

```bash
sm research 002273
```

**产物目录结构：**

```
research/002273/2026-04-03/
├── context.md        ← 数据上下文包
├── dossier.yaml      ← 结构化事实档案
├── agents/           ← 各角色调研报告（待填写）
├── stock-report.md   ← 一页式结论页（8 个关键问题）
├── synthesis.md      ← 综合研判（待生成）
└── decision.md       ← 决策模板（待你填写）
```

**下一步**：在 Cursor 中 `@` 引用 `context.md` + `dossier.yaml` + `prompts/research/` 下的模板，分角色产出调研报告。

---

### sm suggest

调用多个 AI 模型（GPT/Claude/Gemini）生成综合投资建议。

**前置条件**：需要先运行 `sm agent-login` 登录。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `--no-refresh` | 开关 | 否 | 跳过数据刷新，使用已有的上下文 |
| `--code, -c` | 字符串（可多次） | 否 | 仅分析指定股票（不指定则分析全部已研究股票） |

**示例：**

```bash
# 分析所有已研究股票
sm suggest

# 仅分析指定股票
sm suggest --code 002273 --code 600519

# 跳过数据刷新
sm suggest --no-refresh
```

**产物**：保存在 `research/_suggest/<date>/` 目录下，包含各模型的独立建议和最终综合报告。

---

### sm trade

记录一笔真实交易。系统会同时更新交易记录、持仓状态和叙事日志。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `ACTION` | 位置参数 | 是 | 交易动作：`buy`（买入）/ `sell`（卖出）/ `add`（加仓）/ `reduce`（减仓） |
| `CODE` | 位置参数 | 是 | 股票代码 |
| `--price, -p` | 数字 | 是 | 成交价格 |
| `--shares, -s` | 整数 | 是 | 成交股数 |
| `--reason, -r` | 字符串 | 否 | 交易理由（强烈建议填写，便于复盘） |
| `--ref` | 字符串 | 否 | 关联的调研目录路径 |
| `--confidence, -c` | 整数 | 否 | 信心评分 1~10（默认 5） |
| `--review-date` | 字符串 | 否 | 复盘日期（YYYY-MM-DD 格式） |

**示例：**

```bash
# 买入
sm trade buy 002273 --price 20.5 --shares 500 --reason "估值合理，行业回暖"

# 卖出
sm trade sell 002273 --price 25.0 --shares 500 --reason "达到目标价，分批止盈"

# 加仓，附带调研引用和高信心
sm trade add 002273 --price 19.8 --shares 300 --reason "回调到支撑位" --ref "research/002273/2026-04-01" --confidence 8

# 减仓
sm trade reduce 002273 --price 23.0 --shares 200 --reason "仓位过重，降低风险"
```

**产物：**
- `journal/trades/<date>-<code>-<action>.yaml` — 结构化交易记录
- `journal/entries/<date>-<action>-<code>.md` — 叙事日志（待补充决策逻辑和情绪记录）
- `journal/portfolio.yaml` — 持仓自动更新

---

### sm portfolio

查看当前持仓状态。

**无需参数，直接运行：**

```bash
sm portfolio
```

**输出信息**：股票名称、持仓股数、成本价、止损价、策略、调研引用。

---

### sm check-buy

买入前的风控检查。综合评估候选标的是否适合当前买入。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `CODE` | 位置参数 | 是 | 候选股票代码 |
| `--position-pct` | 数字 | 是 | 计划仓位百分比（如 `5` 表示 5%） |

**示例：**

```bash
sm check-buy 002273 --position-pct 5
```

**检查项目：**
- 单票集中度是否过高
- 行业集中度是否过高
- 是否在追涨（当前价接近近期高点）
- 候选股与已有持仓是否高度相似
- Dossier 建议的仓位上限
- 关键研究证据是否缺失
- 失效条件是否已触发

---

### sm watchlist

管理你的股票观察清单。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `--action` | 字符串 | 否 | 操作类型：`list`（默认）/ `add` / `remove` |
| `--code` | 字符串 | 视操作 | 股票代码（add/remove 时必需） |
| `--bucket` | 字符串 | 否 | 分组：`ready`（默认）/ `wait_price` / `avoid` |
| `--target-price` | 数字 | 否 | 目标观察价 |
| `--thesis` | 字符串 | 否 | 观察逻辑说明 |

**示例：**

```bash
# 查看观察清单
sm watchlist

# 添加到 ready 分组
sm watchlist --action add --code 002273 --bucket ready --thesis "AR 赛道龙头，等回调"

# 添加到等价位分组，设置目标价
sm watchlist --action add --code 600519 --bucket wait_price --target-price 1600 --thesis "等估值回归"

# 添加到回避分组
sm watchlist --action add --code 000001 --bucket avoid --thesis "银行股周期性风险大"

# 移除
sm watchlist --action remove --code 000001
```

**分组含义：**
| 分组 | 含义 |
|------|------|
| `ready` | 已研究充分，随时可以买入 |
| `wait_price` | 在等合适的价位 |
| `avoid` | 已分析过，不建议买入 |

---

### sm weekly-review

生成包含行为偏差提示的周复盘模板。

**无需参数，直接运行：**

```bash
sm weekly-review
```

**产物**：在 `journal/reviews/` 下生成本周复盘模板，自动附带：
- 行为偏差提示（如果有的话）
- 下周执行清单建议

---

### sm review

创建复盘模板（个股复盘、周度复盘或月度复盘）。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `CODE` | 位置参数 | 否 | 股票代码（留空则创建周度复盘） |
| `--type, -t` | 字符串 | 否 | 复盘类型：`individual`（默认）/ `weekly` / `monthly` |
| `--ref` | 字符串 | 否 | 关联的调研目录 |

**示例：**

```bash
# 个股复盘
sm review 002273

# 周度复盘
sm review --type weekly

# 月度复盘
sm review --type monthly

# 个股复盘并关联调研
sm review 002273 --ref "research/002273/2026-04-01"
```

---

### sm alerts

查看和管理投资提醒。支持自动扫描持仓和观察清单的异动。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `--scan` | 开关 | 否 | 扫描持仓和观察清单，生成新提醒 |
| `--ack` | 整数 | 否 | 确认指定序号的提醒（标记为已处理） |

**示例：**

```bash
# 查看现有提醒
sm alerts

# 扫描生成新提醒
sm alerts --scan

# 确认第 0 号提醒
sm alerts --ack 0
```

**提醒类型：**

| 类型 | 说明 | 严重程度 |
|------|------|----------|
| `announcement` | 重大公告（增持/减持/回购/分红/并购等） | warning~critical |
| `earnings` | 业绩预告变动（预增/预减/扭亏/首亏等） | info~critical |
| `capital_flow` | 主力资金异常流入或流出 | warning |
| `valuation` | 估值到达历史极端区间 | info~warning |
| `price_target` | 观察清单中的目标价触发 | info |
| `risk_warning` | 风险预警（ST、退市风险等） | critical |
| `rebalance` | 仓位偏离目标，需要再平衡 | info |
| `drawdown` | 回撤超过阈值 | warning~critical |

---

### sm paper-trade

模拟盘交易——不涉及真实资金，初始虚拟资金 100 万元。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `ACTION` | 位置参数 | 是 | 操作：`buy` / `sell` / `status` / `performance` |
| `--code, -c` | 字符串 | buy/sell 时必需 | 股票代码 |
| `--price, -p` | 数字 | buy/sell 时必需 | 价格 |
| `--shares, -s` | 整数 | buy/sell 时必需 | 股数 |
| `--reason, -r` | 字符串 | 否 | 交易理由 |

**示例：**

```bash
# 模拟买入
sm paper-trade buy --code 002273 --price 20.5 --shares 500

# 模拟卖出
sm paper-trade sell --code 002273 --price 22.0 --shares 500 --reason "达到目标价"

# 查看模拟盘持仓
sm paper-trade status

# 查看模拟盘业绩
sm paper-trade performance
```

**数据文件**：`journal/paper_portfolio.yaml`

---

### sm profile

查看个人交易行为画像和学习建议。基于你的全部交易记录进行分析。

**无需参数，直接运行：**

```bash
sm profile
```

**输出内容：**
- 总交易次数、胜率
- 平均持有天数
- 你的优势（做对了什么）
- 常见错误（容易在哪里犯错）
- 行为偏差检测（过度交易、追涨杀跌、注意力驱动等），按严重程度标注 🔴/🟡/🟢
- 个性化学习建议

---

### sm snapshot

导入持仓截图，通过 AI 自动识别并更新持仓数据。

**参数：**

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `IMAGE` | 位置参数 | 否 | 截图文件路径（留空则处理 `journal/snapshots/` 内未归档截图） |
| `--no-ai` | 开关 | 否 | 跳过 AI 处理，仅导入文件 |
| `--note, -n` | 字符串 | 否 | 备注（写入同名 .txt 文件） |
| `--list, -l` | 开关 | 否 | 查看截图列表 |

**前置条件**：需要先运行 `sm agent-login` 登录 Cursor Agent CLI。

**示例：**

```bash
# 导入截图并自动识别
sm snapshot 持仓截图.png

# 导入截图并添加备注
sm snapshot 持仓截图.png --note "午盘截图"

# 仅导入，不做 AI 处理
sm snapshot 持仓截图.png --no-ai

# 处理 snapshots/ 中所有未归档截图
sm snapshot

# 查看截图列表
sm snapshot --list
```

**AI 处理流程：**
1. 从截图中识别持仓数据（股票/股数/成本/现价等）
2. 与当前 `portfolio.yaml` 对比，推断交易操作
3. 自动生成交易记录和叙事日志
4. 更新 `journal/portfolio.yaml`

---

### sm agent-login

登录 Cursor Agent CLI。`sm suggest` 和 `sm snapshot` 的 AI 功能依赖已登录的 Agent。

**无需参数，直接运行：**

```bash
sm agent-login
```

按提示完成登录即可。登录状态会持久保存，通常只需要登录一次。

---

## 命令速查表

### 新手入门三步走

```bash
sm research 002273        # 1. 拉数据 + 准备调研目录
sm score 002273           # 2. 看评分
sm check-buy 002273 --position-pct 5  # 3. 买前检查
```

### 日常流程

```bash
sm alerts --scan          # 每日：检查异动
sm portfolio              # 查看持仓
sm watchlist              # 查看观察清单
sm weekly-review          # 每周：生成复盘模板
```

### 交易记录

```bash
sm trade buy 002273 --price 20.5 --shares 500 --reason "理由"
sm trade sell 002273 --price 25.0 --shares 500 --reason "理由"
```

### 模拟盘

```bash
sm paper-trade buy --code 002273 --price 20.5 --shares 500
sm paper-trade status
sm paper-trade performance
```

### 学习成长

```bash
sm profile                # 查看行为画像
sm review 002273          # 个股复盘
sm suggest                # AI 综合建议
```
