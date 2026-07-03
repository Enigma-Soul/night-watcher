# NightWatcher

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![CI](https://img.shields.io/github/actions/workflow/status/Enigma-Soul/night-watcher/ci.yml?style=flat-square&label=CI)](https://github.com/Enigma-Soul/night-watcher/actions)
[![License](https://img.shields.io/badge/License-GPLv3-blue?style=flat-square)](./LICENSE)

English | [简体中文](README.md)

A desktop CGM glucose widget. Pulls data from pluggable adapters — SiBionics, NightScout, or your own source — and displays it as a stay-on-top, frameless, semi-transparent floating badge with real-time values and trend arrows.

**PySide6** + **requests** + **loguru**, managed with **uv**, formatted with **Ruff**.

## Features

- **Floating badge** — 120×60 frameless, always-on-top, semi-transparent rounded widget. Drag it anywhere.
- **Info panel** — tap the badge to expand a 260×280 panel with 1/6/12/24h glucose curves, TIR bars, and a last-updated timestamp.
- **Zone-colored curves** — the line and dots recolor per reading: low (red) / in-range (green) / high (yellow).
- **Drag-and-drop adapters** — drop a `.py` file into `adapter/` and it's loaded on next launch. Files starting with `_` are skipped.
- **Adaptive scheduling** — automatically calibrates server-client clock offset by computing interval mode, avoiding both "waiting too long" and "polling too often".
- **Theme system** — full contract in `themes/*.toml` (main / panel / chart / TIR), selectable from the settings dialog.
- **Multi-source switching** — right-click menu or settings dialog; each adapter has its own config block.
- **Network isolation** — only adapters make HTTP requests. Core library, UI, config, and cache layers never touch the network.
- **Offline resilience** — entries cached in `data/<id>.json`; restarting without a network still shows cached data immediately.

## Quick Start

```bash
git clone <repo-url> && cd night-watcher
uv sync
cp config.example.json config.json    # fill in your credentials
uv run python main.py
```

> [!NOTE]
> `config.json` and `data/` are gitignored — they contain credentials and personal health data.

## Configuration

`config.json` holds GUI preferences and per-adapter credentials. Start from `config.example.json`:

```json
{
  "gui": {
    "low_line": 72, "high_line": 180, "max": 270,
    "theme": "default",
    "unit": "mmol/L",
    "time_range": 6,
    "active_adapter": "sisensing"
  },
  "adapter": {
    "sisensing": {
      "ss_token": "your-token",
      "ss_region": "CN",
      "timeout": 10,
      "retries": 3,
      "mock_file": ""
    },
    "nightscout": {
      "ns_url": "https://your-ns.example.com",
      "api_secret": "your-api-secret",
      "count": 288
    }
  }
}
```

**GUI fields:**
- `low_line` / `high_line` / `max` are stored in **mg/dL** internally; `unit` only controls display.
- `theme` selects a name under `themes/`.
- `time_range` accepts `1 | 6 | 12 | 24` hours.

**Adapter fields:** each adapter reads its own config block from `config["adapter"][<id>]`. Key names are adapter-defined.

> [!TIP]
> **Testing without credentials:** set `sisensing.mock_file` to a local JSON dump of the SiBionics API response. The adapter runs the full parse pipeline without any HTTP request — great for verifying the UI and data pipeline.

## Themes

`themes/*.toml` defines the full theme contract:

```toml
[main]
background = "#1E1E2E"
opacity = 0.85
text_color = "#FFFFFF"
offline_color = "#FFAA00"
border_color = "#646464"

[panel]
background = "#1E1E2E"
opacity = 0.86
text_color = "#FFFFFF"
border_color = "#506080"
border_radius = 10

[chart]
line_color = "#6496FA"
high_line_color = "#FA9664"
low_line_color = "#96FA64"
line_width = 2
dot_visible = true
dot_size = 3
low_zone_color = "#EB5757"
normal_zone_color = "#6DAE81"
high_zone_color = "#F2C94C"

[tir]
high_color = "#F2C94C"
range_color = "#6DAE81"
low_color = "#EB5757"
```

User themes only need to override the keys they care about; missing keys fall back to `default.toml`.

## Built-in Adapters

### SiBionics (`sisensing`)

Follower-mode CGM data from `https://api.sisensing.com/follow/app/follow/myself/glucose/details/devices`.

| Config key | Description |
|---|---|
| `ss_token` | Bearer token (UUID format, obtained via packet capture) |
| `ss_region` | `"CN"` (verified) or `"EU"` (unvalidated) |
| `timeout` | Request timeout in seconds |
| `retries` | Retry attempts on failure |
| `mock_file` | Local JSON path for offline testing (empty = real HTTP) |

Converts `glucoseInfos[].v` from mmol/L to mg/dL (×18.018) and maps the `s` direction field to NightScout arrow names. Automatically skips expired devices with empty `glucoseInfos`.

### NightScout (`nightscout`)

Pulls from any NightScout instance's `entries.json`. Data is already in NightScout format, so the adapter forwards it with minimal normalization.

| Config key | Description |
|---|---|
| `ns_url` | Base URL of the NightScout instance |
| `api_secret` | API secret (optional, sent as `api-secret` header) |
| `count` | Entries per request (default 288, ~1 day at 5-min intervals) |

## Writing Your Own Adapter

Create a `.py` file in `adapter/` that subclasses `BaseAdapter`:

```python
from libs.base_adapter import BaseAdapter, FetchError

class MyAdapter(BaseAdapter):
    id = "my_source"         # unique identifier — matches config["adapter"] key
    name = "My CGM Source"
    poll_interval_seconds = 300  # data publish interval (seconds)

    def is_configured(self) -> bool:
        return bool(self.config.get("api_key"))

    def fetch(self) -> list[dict]:
        # Return entries in this format:
        #   [{"date": int(ms), "sgv": int(mg/dL), "direction": str}, ...]
        # Raise FetchError on failure.
        # Don't deduplicate or sort — SGV.merge handles that.
        ...
```

**Loading rules:**
- Files starting with `_` (e.g. `_wip.py`, `__init__.py`) are skipped.
- Every other `.py` is imported and scanned for `BaseAdapter` subclasses.
- Two adapter classes sharing the same `id` → startup error dialog and exit.

> [!WARNING]
> Only adapter files may make network requests. The core library, UI, config, and cache layers must remain network-free. An adapter *may* optionally upload to NightScout inside `fetch()`, but that is not a project requirement.

## Development

```bash
# Install dependencies
uv sync

# Launch the app
uv run python main.py

# Format code
uv run ruff format .

# Lint
uv run ruff check .
```

### Code conventions

- **Ruff** drives both lint and format; config is in `pyproject.toml`: `line-length = 100`, targeting Python 3.12+, with `E/F/I/N/W/UP` rules.
- Comments and commit messages are in Chinese.
- **Absolute imports**: adapter files use `from libs.base_adapter import BaseAdapter`, not relative imports.
- **Don't add dependencies lightly**: currently pinned to `PySide6` + `requests` + `loguru`. Open an issue before adding more.

### Layout

| Path | Role |
|------|------|
| `main.py` | Sole entry point |
| `libs/` | Core library (fixed files, not auto-discovered) |
| `libs/ui/` | PySide6 widgets |
| `adapter/` | Pluggable data-source adapters (auto-scanned at startup) |
| `themes/` | Theme `.toml` files |
| `data/` | Runtime cache + adaptive metadata (gitignored) |
| `config.json` | Credentials + GUI prefs (gitignored) |

### Commit convention

Follows [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scope): short description
fix(scope): short description
chore: short description
```

Branch model: `main` is protected, PRs only. Active development happens on `develop`.

## CI & Releases

GitHub Actions handles the full pipeline:

- **check** (every push/PR): `uv sync` + core-import smoke test.
- **build-and-release** (on push to `main`): `pyinstaller --onefile` → parse the first line of `CHANGELOG.md` for the version → create a GitHub Release with `v{version}` tag and attach `night-watcher.exe`.

Workflow:

1. Develop, commit, push on `develop`.
2. Open a `develop → main` PR.
3. After merge, CI automatically builds, reads `CHANGELOG.md`, and publishes a tagged release.

## Architecture

```
main.py              # sole entry point — orchestrates startup and owns the event loop
libs/
├── config.py        #   Config — atomic JSON read/write, defaults on corruption
├── sgv.py           #   SGV — flat entry list, merge-by-date dedup, TIR stats
├── base_adapter.py  #   BaseAdapter + FetchError + adaptive scheduling state machine
├── adapter_loader.py#   importlib scanner — _-prefix skip, duplicate-id detection
├── theme.py         #   theme loader — TOML parsing + default merge + typed dataclasses
├── logger.py        #   loguru wrapper — colored terminal + file sink (1MB rotation)
└── ui/              #   PySide6 widgets (built from scratch)
    ├── app.py           App — QTimer + QThreadPool + source switching
    ├── float_widget.py  floating badge
    ├── info_panel.py    expandable info panel (paintEvent-drawn background)
    ├── chart_view.py    QPainter glucose curve (zone-colored)
    ├── tir_view.py      TIR progress bars
    └── settings_dialog.py settings dialog + adapter credential editor
adapter/             # pluggable data-source adapters (auto-discovered at startup)
├── sisensing.py     #   SiBionics CGM
└── nightscout.py    #   NightScout entries.json
themes/
└── default.toml     #   default theme (fallback for missing keys in user themes)
data/                #   runtime cache + adaptive metadata (gitignored)
└── <id>.json        #   entries + offset + phase + last_latest
```

**Data flow**: `adaptive-scheduling-timer` → `QThreadPool worker` → `adapter.fetch()` (on worker thread) → `Signal back to main thread` → `SGV.merge` → `adapter.save_cache` → `UI.update()`. Fetching happens off the main thread so the badge never freezes during network I/O.

**Adaptive scheduling**: on launch, poll every 20 s until a new reading arrives → wait 290 s → probe at 1 s × 10 → once a new reading lands, compute `offset` and enter steady state (scheduled at `server_time + 300 + offset + 5`). Calibration is persisted in `data/<id>.json` so restarts resume in steady state immediately.

**Direction mapping**: adapters provide NightScout direction strings (`DoubleUp`, `SingleUp`, `FortyFiveUp`, `Flat`, `FortyFiveDown`, `SingleDown`, `DoubleDown`). The UI maps these to arrows: ↑↑ ↑ ↗ → ↘ ↓ ↓↓. Unknown or missing directions render as →.
