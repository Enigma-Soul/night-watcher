# 0.1.2

### Chore(ci)

- CI 拆分为 build / release 两个 job
- build: 仅 PR 到 main 时运行，安装依赖 + 编译 exe + 存入缓存
- release: 仅 push 到 main 时运行，恢复缓存 exe + 解析 CHANGELOG + 发版，不安装任何依赖

### Refactor

- 缓存逻辑从 `libs/cache.py` 迁移至 `BaseAdapter`（per-adapter `data/<id>.json`）
- 自适应调度状态机内置 `BaseAdapter`
- 日志从 stdlib logging 切换到 loguru（彩色终端 + 1MB 文件轮转）
- 全量 Ruff format + lint 修复
- CLAUDE.md 重写为面向 Claude Code 的开发指南

# 0.1.0

### Feat(adapter)

- 硅基动感 (SiBionics/Sisensing) 关注者 API 适配器,含 Bearer token 认证与多区域 URL
- NightScout 兼容 API 适配器 (`entries.json`)
- 离线冒烟: Sisensing `mock_file` 本地 json,无需真实 token 即可端到端测试

### Feat(ui)

- 120×60 无边框置顶半透明圆角悬浮窗,左键拖拽 / 短按切换面板 / 右键菜单
- 260×280 信息面板:血糖值+趋势箭头+最后更新时间+1h/6h/12h/1d 时间按钮
- 折线/散点图 (QPainter 手绘):高/低参考虚线 + 按区间分段着色(低血糖红 / 正常绿 / 高血糖黄)
- TIR 三段进度条 (High / Range / Low)
- 设置对话框: GUI 偏好 (低/高警报线,单位,时间范围) + 数据源选择 + per-adapter 凭据编辑
- 右键菜单"刷新"强制拉取

### Feat(theme)

- `themes/` 目录 + `.toml` 主题文件,完整契约 (`MainTheme / PanelTheme / ChartTheme / TirTheme`)
- `libs/theme.py`: TOML 加载 + 递归默认值补全 + 类型化 `Theme` dataclass
- 设置对话框主题选择器,动态扫描 `themes/` 目录
- 所有颜色/不透明度/线宽/散点均经主题系统,支持运行时换肤

### Feat(schedule)

- 智能拉取调度: `BaseAdapter.poll_interval_seconds` 契约 + 数据点间隔众数 + 5 秒缓冲
- 单次定时器动态计算下次拉取时间,失败 60 秒重试,stale 数据下限 30 秒防 tight loop

### Fix(adapter)

- Sisensing `timeout` 类型转换:设置对话框写字符串 `"10"`,适配器漏 `int()`→ urllib3 拒绝→fetch 永远失败
- Sisensing 直连绕过系统代理 (`trust_env=False`):CN 域名 `api.sisensing.com` 走 Clash 境外节点偶发停滞
- NightScout / Sisensing 适配器统一添加 `poll_interval_seconds = 300` 到适配器契约

### Fix(ui)

- 设置对话框数值字段 (`timeout` / `retries` / `count`) 写字符串 → 加 `_INT_FIELDS` 转 `int`,空值跳过,非法值阻断
- 信息面板 `paintEvent` 手绘圆角半透明背景(替换 `WA_TranslucentBackground` + stylesheet 不渲染的 Qt bug)
- 面板拖拽随主窗移动 (`on_moved` 回调)
- 数据面板跟随主窗移动: `FloatWidget.mouseMoveEvent` 每次 `self.move()` 后触发 `on_moved`

### Feat(project)

- `uv` 包管理 + Python 3.12+
- GitHub Actions CI: 导入检查 + PyInstaller 打包 + 自动读取 CHANGELOG.md 发版
- 分支保护: `main` 只接收 PR,开发在 `develop`
