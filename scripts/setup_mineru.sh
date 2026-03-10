#!/bin/bash
# MinerU 初始化脚本 - ModelScope 创空间
# 使用方法: bash scripts/setup_mineru.sh

set -e

echo "=========================================="
echo "MinerU 初始化脚本"
echo "=========================================="

# 配置路径
MODELS_DIR="/mnt/workspace/models/MinerU"
CONFIG_FILE="/mnt/workspace/.magic-pdf.json"
CACHE_DIR="/mnt/workspace/.cache/modelscope"

# 1. 创建目录
echo "[1/4] 创建模型目录..."
mkdir -p "$MODELS_DIR"
mkdir -p "$CACHE_DIR"

# 2. 创建配置文件
echo "[2/4] 创建 magic-pdf.json 配置文件..."
cat > "$CONFIG_FILE" << 'EOF'
{
  "models-dir": "/mnt/workspace/models/MinerU",
  "device-mode": "cpu"
}
EOF
echo "配置文件已创建: $CONFIG_FILE"

# 3. 设置环境变量提示
echo "[3/4] 环境变量配置提示"
echo "请在 ModelScope 创空间设置以下环境变量:"
echo "  - MINERU_TOOLS_CONFIG_JSON=$CONFIG_FILE"
echo "  - MODELSCOPE_CACHE=$CACHE_DIR"
echo "  - PARSER_BACKEND=mineru"

# 4. 下载模型
echo "[4/4] 下载 MinerU 模型 (约 3GB，需要几分钟)..."
echo "开始下载..."

# 检查是否有 mineru-models-download 命令
if command -v mineru-models-download &> /dev/null; then
    mineru-models-download
    echo "✓ 模型下载完成"
else
    echo "⚠ 未找到 mineru-models-download 命令"
    echo "请先安装: pip install mineru[all]"
    echo "然后手动执行: mineru-models-download"
fi

echo ""
echo "=========================================="
echo "✓ MinerU 初始化完成!"
echo "=========================================="
echo "模型目录: $MODELS_DIR"
echo "配置文件: $CONFIG_FILE"
echo ""
echo "请在创空间环境变量中添加:"
echo "  MINERU_TOOLS_CONFIG_JSON=$CONFIG_FILE"
echo "  PARSER_BACKEND=mineru"
