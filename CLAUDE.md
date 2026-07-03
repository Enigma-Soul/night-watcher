# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                           # install dependencies
uv run python main.py                             # launch the desktop widget
uv run --no-sync python -c "<test snippet>"       # run ad-hoc tests without re-syncing
```

No linting or test framework is configured — this is a desktop application, not a package.

## Architecture

NightWatcher is a PySide6 desktop widget that displays CGM (continuous glucose monitoring) data as a stay-on-top floating badge. It pulls data from pluggable adapters — only adapters make HTTP requests; the core library, UI, config, and cache layers never touch the network.

**Data flow (pull cycle):**
```
QTimer [2 min] → app.refresh()
  → dispatches _FetchWorker (QRunnable) onto QThreadPool
  → worker runs adapter.fetch() on a background thread
  → emits Signal(adapter_id, entries | None, error | None) back to main thread
  → SGV.merge(entries) + Cache.save + update_ui()
```

Fetching happens off the main thread so the widget never freezes during network I/O — this replaces the old project's bare `Thread + sleep` pattern that would block on sync `requests.get`.

**Startup sequence (main.py):**
1. `QApplication` created early (needed for `QMessageBox` error dialogs during adapter scanning).
2. `Config.load("config.json")` — writes defaults if missing, backs up corrupted files to `.bad`.
3. `logger.setup("log.log")` — file + console handlers via stdlib `logging`.
4. `adapter_loader.scan("adapter")` — importlib scans `adapter/*.py`, collects `BaseAdapter` subclasses. Duplicate `id` or missing `id` → fatal error dialog + exit.
5. Instantiate adapters: `{cls.id: cls(config.adapter_config(cls.id))}`. Config missing for an adapter → empty dict (no KeyError).
6. Active adapter fallback: `config.gui.active_adapter` must exist in `instances`; otherwise the first instance is used and written back.
7. `App.run()` — show `FloatWidget`, start timer, initial refresh, `QApplication.exec()`.

**Module responsibilities:**

| Module | Role |
|---|---|
| `libs/base_adapter.py` | `BaseAdapter` ABC + `FetchError`. Adapter contract: `id` (str), `name` (str), `fetch() -> list[dict]`, `is_configured() -> bool`. |
| `libs/adapter_loader.py` | Scans `adapter/` with `pkgutil.iter_modules` + `importlib.import_module`. Skips `_`-prefixed files. Detects duplicate `id`. |
| `libs/sgv.py` | In-memory entry store. `merge()` deduplicates by `date` (later wins). `latest()`, `in_range()`, `tir(low, high, start, end)`. No persistence. |
| `libs/cache.py` | `cache.json` reader/writer, partitioned by adapter id. Atomic write via `.tmp` + `os.replace`. Corrupted file → returns `[]`. |
| `libs/config.py` | `config.json` reader/writer with defaults. Corrupted → backup to `.bad` + rewrite defaults. GUI and adapter configs separated. |
| `libs/logger.py` | stdlib `logging` wrappers. `setup(path)` + `get()`. File write failure degrades gracefully (no crash). |
| `libs/ui/app.py` | `App` class — owns `QTimer`, `QThreadPool`, `SGV`, `Config`, `Cache`, adapter instances. Orchestrates refresh cycle, source switching, UI updates. |
| `libs/ui/float_widget.py` | 120×60 frameless, always-on-top badge. Left-click toggles info panel, drag to move, right-click → context menu. |
| `libs/ui/info_panel.py` | Expandable 260×260 panel: glucose value + arrow + timestamp, 1/6/12/24h time-range buttons, `ChartView`, `TirView`. |
| `libs/ui/chart_view.py` | QPainter line chart with high/low dashed reference lines. |
| `libs/ui/tir_view.py` | High/Range/Low QProgressBar triplets. |
| `libs/ui/settings_dialog.py` | GUI preferences + per-adapter credential editor. Emits `settings_changed(dict)` with `{"gui": {...}, "adapter": {id: {...}}}`. |

## Adapter contract

Every adapter is a `.py` file in `adapter/` with a single class that subclasses `BaseAdapter`. The file must use **absolute imports** (`from libs.base_adapter import BaseAdapter`).

Required class attributes:
- `id: str` — unique identifier, matches the key in `config["adapter"][<id>]`.
- `name: str` — display name for UI menus.

Required method:
- `fetch() -> list[dict]` — returns entries in the format:
  ```
  [{"date": int(ms), "sgv": int(mg/dL), "direction": str}, ...]
  ```
  On failure, raises `FetchError`. Do **not** deduplicate or sort — `SGV.merge` handles that.

Optional override:
- `is_configured() -> bool` — return `False` if minimum config (token/url) is missing. The app shows `--` and skips fetch when unconfigured.

The config dict passed to `__init__` is `config["adapter"].get(cls.id, {})`. Adapters read their own keys (e.g. `self.config.get("ss_token")`) — key names are adapter-defined.

Files named with a leading `_` (e.g. `_wip.py`, `__init__.py`) are skipped by the loader. Two adapters sharing the same `id` cause a fatal error dialog at startup.

## Internal conventions

**sgv is always mg/dL.** The `sgv` field inside entries is always `int` mg/dL. Adapters are responsible for converting from their source unit before returning entries (e.g. Sisensing `v` mmol/L → `round(v * 18.018)`). The config stores `low_line`/`high_line`/`max` in mg/dL. The `unit` config key only controls GUI display (`_format_value` divides by 18.018 for `"mmol/L"`).

**direction strings are NightScout names.** Adapters return `"DoubleUp"`, `"SingleUp"`, `"FortyFiveUp"`, `"Flat"`, `"FortyFiveDown"`, `"SingleDown"`, `"DoubleDown"`. The UI maps these to arrow glyphs. Unknown/missing direction → `→`.

**Network isolation rule.** Only files under `adapter/` may `import requests` or make HTTP calls. `libs/`, `main.py`, and `libs/ui/` must remain network-free.

**Config and data are separate files.** `config.json` = credentials + GUI prefs (gitignored, template at `config.example.json`). `cache.json` = blood glucose entries (also gitignored). The old project mixed 271 KB of data into `config.json` — this is explicitly avoided.

**Atomic file writes.** `Config` and `Cache` both write to `.tmp` first, then `os.replace` to the target path. This prevents corruption on crash or partial write.

## Gotchas

- **`QAction` is `PySide6.QtGui`, not `QtWidgets`** (PySide6 6.11 / Qt6). The old project had it in the wrong package.
- **Sisensing needs `Authorization: Bearer <token>`** — the reference implementation in `G:\Temp\nightscout-sisensingcgm-uploader` was missing the `Bearer` prefix. The API doc at `docs/sisensing-api.md` confirms `Bearer` is required.
- **`datetime.now()` works in application code.** The workflow-script restriction on `Date.now()` only applies to the `Workflow` tool's JavaScript scripts, not to the Python application.
- **Adapters use absolute imports.** `from libs.base_adapter import BaseAdapter` — relative imports (`from ..libs`) don't work because `adapter` and `libs` are sibling top-level packages.
- **The project is an application, not a package.** `pyproject.toml` has `[tool.uv] package = false`. There is no `setup.py`, `setup.cfg`, or build system. `uv sync` installs dependencies into `.venv`; `uv run python main.py` runs the app.

## Built-in adapters

| Adapter | `id` | Source | Config keys |
|---|---|---|---|
| Sisensing | `"sisensing"` | Sisensing follower API (CN/EU) | `ss_token`, `ss_region`, `timeout`, `retries`, `mock_file` |
| NightScout | `"nightscout"` | Any NightScout `entries.json` | `ns_url`, `api_secret`, `count` |

Sisensing supports a `mock_file` config key — when set to a local JSON path, `fetch()` reads the file instead of making an HTTP request. This allows full end-to-end testing without real credentials.
