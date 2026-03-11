# Repository Guidelines

## Project Structure & Module Organization
Core trading logic lives in `btc/`, `stocks/`, `execution/`, and `quant/`. Shared infrastructure such as config loading, logging, Telegram, and common utilities sits in `common/`. The React dashboard is in `dashboard/`, with app code under `dashboard/src/` and static assets in `dashboard/public/`. Tests are primarily Python tests in `tests/`; operational scripts and entrypoints are in `scripts/`; documentation and screenshots live in `docs/`.

## Build, Test, and Development Commands
Use the repo root for backend work:

- `.venv/bin/pip install -r requirements.txt`: install backend and test dependencies into the local virtualenv.
- `docker compose up -d --build`: start the local stack and dashboard-serving backend.
- `.venv/bin/python -m pytest`: run the Python test suite from `tests/`.
- `.venv/bin/flake8 .`: lint Python code with the repository rules.

Use `dashboard/` for frontend work:

- `npm run dev`: start the Vite dev server on `localhost:3000`.
- `npm run build`: create the production bundle in `dashboard/dist/`.
- `npm run lint`: run ESLint on the dashboard code.

## Coding Style & Naming Conventions
Follow PEP 8 with repository overrides: 4-space indentation and a soft 120-character line limit. Python modules use `snake_case.py`; test files use `test_*.py`. Keep trading logic separated by market or domain rather than adding large cross-cutting modules. In the dashboard, prefer React function components, `PascalCase` component filenames such as `BtcPage.jsx`, and `camelCase` for hooks and utility functions.

## Testing Guidelines
Pytest is configured in `pytest.ini` and discovers `tests/test_*.py`, `Test*` classes, and `test_*` functions. Add or update tests with every behavior change, especially around env loading, metrics, execution flow, and market-specific strategies. For frontend changes, run `npm run lint` and include manual verification for affected routes such as `/`, `/kr`, `/us`, or `/agents`.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit subjects like `Remove broken README references` and `Build dashboard in Docker image`. Keep commits focused and descriptive. Pull requests should include a concise summary, impacted areas, test or lint commands run, linked issues, and screenshots for dashboard UI changes.

## Security & Configuration Tips
Keep secrets in local `.env` files only; never commit API keys, certificates, logs, or generated dashboard builds unless intentionally updating deploy artifacts. Treat broker integrations and external APIs as untrusted input, and validate config changes with paper or dry-run paths before touching live trading flows.
