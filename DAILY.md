## 2026-04-02

### 对话进展
- 综合 6 份现有 AI 升级思路和联网调研，确定以“稳健增值 + 新手友好 + 可接入付费数据”为主线推进 `stock_master`。
- 完成核心升级落地：新增 `dossier.yaml` 结构化事实包、多因子评分、组合风控、观察清单、学习飞轮，以及 `sm dossier`、`sm check-buy`、`sm watchlist`、`sm weekly-review` 等命令。
- 打通研究闭环，`sm suggest` 现在会结合 `context.md`、`dossier.yaml`、`agents/*.md`、`synthesis.md` 和组合风控一起生成建议。
- 完成测试与评审收口，升级实现已本地合并到 `main`，全量验证通过。

### 后续可做
- 接入真实的付费数据源（如 iFinD / Choice / Wind）并补足宏观、资金、评级、公告等高价值字段。
- 继续增强观察清单提醒、周复盘报表和行为偏差分析，让系统更像长期可用的投资教练。
