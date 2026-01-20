# 项目打包指南

本文档说明如何将 AdaptiMultiRAG 项目打包为轻量级分发包。

---

## 📦 打包方案对比

| 方案 | 体积 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| **方案一：清理打包** | ~50MB | 保留源码，易于二次开发 | 需要重新安装依赖 | 开源分享、团队协作 |
| **方案二：Docker 镜像** | ~2GB | 开箱即用，环境一致 | 体积大，需要 Docker | 生产部署 |
| **方案三：仅源码** | ~10MB | 最小体积 | 需要完整配置环境 | Git 仓库 |

---

## 🚀 方案一：清理打包（推荐）

### 自动打包

#### macOS/Linux

```bash
# 1. 赋予执行权限
chmod +x package_project.sh

# 2. 运行打包脚本
./package_project.sh

# 3. 查看输出
ls -lh dist/
```

#### Windows

```cmd
# 双击运行或命令行执行
package_project.bat
```

### 手动打包

如果自动脚本不可用，可以手动执行：

```bash
# 1. 清理后端
cd rag-backend
rm -rf .venv
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
rm -f *.log

# 2. 清理前端
cd ../rag-frontend
rm -rf node_modules dist

# 3. 返回根目录打包
cd ..
tar -czf AdaptiMultiRAG-$(date +%Y%m%d).tar.gz \
  --exclude='.git' \
  --exclude='*.log' \
  --exclude='.DS_Store' \
  .
```

### 打包后的目录结构

```
AdaptiMultiRAG-20260106.tar.gz
└── AdaptiMultiRAG/
    ├── README.md                    # 项目说明
    ├── rag-backend/
    │   ├── backend/                 # 源代码
    │   ├── main.py
    │   ├── pyproject.toml          # Python 依赖
    │   └── uv.lock                 # 锁定版本（可选）
    └── rag-frontend/
        ├── src/                     # 源代码
        ├── package.json            # Node 依赖
        └── package-lock.json       # 锁定版本（可选）
```

---

## 🐳 方案二：Docker 镜像打包

### 构建镜像

```bash
# 构建后端镜像
cd rag-backend
docker build -t adaptimultirag-backend:latest .

# 构建前端镜像
cd ../rag-frontend
docker build -t adaptimultirag-frontend:latest .
```

### 导出镜像

```bash
# 导出为 tar 文件
docker save adaptimultirag-backend:latest | gzip > backend-image.tar.gz
docker save adaptimultirag-frontend:latest | gzip > frontend-image.tar.gz
```

### 导入镜像

```bash
# 在目标机器上导入
docker load < backend-image.tar.gz
docker load < frontend-image.tar.gz
```

---

## 📁 方案三：仅源码打包

适合 Git 仓库或最小化分发。

```bash
# 使用 git archive
git archive --format=tar.gz --prefix=AdaptiMultiRAG/ HEAD > AdaptiMultiRAG-source.tar.gz

# 或手动排除
tar -czf AdaptiMultiRAG-source.tar.gz \
  --exclude='.git' \
  --exclude='rag-backend/.venv' \
  --exclude='rag-backend/__pycache__' \
  --exclude='rag-frontend/node_modules' \
  --exclude='*.log' \
  --exclude='.DS_Store' \
  .
```

---

## 📤 分发包使用说明

### 解压

```bash
# Linux/macOS
tar -xzf AdaptiMultiRAG-20260106.tar.gz
cd AdaptiMultiRAG

# Windows
# 使用 7-Zip 或 WinRAR 解压 .zip 文件
```

### 安装依赖

```bash
# 后端
cd rag-backend
uv sync  # 或 pip install -e .

# 前端
cd ../rag-frontend
npm install
```

### 配置和启动

参考 `README.md` 中的快速开始章节。

---

## 🔧 高级选项

### 排除上传文件

如果不想包含用户上传的文档：

```bash
# 编辑打包脚本，取消注释这一行
rm -rf rag-backend/uploads/*
```

### 移除 Git 历史

可以大幅减小体积（从 ~50MB 到 ~10MB）：

```bash
# 编辑打包脚本，取消注释这一行
rm -rf .git
```

### 保留构建产物

如果想包含前端构建后的静态文件：

```bash
# 先构建前端
cd rag-frontend
npm run build

# 然后打包时不删除 dist 目录
# 注释掉脚本中的 rm -rf dist
```

---

## 📊 体积优化对比

| 内容 | 体积 | 说明 |
|------|------|------|
| 完整项目（含依赖） | ~2.5GB | .venv + node_modules |
| 清理后（方案一） | ~50MB | 仅源码 + 配置 |
| 移除 Git 历史 | ~10MB | 最小化 |
| Docker 镜像 | ~2GB | 包含运行时环境 |

---

## ✅ 打包检查清单

打包前确认：

- [ ] 已更新 `README.md`
- [ ] 已更新 `.env.example`
- [ ] 已删除敏感信息（API Key、密码等）
- [ ] 已测试打包脚本
- [ ] 已验证解压后可正常运行
- [ ] 已添加 LICENSE 文件（如需开源）
- [ ] 已更新版本号

---

## 🆘 常见问题

**Q: 打包后体积还是很大？**

A: 检查是否包含了以下目录：
- `rag-backend/.venv/`
- `rag-frontend/node_modules/`
- `.git/`

**Q: 解压后无法运行？**

A: 确保：
1. 已安装依赖（`uv sync` 和 `npm install`）
2. 已配置 `.env` 文件
3. 数据库服务已启动

**Q: 如何自动化打包？**

A: 可以集成到 CI/CD 流程：

```yaml
# GitHub Actions 示例
- name: Package Project
  run: |
    chmod +x package_project.sh
    ./package_project.sh
    
- name: Upload Artifact
  uses: actions/upload-artifact@v3
  with:
    name: AdaptiMultiRAG-Package
    path: dist/*.tar.gz
```

---

## 📧 支持

如有问题，请提交 Issue 或联系项目维护者。
