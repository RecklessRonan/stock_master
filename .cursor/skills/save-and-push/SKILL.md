---
name: save-and-push
description: Use when the user invokes save-and-push, asks to append daily progress to DAILY.md then commit and push, or wants a session wrap-up synced to the remote.
---

# save-and-push

## 目标

将**当前对话的进展**写入仓库根目录的 `DAILY.md`，**概括本次工作区改动**并 `git commit`，再 **`git push`** 到当前分支的上游。

## 前置检查

- 确认工作区是 **git 仓库**，且已配置 `remote`（无远程则只执行到 commit，并说明原因）。
- **禁止** `git push --force`、`--force-with-lease`，除非用户在同一段对话里明确要求。
- 若有未合并冲突、`git status` 显示异常状态，先说明并停在做破坏性操作之前。

## 步骤

### 1. 更新 `DAILY.md`

- 路径：仓库根目录 `DAILY.md`（若不存在则创建）。
- 使用 **中文**，语气温和、可扫读；避免流水账复述工具输出。
- 在文件 **末尾追加** 一个新章节（不要整文件重写），建议结构：

```markdown
## YYYY-MM-DD

### 对话进展
- 用户目标 / 已解决的问题（1–5 条）
- 关键结论或约定（若有）

### 后续可做（可选）
- …
```

- **日期**：以用户或会话提供的「今天」为准；若无则用语境中的权威日期。

### 2. 概括改动并提交

1. 运行 `git status`；对未暂存改动运行 `git diff`；若有已暂存再运行 `git diff --cached`。
2. 用简短列表归纳：**改了哪些模块 / 文件、目的、风险点**（一句带过即可）。
3. **暂存**：将本次相关改动纳入提交（至少包含 `DAILY.md` 与本轮代码/配置文件改动）。  
   - 默认：`git add -A`（若用户明确排除某些路径则尊重排除项）。  
   - 不要擅自 `git add` 机密或明显不该进库的文件；若发现误添加路径，提醒用户。
4. **若无任何可提交变更**（例如全部已干净），则跳过 commit/push，在回复中说明。
5. **`git commit`**：
   - 第一行：**英文或中文短 subject**（≤72 字符为佳），例如 `docs(daily): log session + fix agent resolve`。
   - 正文：多行 `body`，对应第 2 步的改动归纳（可与 `DAILY.md` 互补，不必逐字重复）。

### 3. 推送

- 执行 `git push`（当前分支跟踪的上游）。
- 若需设置上游：`git push -u origin <branch>`（仅当当前分支无 upstream 且用户意图是推送到 `origin`）。
- **失败时**：打印远程错误摘要，不要求用户交互输入 token；可提示检查网络、权限、SSH、VPN。

## 完成后的回复

用几句话告诉用户：

- `DAILY.md` 追加了哪一天的段落；
- commit hash 或 subject（若 commit 成功）；
- push 是否成功。

## 何时不要用本技能

- 用户只要写日志、不要提交或不要 push。
- 用户要求在未审阅 diff 的情况下大批提交（应改为只生成摘要，由用户确认后再提交——除非用户在本轮明确说「直接提交」）。
