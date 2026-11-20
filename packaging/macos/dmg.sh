#!/usr/bin/env bash
# macOS 安装包制作：PyInstaller .app → .dmg（打包 spec §5.5）。
#
# 输入：dist/text2sql-agent.app（先 `.venv/bin/python -m PyInstaller text2sql.spec
#       --noconfirm` 构建；BUNDLE 名见 text2sql.spec）。
# 输出：dist/text2sql-agent-<version>-macos-arm64.dmg（Applications 拖拽安装布局，
#       卷内含 README_FIRST_RUN.txt 首跑说明）。
#
# 依赖：create-dmg ≥ 1.3.0（brew install create-dmg；1.3.0 起 --add-file 为
#       四参形式 <卷内名> <源文件> <x> <y>）。仅可在 macOS 上运行。
# 用法（仓库根或任意目录均可）：
#   bash packaging/macos/dmg.sh              # 版本默认 1.0.0
#   bash packaging/macos/dmg.sh 1.2.3        # 位置参数指定版本
#   VERSION=1.2.3 bash packaging/macos/dmg.sh
# 版本优先级：位置参数 > VERSION 环境变量 > 仓库根 VERSION 文件（若有）> 1.0.0。
# CI（Task 6，macos-latest arm64）：brew install create-dmg 后直接调用本脚本。
#
# 注意：v1 不签名/不公证，用户首次打开需右键→打开绕过 Gatekeeper
# （详见 packaging/README_FIRST_RUN.txt）。文件名假定 arm64 构建
# （CI macos-latest＝Apple Silicon；Intel Mac 支持留后续）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- 版本解析：位置参数 > 环境变量 > VERSION 文件 > 默认 1.0.0 ---
VERSION="${1:-${VERSION:-}}"
if [[ -z "$VERSION" && -f "$PROJECT_ROOT/VERSION" ]]; then
    VERSION="$(tr -d '[:space:]' < "$PROJECT_ROOT/VERSION")"
fi
VERSION="${VERSION:-1.0.0}"

APP_NAME="text2sql-agent.app"
APP_PATH="$PROJECT_ROOT/dist/$APP_NAME"
DMG_PATH="$PROJECT_ROOT/dist/text2sql-agent-${VERSION}-macos-arm64.dmg"
README_PATH="$SCRIPT_DIR/../README_FIRST_RUN.txt"

# --- 前置检查（缺工具/缺产物时给出可操作的错误信息）---
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "错误：dmg 只能在 macOS 上制作（当前：$(uname -s)）。" >&2
    exit 1
fi
if ! command -v create-dmg >/dev/null 2>&1; then
    echo "错误：未找到 create-dmg。请先安装：brew install create-dmg" >&2
    exit 1
fi
if [[ ! -d "$APP_PATH" ]]; then
    echo "错误：未找到 $APP_PATH" >&2
    echo "请先构建：.venv/bin/python -m PyInstaller text2sql.spec --noconfirm" >&2
    exit 1
fi
if [[ ! -f "$README_PATH" ]]; then
    echo "错误：未找到首跑说明 $README_PATH" >&2
    exit 1
fi

# 架构提示（仅告警不阻断）：文件名标 arm64，若产物非 arm64 提醒核对构建机。
if command -v lipo >/dev/null 2>&1; then
    APP_ARCHS="$(lipo -archs "$APP_PATH/Contents/MacOS/text2sql-agent" 2>/dev/null || true)"
    if [[ -n "$APP_ARCHS" && "$APP_ARCHS" != *arm64* ]]; then
        echo "警告：.app 架构为 [$APP_ARCHS]，与文件名 macos-arm64 不符，请核对构建机。" >&2
    fi
fi

# create-dmg 拒绝覆盖已存在的输出文件，先清理旧产物与失败残留的读写中间镜像。
rm -f "$DMG_PATH" "$PROJECT_ROOT/dist/"rw.*.text2sql-agent-*.dmg

echo "制作 dmg：$APP_NAME → ${DMG_PATH}（版本 ${VERSION}）"
# 布局：左侧 .app 图标，右侧 Applications 拖拽链接，底部居中首跑说明。
# --no-internet-enable：跳过已废弃的 internet-enable 标记步骤。
# --format UDZO：zlib 压缩（兼容性与速度均衡；约 550MB 包体压缩后显著缩小）。
CREATE_DMG_ARGS=(
    --volname "text2sql-agent $VERSION"
    --window-size 660 420
    --icon-size 96
    --icon "$APP_NAME" 165 180
    --app-drop-link 495 180
    --add-file "README_FIRST_RUN.txt" "$README_PATH" 330 330
    --no-internet-enable
    --format UDZO
)
if ! create-dmg "${CREATE_DMG_ARGS[@]}" "$DMG_PATH" "$APP_PATH"; then
    # Finder 美化 AppleScript 偶发超时（-1712），无 GUI/CI 环境尤甚。
    # 回退 --skip-jenkins：跳过图标位置/窗口尺寸美化，Applications 拖拽
    # 链接与卷内容（.app + README）不变，安装功能不受影响。
    echo "警告：create-dmg 完整布局失败（多为 Finder AppleScript 超时 -1712）。" >&2
    echo "      以 --skip-jenkins 重试：跳过 Finder 美化，卷内容与拖拽安装不变。" >&2
    rm -f "$DMG_PATH" "$PROJECT_ROOT/dist/"rw.*.text2sql-agent-*.dmg
    create-dmg --skip-jenkins "${CREATE_DMG_ARGS[@]}" "$DMG_PATH" "$APP_PATH"
fi

if [[ ! -f "$DMG_PATH" ]]; then
    echo "错误：create-dmg 未产出 $DMG_PATH" >&2
    exit 1
fi
echo "完成：${DMG_PATH}（$(du -h "$DMG_PATH" | cut -f1)）"
echo "验证：hdiutil attach \"$DMG_PATH\" 后应见 ${APP_NAME}、Applications 链接与 README_FIRST_RUN.txt。"
