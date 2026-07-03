# NightWatcher

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![CI](https://img.shields.io/github/actions/workflow/status/Enigma-Soul/night-watcher/ci.yml?style=flat-square&label=CI)](https://github.com/Enigma-Soul/night-watcher/actions)
[![License](https://img.shields.io/badge/License-GPLv3-blue?style=flat-square)](./LICENSE)

[English](README-en.md) | 简体中文

桌面 CGM 血糖悬浮小部件。通过可插拔的 adapter 拉取多源血糖数据（硅基动感、NightScout、或自写数据源），以无边框置顶半透明悬浮窗实时显示数值与趋势。

**PySide6** + **requests** + **loguru**，用 **uv** 管理依赖，**Ruff** 统一格式。

## 特性

- **悬浮窗** — 120×60 无边框置顶圆角半透明窗，显示当前血糖与趋势箭头，可拖拽任意位置。
- **信息面板** — 点击悬浮窗展开 260×280 面板，含 1/6/12/24h 血糖曲线、TIR 进度条、最后更新时间。
- **按区间着色曲线** — 折线与散点按血糖阈值自动换色：低（红）/ 正常（绿）/ 高（黄）。
- **拖拽式 adapter** — 把 `.py` 丢进 `adapter/` 下次启动自动加载，文件名以 `_` 开头则跳过。
- **自适应拉取调度** — 根据数据点间隔众数自动校准服务器-客户端时差，避免"等太久"或"轮询过密"。
- **主题系统** — `themes/*.toml` 完整契约（主窗/面板/图表/TIR），设置对话框动态切换。
- **多数据源切换** — 右键菜单或设置对话框切换，每个 adapter 在 `config.json` 中有独立配置块。
- **网络隔离** — 仅 adapter 发起 HTTP 请求；核心库、UI、配置、缓存层均不联网。
- **离线可用** — 缓存于 `data/<id>.json`，断网重启后直接显示缓存数据。

## 快速开始

```bash
git clone <repo-url> && cd night-watcher
uv sync
cp config.example.json config.json    # 编辑填入凭据
uv run python main.py
```

> [!NOTE]
> `config.json` 与 `data/` 均已被 gitignore —— 分别含凭据与个人血糖数据，切勿提交入库。

## 配置

`config.json` 存 GUI 偏好与各 adapter 凭据。从 `config.example.json` 复制后编辑：

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

**GUI 字段**：
- `low_line` / `high_line` / `max` 内部以 **mg/dL** 存储；`unit` 仅控制显示。
- `theme` 选择 `themes/` 下的主题名。
- `time_range` 合法值 `1 | 6 | 12 | 24`（小时）。

**Adapter 字段**：每个 adapter 从 `config["adapter"][<id>]` 读取自身配置。字段名由 adapter 自行定义。

> [!TIP]
> **无真实凭据也能跑**：把 `sisensing.mock_file` 设为本地硅基 API 抓包 JSON 路径，adapter 走完整解析但完全不联网。适合快速验证 UI 与数据管线。

## 主题

`themes/*.toml` 是完整的主题契约：

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

用户主题只需写要覆盖的键；缺失键自动以 `default.toml` 补足。

## 内置 Adapter

### 硅基动感 (`sisensing`)

从硅基 API 关注者模式拉取：`https://api.sisensing.com/follow/app/follow/myself/glucose/details/devices`

| 配置键 | 说明 |
|---|---|
| `ss_token` | Bearer token（UUID 格式，需抓包获取） |
| `ss_region` | `"CN"`（已验证）或 `"EU"`（未验证） |
| `timeout` | 请求超时（秒） |
| `retries` | 失败重试次数 |
| `mock_file` | 本地 JSON 路径，填写后走离线解析（空字符串 = 真实 HTTP） |

解析 `glucoseInfos[].v` 从 mmol/L 转 mg/dL（×18.018），将 `s` 字段映射为 NightScout 方向名。自动跳过 `glucoseInfos` 为空的过期设备。

### NightScout (`nightscout`)

从任意 NightScout 实例的 `entries.json` 拉取。数据本身已是 NightScout 格式，adapter 仅做最小标准化后直通。

| 配置键 | 说明 |
|---|---|
| `ns_url` | NightScout 实例基地址 |
| `api_secret` | API 密钥（可选，以 `api-secret` 请求头发出） |
| `count` | 每次拉取条目数（默认 288，约一天 5 分钟点的量） |

## 编写自己的 Adapter

在 `adapter/` 下新建 `.py`，继承 `BaseAdapter`：

```python
from libs.base_adapter import BaseAdapter, FetchError

class MyAdapter(BaseAdapter):
    id = "my_source"        # 唯一标识，对应 config["adapter"] 的 key
    name = "我的 CGM 源"
    poll_interval_seconds = 300  # 数据发布间隔（秒）

    def is_configured(self) -> bool:
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

> [!WARNING]
> 仅 adapter 文件可发起网络请求。核心库、UI、配置、缓存层禁止联网。adapter **可以**在 `fetch()` 内顺便上传 NightScout，但这不属于项目核心功能。

## 开发

```bash
# 安装依赖
uv sync

# 启动应用
uv run python main.py

# 代码格式化
uv run ruff format .

# 静态检查
uv run ruff check .
```

### 代码规范

- **Ruff** 统一 lint 与格式化，配置见 `pyproject.toml`：`line-length = 100`，目标 Python 3.12+，启用 `E/F/I/N/W/UP` 规则。
- **注释中文**，commit message 中文。
- **绝对导入**：adapter 文件用 `from libs.base_adapter import BaseAdapter`，不用相对导入。
- **不随意引入依赖**：目前依赖锁定 `PySide6` + `requests` + `loguru`，新增前先在 issue 讨论。

### 目录约定

| 路径 | 职责 |
|------|------|
| `main.py` | 唯一入口 |
| `libs/` | 核心库（固定文件，不自动扫描） |
| `libs/ui/` | PySide6 组件 |
| `adapter/` | 可插拔数据源转接头（启动时自动扫描） |
| `themes/` | 主题 `.toml` 文件 |
| `data/` | 运行时缓存与自适应元数据（gitignored） |
| `config.json` | 凭据与 GUI 偏好（gitignored） |

### 提交规范

项目遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat(scope): 简短描述
fix(scope): 简短描述
chore: 简短描述
```

分支模型：`main` 受保护，只接受 PR；开发在 `develop` 进行。

## CI 与发版

GitHub Actions 自动处理：

- **check**（每次 push/PR）：`uv sync` + 核心模块导入检查。
- **build-and-release**（push 到 `main` 时）：`pyinstaller --onefile` 打包 → 解析 `CHANGELOG.md` 首行版本 → 创建 GitHub Release + 附加 `night-watcher.exe`。

工作流：

1. 在 `develop` 分支开发、提交、push。
2. 创建 `develop → main` 的 PR。
3. PR 合并后，CI 自动打包、读 `CHANGELOG.md`、创建带 `v{version}` tag 的 Release。

## 架构

```
main.py              # 唯一入口，编排启动顺序与事件循环
libs/
├── config.py        #   Config — 原子 JSON 读写，损坏时备份并写默认值
├── sgv.py           #   SGV — 扁平列表存血糖条目，按 date 去重，TIR 统计
├── base_adapter.py  #   BaseAdapter + FetchError + 自适应调度状态机
├── adapter_loader.py#   importlib 扫描器 — _前缀跳过、id 重复检测
├── theme.py         #   主题加载 — TOML 解析 + 默认值合并 + 类型化 dataclass
├── logger.py        #   loguru 封装 — 彩色终端 + 文件落地(1MB 轮转)
└── ui/              #   PySide6 组件（全新重写）
    ├── app.py           App — QTimer + QThreadPool + 数据源切换
    ├── float_widget.py  悬浮窗
    ├── info_panel.py    展开信息面板（paintEvent 手绘背景）
    ├── chart_view.py    QPainter 血糖曲线（按区间着色）
    ├── tir_view.py      TIR 进度条
    └── settings_dialog.py 设置对话框 + adapter 凭据编辑
adapter/             # 可插拔数据源转接头（启动时自动扫描）
├── sisensing.py     #   硅基动感 API
└── nightscout.py    #   NightScout entries.json
themes/
└── default.toml     #   默认主题（其余 .toml 缺失键的兜底）
data/                #   运行时缓存与自适应元数据（gitignored）
└── <id>.json        #   entries + offset + phase + last_latest
```

**数据流**：`adaptive-scheduling-timer` → `QThreadPool worker` → `adapter.fetch()`（子线程）→ `Signal 回主线程` → `SGV.merge` → `adapter.save_cache` → `UI.update()`。拉取全程在子线程，悬浮窗交互绝不卡顿。

**自适应调度**：启动时 20 秒轮询发现新数据 → 进入 290 秒等待 → 1 秒 ×10 探测窗口 → 得到 offset 后进入 steady（按 `server_time + 300 + offset + 5` 对齐）。校准结果写入 `data/<id>.json`，重启立即恢复。

**方向映射**：adapter 输出 NightScout 方向字符串（`DoubleUp`、`SingleUp`、`FortyFiveUp`、`Flat`、`FortyFiveDown`、`SingleDown`、`DoubleDown`），UI 映射为 ↑↑ ↑ ↗ → ↘ ↓ ↓↓。未知或缺失显示 →。
