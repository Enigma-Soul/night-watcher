# NightWatcher

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-GPLv3-blue?style=flat-square)](./LICENSE)

[English](README-en.md) | 简体中文

桌面血糖悬浮小部件。通过模块化 adapter 拉取多源 CGM 数据（硅基动感、NightScout、或自写数据源），以置顶层半透明悬浮窗展示血糖值与趋势。仅 adapter 联网，核心库与 UI 永不发起网络请求。

**PySide6** + **requests**，用 **uv** 管理依赖。

## 特性

- **悬浮窗** — 120×60 无边框置顶层圆角半透明窗，显示当前血糖值和趋势箭头，可拖拽到屏幕任意位置。
- **信息面板** — 点击悬浮窗展开 260×260 面板，含 1/6/12/24 小时血糖曲线、TIR（目标范围内时间）进度条、最后更新时间。
- **拖拽式 adapter** — 把 `.py` 文件放入 `adapter/` 目录，下次启动即自动加载。文件名以 `_` 开头则跳过。
- **多数据源切换** — 右键菜单或设置对话框切换当前数据源，每个 adapter 在 `config.json` 中拥有独立配置块。
- **网络隔离** — 仅 adapter 文件发起 HTTP 请求。核心库（`libs/`）、UI、配置读写、缓存层均不联网。
- **离线可用** — 历史数据缓存于 `cache.json`。断网重启后悬浮窗直接显示缓存数据，不等网络。
- **配置分离** — `config.json` 只存凭据与 GUI 偏好，血糖数据放入独立的缓存文件。告别旧版 271KB 的臃肿配置。

## 快速开始

```bash
git clone <仓库地址> && cd night-watcher
uv sync
cp config.example.json config.json    # 编辑填入凭据
uv run python main.py
```

> [!NOTE]
> `config.json` 与 `cache.json` 已被 gitignore —— 它们分别包含凭据和个人血糖数据，切勿提交入库。

## 配置

`config.json` 含 GUI 偏好与各 adapter 凭据。从 `config.example.json` 复制后编辑：

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
      "ss_token": "你的-token",
      "ss_region": "CN",
      "timeout": 10,
      "retries": 3,
      "mock_file": ""
    },
    "nightscout": {
      "ns_url": "https://your-ns.example.com",
      "api_secret": "你的-api-secret",
      "count": 288
    }
  }
}
```

**GUI 字段** — `low_line` / `high_line` / `max` 内部以 **mg/dL** 存储；`unit` 仅控制显示（`"mmol/L"` 或 `"mg/dL"`）。`time_range` 合法值 `1 | 6 | 12 | 24`（小时）。`active_adapter` 指定启动时默认使用的数据源。

**Adapter 字段** — 每个 adapter 从 `config["adapter"][<id>]` 读取自身配置。字段名由 adapter 自行定义，见下方内置 adapter 说明。

> [!TIP]
> **无真实凭据也能跑**：把 `sisensing.mock_file` 设为本地硅基 API 抓包 JSON 路径，adapter 走完整解析流程但完全不联网。适合快速验证 UI 与数据管线。

## 内置 Adapter

### 硅基动感 (`sisensing`)

从硅基 API 关注者模式拉取全量历史数据：`https://api.sisensing.com/follow/app/follow/myself/glucose/details/devices`

| 配置键 | 说明 |
|---|---|
| `ss_token` | Bearer token（UUID 格式，需抓包获取） |
| `ss_region` | `"CN"`（已验证） 或 `"EU"`（未验证） |
| `timeout` | 请求超时（秒） |
| `retries` | 失败重试次数 |
| `mock_file` | 本地 JSON 路径，填写后走离线解析（空字符串 = 真实 HTTP） |

解析 `glucoseInfos[].v` 从 mmol/L 转为 mg/dL（×18.018），将 `s` 字段映射为 NightScout 方向名。自动跳过 `glucoseInfos` 为空的过期设备。

### NightScout (`nightscout`)

从任意 NightScout 实例的 `entries.json` 端点拉取。数据本身已是 NightScout 格式，adapter 仅做最小标准化后直通。

| 配置键 | 说明 |
|---|---|
| `ns_url` | NightScout 实例的基地址 |
| `api_secret` | API 密钥（可选，以 `api-secret` 请求头发出） |
| `count` | 每次拉取的条目数（默认 288，约一天 5 分钟点的量） |

## 编写自己的 Adapter

在 `adapter/` 下新建 `.py`，继承 `BaseAdapter`：

```python
from libs.base_adapter import BaseAdapter, FetchError

class MyAdapter(BaseAdapter):
    id = "my_source"       # 唯一标识，对应 config["adapter"] 的 key
    name = "我的 CGM 源"    # 菜单显示名

    def is_configured(self) -> bool:
        # 判断最小配置是否就绪（如 token/url 已填）
        return bool(self.config.get("api_key"))

    def fetch(self) -> list[dict]:
        # 返回统一格式：
        #   [{"date": int(ms), "sgv": int(mg/dL), "direction": str}, ...]
        # 失败抛 FetchError。不要在此去重或排序，交给 SGV.merge。
        ...
```

**加载规则：**
- 文件名以 `_` 开头的（如 `_wip.py`、`__init__.py`）跳过。
- 其余 `.py` 一律 import，扫描其中定义的 `BaseAdapter` 子类。
- 两个 adapter 类的 `id` 重复 → 启动时弹窗报错并退出。
- 在 `config.json` 的 `adapter` 下新建同名 id 的配置块以提供凭据。

> [!WARNING]
> 仅 adapter 文件可以发起网络请求。核心库、UI、配置读写、缓存层禁止联网。adapter **可以**在 `fetch()` 内部顺便上传 NightScout，但这不属于项目核心功能——完全由 adapter 自行决定。

## 架构

```
main.py              # 唯一入口，编排启动顺序与事件循环
libs/                # 核心库（固定文件，非自动扫描）
├── config.py        #   Config — 原子 JSON 读写，损坏时备份并写默认值
├── cache.py         #   Cache — 按 adapter id 分区的 cache.json 读写
├── sgv.py           #   SGV — 扁平列表存血糖条目，按 date 去重，TIR 统计
├── base_adapter.py  #   BaseAdapter + FetchError — adapter 抽象契约
├── adapter_loader.py#   importlib 扫描器 — _前缀跳过、id 重复检测
├── logger.py        #   stdlib logging 封装（文件 + 控制台双输出）
└── ui/              #   PySide6 组件（全新重写，未沿用旧代码）
    ├── app.py           App — QTimer + QThreadPool + 数据源切换
    ├── float_widget.py  悬浮窗
    ├── info_panel.py    展开信息面板
    ├── chart_view.py    QPainter 血糖曲线
    ├── tir_view.py      TIR 进度条
    └── settings_dialog.py 设置对话框 + adapter 凭据编辑
adapter/             # 可插拔数据源转接头（启动时自动扫描）
├── sisensing.py     #   硅基动感 API → 内部统一格式
└── nightscout.py    #   NightScout entries.json → 内部统一格式
```

**数据流**：`QTimer[(2 分钟)]` → `QThreadPool worker` → `adapter.fetch()`（子线程）→ `Signal 回主线程` → `SGV.merge` → `Cache.save` → `UI.update()`。拉取全程在子线程，悬浮窗交互绝不卡顿。

**方向映射**：adapter 输出 NightScout 方向字符串（`DoubleUp`、`SingleUp`、`FortyFiveUp`、`Flat`、`FortyFiveDown`、`SingleDown`、`DoubleDown`），UI 映射为箭头 ↑↑ ↑ ↗ → ↘ ↓ ↓↓。未知或缺失方向默认显示 →。
