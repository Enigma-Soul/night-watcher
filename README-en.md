# NightWatcher

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-GPLv3-blue?style=flat-square)](./LICENSE)

English | [简体中文](README.md)

A desktop glucose monitor that pulls CGM data from modular adapters — SiBionics, NightScout, or your own source — and displays it as a stay-on-top floating widget. Only adapters make network requests; the core library and UI never touch the network.

**PySide6** + **requests**, managed with **uv**.

## Features

- **Floating widget** — 120×60 frameless, always-on-top, semi-transparent badge showing current glucose and trend arrow. Drag anywhere on screen.
- **Info panel** — tap the badge to expand a 260×260 panel with a glucose curve (1/6/12/24 h), TIR (Time-in-Range) progress bars, and last-updated timestamp.
- **Drag-and-drop adapters** — drop a `.py` into `adapter/` and it's loaded automatically on next launch. Files prefixed with `_` are skipped.
- **Multi-source switching** — right-click menu or settings dialog to switch between data sources. Each adapter has its own configuration block in `config.json`.
- **Network isolation** — only adapter files make HTTP requests. The core library (`libs/`), UI, config, cache, and data layer never touch the network.
- **Offline resilience** — historical entries are cached in `cache.json`. Restart without a network and the widget displays cached data immediately.
- **Clean config separation** — `config.json` stores credentials and GUI preferences only. Blood glucose data lives in a separate cache file. No more 271 KB config bloat.

## Quick Start

```bash
git clone <repo-url> && cd night-watcher
uv sync
cp config.example.json config.json    # edit to fill in your credentials
uv run python main.py
```

> [!NOTE]
> `config.json` and `cache.json` are gitignored — they contain credentials and personal health data.

## Configuration

`config.json` holds GUI preferences and per-adapter credentials. Start from `config.example.json`:

```json
{
  "gui": {
    "low_line": 72, "high_line": 180, "max": 270,
    "color_scheme": 0,
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

**GUI fields** — `low_line` / `high_line` / `max` are stored in **mg/dL** internally; `unit` only controls display (`"mmol/L"` or `"mg/dL"`). `time_range` accepts `1 | 6 | 12 | 24` hours. `active_adapter` sets the default data source on startup.

**Adapter fields** — each adapter reads its own config block from `config["adapter"][<id>]`. Key names are adapter-defined (see built-in adapters below for their defaults).

> [!TIP]
> **Testing without real credentials**: set `sisensing.mock_file` to a local JSON dump of the SiBionics API response. The adapter runs the full parse pipeline without making any HTTP request — great for verifying the UI and data pipeline quickly.

## Built-in Adapters

### SiBionics (`sisensing`)

Follower-mode CGM data from `https://api.sisensing.com/follow/app/follow/myself/glucose/details/devices`.

| Config key | Description |
|---|---|
| `ss_token` | Bearer token (UUID format, obtained via packet capture) |
| `ss_region` | `"CN"` (verified) or `"EU"` (unvalidated) |
| `timeout` | Request timeout in seconds |
| `retries` | Number of retry attempts on failure |
| `mock_file` | Path to a local JSON dump for offline testing (empty = real HTTP) |

Converts `glucoseInfos[].v` from mmol/L to mg/dL (×18.018) and maps the `s` direction field to NightScout arrow names. Automatically skips expired devices that have empty `glucoseInfos`.

### NightScout (`nightscout`)

Pulls from any NightScout instance's `entries.json` endpoint. Data is already in NightScout format, so the adapter forwards it with minimal normalization.

| Config key | Description |
|---|---|
| `ns_url` | Base URL of the NightScout instance |
| `api_secret` | API secret (optional, sent as `api-secret` header) |
| `count` | Number of entries per request (default 288, roughly one day at 5-min intervals) |

## Writing Your Own Adapter

Create a `.py` file in `adapter/` that subclasses `BaseAdapter`:

```python
from libs.base_adapter import BaseAdapter, FetchError

class MyAdapter(BaseAdapter):
    id = "my_source"       # unique identifier — matches config["adapter"] key
    name = "My CGM Source" # display name in menus

    def is_configured(self) -> bool:
        # check whether the minimum config is present (e.g., token/url filled in)
        return bool(self.config.get("api_key"))

    def fetch(self) -> list[dict]:
        # Return entries in this format:
        #   [{"date": int(ms), "sgv": int(mg/dL), "direction": str}, ...]
        # Raise FetchError on failure.
        # Don't deduplicate or sort — SGV.merge handles that.
        ...
```

**Loading rules:**
- Files named with a leading `_` (e.g. `_wip.py`, `__init__.py`) are skipped.
- Every other `.py` is imported and scanned for `BaseAdapter` subclasses.
- If two adapters share the same `id`, the app shows an error dialog and exits.
- Add a matching config block under `config["adapter"]["<id>"]` in `config.json`.

> [!WARNING]
> Only adapter files may make network requests. The core library, UI, config, and cache layer must remain network-free. An adapter *may* optionally upload to NightScout inside its `fetch()` method, but that is not a project requirement — it's purely an adapter-level decision.

## Architecture

```
main.py              # sole entry point — orchestrates startup and owns the event loop
libs/                # core library (fixed files, not auto-discovered)
├── config.py        #   Config — atomic JSON read/write, defaults on corruption
├── cache.py         #   Cache — partitioned cache.json per adapter id
├── sgv.py           #   SGV — flat entry list, merge-by-date dedup, TIR stats
├── base_adapter.py  #   BaseAdapter + FetchError — adapter contract
├── adapter_loader.py#   importlib scanner — _-prefix skip, duplicate-id detection
├── logger.py        #   stdlib logging with file + console handlers
└── ui/              #   PySide6 widgets (built from scratch)
    ├── app.py           App — QTimer + QThreadPool + source switching
    ├── float_widget.py  floating badge
    ├── info_panel.py    expandable info panel
    ├── chart_view.py    QPainter glucose curve
    ├── tir_view.py      TIR progress bars
    └── settings_dialog.py settings dialog + adapter credential editor
adapter/             # pluggable data-source adapters (auto-discovered at startup)
├── sisensing.py     #   SiBionics CGM → internal format
└── nightscout.py    #   NightScout entries.json → internal format
```

**Data flow**: `QTimer[(2 min)]` → `QThreadPool worker` → `adapter.fetch()` (on worker thread) → `Signal back to main thread` → `SGV.merge` → `Cache.save` → `UI.update()`. Fetching happens off the main thread so the widget never freezes during network I/O.

**Direction mapping**: adapters provide NightScout direction strings (`DoubleUp`, `SingleUp`, `FortyFiveUp`, `Flat`, `FortyFiveDown`, `SingleDown`, `DoubleDown`). The UI maps these to arrows: ↑↑ ↑ ↗ → ↘ ↓ ↓↓. Unknown or missing directions render as →.
