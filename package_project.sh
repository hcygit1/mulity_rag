#!/bin/bash

# AdaptiMultiRAG 项目打包脚本
# 用途：清理开发文件，生成轻量级分发包

set -e

PROJECT_NAME="AdaptiMultiRAG"
OUTPUT_DIR="dist"
ARCHIVE_NAME="${PROJECT_NAME}-$(date +%Y%m%d).tar.gz"

# 保存原始工作目录
ORIGINAL_DIR=$(pwd)

echo "=========================================="
echo "开始打包 ${PROJECT_NAME}"
echo "=========================================="

# 1. 创建临时目录
echo "[1/7] 创建临时目录..."
TEMP_DIR=$(mktemp -d)
cp -r . "${TEMP_DIR}/${PROJECT_NAME}"
cd "${TEMP_DIR}/${PROJECT_NAME}"

# 2. 清理后端文件
echo "[2/7] 清理后端文件..."
cd rag-backend

# 删除虚拟环境
rm -rf .venv

# 删除 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# 删除日志文件
rm -f lightrag.log
rm -f *.log

cd ..

# 3. 清理前端文件
echo "[3/7] 清理前端文件..."
cd rag-frontend

# 删除 node_modules
rm -rf node_modules

# 删除构建产物
rm -rf dist

cd ..

# 4. 清理根目录文件
echo "[4/7] 清理根目录文件..."

# 删除 macOS 文件
find . -name ".DS_Store" -delete

# 5. 返回临时目录的父目录
echo "[5/7] 创建压缩包..."
cd ..

# 6. 打包
tar -czf "${ARCHIVE_NAME}" "${PROJECT_NAME}"

# 7. 复制到原始项目目录
echo "[6/7] 复制到项目目录..."
mkdir -p "${ORIGINAL_DIR}/${OUTPUT_DIR}"
cp "${ARCHIVE_NAME}" "${ORIGINAL_DIR}/${OUTPUT_DIR}/"

# 计算文件大小
SIZE=$(du -h "${ORIGINAL_DIR}/${OUTPUT_DIR}/${ARCHIVE_NAME}" | cut -f1)

echo "[7/7] 清理临时文件..."
rm -rf "${TEMP_DIR}"

echo "=========================================="
echo "✅ 打包完成！"
echo "=========================================="
echo "输出文件: ${OUTPUT_DIR}/${ARCHIVE_NAME}"
echo "完整路径: ${ORIGINAL_DIR}/${OUTPUT_DIR}/${ARCHIVE_NAME}"
echo "文件大小: ${SIZE}"
echo ""
echo "解压命令: tar -xzf ${ARCHIVE_NAME}"
echo "=========================================="
