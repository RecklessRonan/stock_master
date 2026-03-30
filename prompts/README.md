# Prompt 模板库

调研与决策流程中各角色的 AI 提示词模板。

## 目录结构

```
prompts/
├── research/           # 分角色调研模板
│   ├── 01-fundamental.md    # 基本面分析
│   ├── 02-financial.md      # 财务深度分析
│   ├── 03-risk.md           # 风险评估（空头视角）
│   ├── 04-technical.md      # 技术面分析
│   └── 05-industry.md       # 行业与竞争
├── synthesis/          # 综合研判模板
│   ├── consensus-matrix.md  # 共识/分歧矩阵
│   └── investment-thesis.md # 投资论点生成
├── suggest/            # 组合级多模型建议模板（sm suggest 使用）
│   ├── model-decision.md    # 单模型分析 prompt
│   └── final-synthesis.md   # 最终综合 prompt
└── discussion/         # 策略讨论模板
    └── strategy-review.md   # 策略一致性检查
```

## 使用方式

模板中的 `{{变量}}` 在使用时替换为实际数据。在 Cursor 中使用时：

1. 运行 `sm data <code>` 生成上下文包
2. 在 Cursor Chat 中 `@` 引用对应模板和 context.md
3. 收集各角色输出到 `research/{code}/{date}/agents/`

### sm suggest 自动建议

`prompts/suggest/` 下的模板由 `sm suggest` 自动使用，无需手动引用：

- `model-decision.md` — 发给每个模型的分析 prompt（结合持仓 + 各股上下文）
- `final-synthesis.md` — 汇总三份独立建议的综合 prompt

结果保存在 `research/_suggest/{date}/`。
