# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 版本

当前版本：**0.1.6**（同步更新 `pyproject.toml` 和 `CHANGELOG.md`）

每次 push 前必须询问用户新版本号，并同时更新：
- `pyproject.toml` 的 `version` 字段
- `CHANGELOG.md` 顶部新增版本条目

## Commands

```bash
# 安装依赖
uv sync

# 启动应用
uv run python main.py

# 代码格式化（完成后必须执行）
uv run ruff format .

# 静态检查
uv run ruff check .

# 修复可自动修复的 lint 问题
uv run ruff check --fix .
```

## Git 工作流

- **`main` 受保护，禁止直接 push。** 所有开发在 `develop` 分支进行。
- 完成后创建 `develop → main` 的 PR。
- Commit message 使用中文，遵循 Conventional Commits（`feat(scope): 描述`、`fix(scope): 描述`）。
- **完成后必须运行 `uv run ruff format .` 格式化代码。**
- **每次功能改动后必须打包测试**，确保 PyInstaller 产物可正常启动：
  ```bash
  uv run pyinstaller --name night-watcher --noconsole --hidden-import requests --add-data "adapter;adapter" --add-data "themes;themes" main.py -y
  ```
  手动启动 `dist\night-watcher\night-watcher.exe` 确认无崩溃后，将 exe 进程终止。

## Architecture

桌面 CGM 血糖悬浮小部件。PySide6 + requests + loguru，uv 管理依赖。

**核心数据流：**
```
QTimer(自适应) → App.refresh() → QThreadPool._FetchWorker(子线程)
  → adapter.fetch() → Signal 回主线程 → SGV.merge → save_cache → update_ui()
```

网络请求只在 `adapter/` 内发起，核心库/UI/配置层禁止联网。

### Module Map

| 模块 | 职责 |
|------|------|
| `main.py` | 唯一入口：Config → logger → adapter_loader.scan → 实例化 → App.run() |
| `libs/config.py` | config.json 原子读写，损坏备份 .bad 后写默认值 |
| `libs/sgv.py` | 血糖 entries 内存存储，按 date 去重，TIR 统计 |
| `libs/base_adapter.py` | BaseAdapter ABC + FetchError + 自适应调度状态机 + 缓存 |
| `libs/adapter_loader.py` | importlib 扫描 adapter/，`_` 前缀跳过，id 重复/空检测 |
| `libs/theme.py` | themes/*.toml 加载，递归合并默认值，类型化 dataclass |
| `libs/logger.py` | loguru 封装：彩色终端 + 文件轮转(1MB) |
| `libs/ui/app.py` | 主控制器：QTimer + QThreadPool + 数据源切换 + UI 更新 |
| `libs/ui/float_widget.py` | 120×60 无边框置顶悬浮窗 |
| `libs/ui/info_panel.py` | 展开面板：血糖值+曲线+TIR |
| `libs/ui/chart_view.py` | QPainter 血糖曲线（按区间着色） |
| `libs/ui/tir_view.py` | TIR 三段进度条 |
| `libs/ui/settings_dialog.py` | 设置对话框 + adapter 凭据编辑 |
| `adapter/` | 可插拔数据源（启动时自动扫描） |

### Adapter 契约

`adapter/*.py` 继承 `BaseAdapter`，必须定义 `id`（str，唯一）和 `name`（str），实现 `fetch() -> list[dict]`。

返回格式：`[{"date": int(ms), "sgv": int(mg/dL), "direction": str}, ...]`

失败抛 `FetchError`。不要在 fetch 内去重或排序，交给 `SGV.merge`。

用绝对导入：`from libs.base_adapter import BaseAdapter, FetchError`

## Conventions

- **sgv 统一 mg/dL**：adapter 负责单位转换（如 mmol/L × 18.018），config 内 low/high/max 也是 mg/dL，unit 仅控制显示。
- **direction 用 NightScout 名**：`DoubleUp`/`SingleUp`/`FortyFiveUp`/`Flat`/`FortyFiveDown`/`SingleDown`/`DoubleDown`，UI 映射箭头。
- **原子写入**：Config 和 Cache 均先写 `.tmp` 再 `os.replace`。
- **缓存路径**：`data/<adapter_id>.json`（gitignored），存 entries + 自适应调度元数据。
- **注释中文**，代码内注释和 commit message 均用中文。
- **Ruff 配置**：`line-length = 100`，`target-version = "py312"`，启用 `E/F/I/N/W/UP` 规则。

## CI & Release

两个独立 workflow：
- **build.yml**（PR 到 `main`）：安装依赖 + PyInstaller 编译验证，不发版。
- **release.yml**（push 到 `main`）：安装依赖 + 编译 + 解析 `CHANGELOG.md` + 创建 GitHub Release。

工作流：`develop` 开发 → PR 到 `main`（触发 build 验证）→ 合并（触发 release 发版）。
