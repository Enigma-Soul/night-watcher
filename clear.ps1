<#
.SYNOPSIS
    清理 night-watcher 的构建中间文件与运行时临时产物。

.DESCRIPTION
    默认清理：PyInstaller 产物 (build/ dist/)、Python 字节码缓存 (__pycache__/ *.pyc)、
    Ruff 缓存 (.ruff_cache/)、运行日志 (log.log)、原子写残留 (*.tmp)、损坏备份 (*.bad)、
    旧版遗留缓存 (cache.json)。
    -All         额外清理运行时血糖缓存 (data/)。
    -DryRun      仅预览不删除。
    始终跳过 .venv / .git / .idea / .claude / .github，绝不清 config.json（凭据）与源码。

.EXAMPLE
    pwsh clear.ps1 -DryRun     # 预览将清理的内容
    pwsh clear.ps1             # 执行清理
    pwsh clear.ps1 -All        # 连 data/ 运行时缓存一并清理
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$All
)

$ErrorActionPreference = 'SilentlyContinue'
$root = $PSScriptRoot

# 强制 UTF-8 输出：避免在 GBK 控制台或被外部捕获时中文乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 虚拟环境 / 版本控制 / IDE 目录，递归清理时一律跳过
$skipPatterns = '\.venv\\', '\.git\\', '\.idea\\', '\.claude\\', '\.github\\'

function Test-Skipped([string]$path) {
    foreach ($p in $skipPatterns) {
        if ($path -match $p) { return $true }
    }
    return $false
}

function Remove-Path([string]$path, [string]$label) {
    if (-not (Test-Path $path)) { return 0 }
    $size = (Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum).Sum
    if ($DryRun) {
        Write-Host "  [DRY] $label : $path" -ForegroundColor Yellow
    } else {
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK]   $label : $path" -ForegroundColor Green
    }
    return [int64]$size
}

$total = [int64]0

Write-Host "`n=== PyInstaller 产物 ===" -ForegroundColor Cyan
foreach ($d in 'build', 'dist') {
    $total += Remove-Path (Join-Path $root $d) $d
}

Write-Host "`n=== Python 字节码缓存 ===" -ForegroundColor Cyan
Get-ChildItem -Path $root -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue |
    Where-Object { -not (Test-Skipped $_.FullName) } |
    ForEach-Object { $total += Remove-Path $_.FullName '__pycache__' }

# *.pyc 散落文件（__pycache__ 已清，但兜底扫一遍）
Get-ChildItem -Path $root -Recurse -File -Filter *.pyc -ErrorAction SilentlyContinue |
    Where-Object { -not (Test-Skipped $_.FullName) } |
    ForEach-Object { $total += Remove-Path $_.FullName '*.pyc' }

Write-Host "`n=== 工具缓存 ===" -ForegroundColor Cyan
$total += Remove-Path (Join-Path $root '.ruff_cache') '.ruff_cache'

Write-Host "`n=== 运行时临时文件 ===" -ForegroundColor Cyan
# log.log / cache.json（旧 libs/cache.py 遗留，已被 data/ 取代）/ 原子写残留 / 损坏备份
foreach ($name in 'log.log', 'cache.json') {
    $p = Join-Path $root $name
    if (Test-Path $p) { $total += Remove-Path $p $name }
}
Get-ChildItem -Path $root -Recurse -File -Include *.tmp, *.bad -ErrorAction SilentlyContinue |
    Where-Object { -not (Test-Skipped $_.FullName) } |
    ForEach-Object { $total += Remove-Path $_.FullName $_.Name }

if ($All) {
    Write-Host "`n=== 运行时血糖缓存 (-All) ===" -ForegroundColor Cyan
    $total += Remove-Path (Join-Path $root 'data') 'data'
} else {
    Write-Host "`n(跳过 data/ 运行时缓存，加 -All 一并清理)" -ForegroundColor DarkGray
}

$mb = if ($total -gt 0) { '{0:N1}' -f ($total / 1MB) } else { '0.0' }
$mode = if ($DryRun) { '预览（未删除）' } else { '已清理' }
Write-Host "`n=== 完成：$mode，共 $mb MB ===" -ForegroundColor Cyan
