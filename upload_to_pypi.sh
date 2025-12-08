#!/bin/bash
# 临时 PyPI 上传脚本

set -e

echo "=== 直接发布到 PyPI ==="
echo ""

# 检查分发包
if [ ! -f "dist/pyapollo_zenkilan-0.2.0.tar.gz" ] || [ ! -f "dist/pyapollo_zenkilan-0.2.0-py3-none-any.whl" ]; then
    echo "❌ 错误: 分发包不存在"
    exit 1
fi

echo "📦 找到分发包:"
ls -la dist/
echo ""

echo "🔐 请提供你的 PyPI API token (从 https://pypi.org/manage/account/token/ 获取)"
echo "Token 格式类似: pypi-AgEIcHlwaS5vcmc..."
echo ""

# 读取 token
read -s -p "输入你的 PyPI API token: " token
echo ""

if [ -z "$token" ]; then
    echo "❌ 错误: API token 不能为空"
    exit 1
fi

echo "🔄 设置环境变量..."
export TWINE_USERNAME=__token__
export TWINE_PASSWORD="$token"

echo "📤 正在上传到 PyPI..."
if twine upload dist/*; then
    echo ""
    echo "🎉 成功发布到 PyPI!"
    echo "📦 安装方式: pip install pyapollo"
    echo "🏠 项目主页: https://pypi.org/project/pyapollo/"
else
    echo ""
    echo "❌ 上传失败，请检查 API token 是否正确"
    echo "💡 提示: 确保 token 格式正确且有发布权限"
fi