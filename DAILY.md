## 2026-04-02

### 对话进展
- 综合 6 份现有 AI 升级思路和联网调研，确定以“稳健增值 + 新手友好 + 可接入付费数据”为主线推进 `stock_master`。
- 完成核心升级落地：新增 `dossier.yaml` 结构化事实包、多因子评分、组合风控、观察清单、学习飞轮，以及 `sm dossier`、`sm check-buy`、`sm watchlist`、`sm weekly-review` 等命令。
- 打通研究闭环，`sm suggest` 现在会结合 `context.md`、`dossier.yaml`、`agents/*.md`、`synthesis.md` 和组合风控一起生成建议。
- 完成测试与评审收口，升级实现已本地合并到 `main`，全量验证通过。

### 后续可做
- 接入真实的付费数据源（如 iFinD / Choice / Wind）并补足宏观、资金、评级、公告等高价值字段。
- 继续增强观察清单提醒、周复盘报表和行为偏差分析，让系统更像长期可用的投资教练。

## 2026-04-02

### 对话进展
- 排查并修复 `sm suggest` 三模型（GPT-5.4 / Opus 4.6 / Gemini 3.1 Pro）全部失败的问题。
- 根因：agent CLI 的 HTTP/2 (gRPC) 连接不走系统代理（Clash），Cursor 服务端检测到中国 IP 后触发区域限制，拒绝 OpenAI / Anthropic / Google 模型。IDE 不受影响是因为其设置了 `disableHttp2: true`，HTTP/1.1 请求被 `global-agent` 正确代理。
- 新增 `_node_proxy_bootstrap.js`：通过 `NODE_OPTIONS --require` 注入，monkey-patch `http2.connect()` 让 gRPC 连接走 HTTP CONNECT 隧道。`_agent_env()` 自动从 Windows 注册表读取系统代理并注入该脚本，无需用户手动配置。
- 三个目标模型全部验证通过，20 项单元测试无回归。

### 后续可做
- 若 Cursor CLI 未来版本原生支持代理或修复区域检测，可移除 bootstrap 脚本。
- 关注 Cursor 论坛的区域限制讨论，看是否有官方修复。
