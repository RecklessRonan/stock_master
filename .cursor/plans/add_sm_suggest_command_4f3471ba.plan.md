---
name: Add sm suggest command
overview: Add a new `sm suggest` command to automatically update research contexts, analyze the portfolio, and query multiple AI models via Cursor CLI for investment decisions.
todos:
  - id: implement-suggest-cmd
    content: Implement `suggest` command in `src/stock_master/cli.py`
    status: pending
  - id: scan-research-dir
    content: Add logic to scan `research/` for stock codes
    status: pending
  - id: update-contexts
    content: Add logic to call `build_context` for each code
    status: pending
  - id: construct-prompt
    content: Construct prompt with portfolio and contexts
    status: pending
  - id: call-cursor-cli
    content: Implement subprocess calls to `agent` CLI for the 3 models
    status: pending
  - id: save-results
    content: Save outputs to `journal/suggestions/YYYY-MM-DD/`
    status: pending
isProject: false
---

# Add `sm suggest` Command

## 1. Discover Researched Stocks

- Scan the `research/` directory to find all previously researched stock codes (e.g., `002273`, `09988`).
- Ignore non-directory files or invalid formats.

## 2. Update Contexts

- For each discovered stock code, call `build_context(code)` from `stock_master.pipeline.context_builder`.
- This will automatically fetch the latest K-line, valuation, news, and generate a new `context.md` under `research/<code>/YYYY-MM-DD/`.

## 3. Load Portfolio

- Read the current holdings from `journal/portfolio.yaml`.

## 4. Construct the Prompt

- Combine the portfolio data and the contents of the newly generated `context.md` files into a single comprehensive prompt.
- The prompt will ask the AI to analyze the current portfolio against the latest stock contexts and provide actionable trading decisions (buy/sell/hold/adjust) with reasoning.

## 5. Query Models via Cursor CLI

- Define the list of requested models: `["gpt-5.4 extra high", "opus 4.6", "gemini 3.1 pro"]`.
- For each model, execute the Cursor CLI using `subprocess.run`:

```python
  subprocess.run(
      ["agent", "-m", model, "-p", "--force", prompt],
      capture_output=True,
      text=True
  )
  

```

- Capture the standard output (the AI's response).

## 6. Save Decision Results

- Create a directory for today's suggestions: `journal/suggestions/YYYY-MM-DD/`.
- Save each model's output to a separate Markdown file, e.g., `journal/suggestions/YYYY-MM-DD/gpt-5.4-extra-high.md`.
- Print a summary to the console indicating where the suggestions are saved.

