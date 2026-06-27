#!/bin/bash
# 快速启动脚本

echo "=========================================="
echo "小说创作Agent系统 - 启动脚本"
echo "=========================================="

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装 Python 3.10+"
    exit 1
fi

# 检查Node.js是否安装
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装 Node.js 16+"
    exit 1
fi

echo "✅ 环境检查通过"

# 创建.env文件（如果不存在）
if [ ! -f .env ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "🐍 创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 安装Python依赖（如果需要）
echo "📦 检查 Python 依赖..."
pip install -e .

# 安装Node依赖（如果需要）
if [ ! -d "node_modules" ]; then
    echo "📦 安装 Node.js 依赖..."
    npm install
fi

echo ""
echo "🚀 系统准备完成！"
echo ""
echo "请使用以下命令启动服务："
echo "  后端: python run.py"
echo "  前端: npm run dev"
echo ""
echo "或者在两个终端窗口中分别运行"
echo ""
