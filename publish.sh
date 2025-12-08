#!/bin/bash
# PyPI 发布脚本

set -e

echo "=== PyApollo PyPI 发布脚本 ==="
echo ""

# 检查环境变量
if [ -z "$TWINE_USERNAME" ]; then
    echo "错误: 请设置 TWINE_USERNAME 环境变量"
    echo "export TWINE_USERNAME=__token__"
    exit 1
fi

if [ -z "$TWINE_PASSWORD" ]; then
    echo "错误: 请设置 TWINE_PASSWORD 环境变量 (你的 PyPI API token)"
    echo "export TWINE_PASSWORD=你的_API_token"
    exit 1
fi

# 检查分发包是否存在
if [ ! -f "dist/pyapollo-0.2.0.tar.gz" ] || [ ! -f "dist/pyapollo-0.2.0-py3-none-any.whl" ]; then
    echo "错误: 分发包不存在，请先运行 'python -m build'"
    exit 1
fi

echo "选择发布目标:"
echo "1) Test PyPI (测试环境，推荐先试用)"
echo "2) PyPI (正式发布)"
read -p "请输入选择 (1 或 2): " choice

case $choice in
    1)
        echo "正在上传到 Test PyPI..."
        twine upload --repository testpypi dist/*
        echo ""
        echo "✅ 成功上传到 Test PyPI!"
        echo "测试安装: pip install --index-url https://test.pypi.org/simple/ pyapollo"
        ;;
    2)
        echo "⚠️  即将上传到正式 PyPI，这将公开你的包！"
        read -p "确认要继续吗？(y/N): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            echo "正在上传到 PyPI..."
            twine upload dist/*
            echo ""
            echo "🎉 成功发布到 PyPI!"
            echo "安装方式: pip install pyapollo"
        else
            echo "已取消发布"
        fi
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac