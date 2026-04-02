# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Stock Master (股票大师) is a Python 3.12+ CLI tool (`sm`) for personal stock investment research. Pure Python, no Docker, no Node.js, no external databases. Data is stored in local SQLite + YAML/Markdown files.

### Development environment

- **Python venv**: `/workspace/.venv` (created with `uv venv .venv`).
- **Activate**: `source .venv/bin/activate` (all commands below assume active venv).
- **Package manager**: `uv` (installed at `~/.local/bin/uv`). Add `$HOME/.local/bin` to PATH if not present.

### Common commands

| Task | Command |
|------|---------|
| Install deps | `uv pip install -e ".[test]"` |
| Run CLI | `sm --help` |
| Lint | `ruff check src/ tests/` |
| Tests | `pytest tests/ -v` |
| Fetch data | `sm data <code>` (e.g. `sm data 002273`) |
| Score stock | `sm score <code>` |

### Non-obvious notes

- The `ruff check` has ~73 pre-existing lint warnings (mostly E501 line-length). These are in the existing codebase and should not block development.
- `sm suggest` and `sm snapshot` require the Cursor Agent CLI (`agent` binary) to be installed and logged in. Most other commands work without it.
- AkShare data fetching requires internet access and can take 30-60 seconds per stock on first run (data is cached in SQLite afterwards).
- The `.venv/` directory is gitignored. After pulling latest changes, re-run `uv pip install -e ".[test]"` to pick up any dependency changes.
- `storage/stock_master.db` is auto-created on first data fetch; no migration step needed.
