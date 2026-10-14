#!/bin/bash
# ==============================================================================
# iOS 27 Carrier & Lock Screen Suite - One-Click Launcher
# Supports macOS Finder double-click execution
# ==============================================================================

set -e

# Resolve the absolute path of this project directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================"
echo "  🚀 正在启动 iOS 27 锁屏运营商定制套件..."
echo "========================================================"
echo "项目目录: $DIR"

# 1. Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未检测到 Python 3。请先安装 Python 3 环境。"
    echo "按任意键退出..."
    read -n 1
    exit 1
fi

# 2. Build native helpers if missing
if [ ! -f "airlift/build/device_helper" ] || [ ! -f "airlift/build/airtraffic_host" ]; then
    echo "⚙️  正在初次编译本地辅助模块 (airlift/build)..."
    make -C airlift
    echo "✅ 辅助模块编译完成。"
fi

# 3. Launch Web GUI Dashboard
echo "🌐 正在启动可视化控制台并在浏览器打开..."
python3 tools/gui_server.py
