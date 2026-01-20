# AdaptiMultiRAG - 智能多模态 RAG 系统

<div align="center">

**基于 LangGraph 的企业级 RAG 知识库问答系统**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3.5+-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-teal.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.6+-purple.svg)](https://langchain-ai.github.io/langgraph/)

</div>

---

## 📖 项目简介

AdaptiMultiRAG 是一个基于 LangGraph 构建的智能 RAG（检索增强生成）系统，支持多种检索模式、联网搜索和知识图谱增强。系统采用前后端分离架构，提供完整的知识库管理、文档上传、智能问答等功能。

### 核心特性

- 🧠 **多模态检索**：支持向量检索、图检索、混合检索
- 🔄 **智能路由**：基于 LangGraph 的动态检索策略
- 🌐 **联网搜索**：集成 Tavily API 实时获取网络信息
- 📚 **知识图谱**：基于 LightRAG 的图数据库增强
- 🔐 **用户隔离**：完整的用户认证和数据隔离机制
- ⚡ **实例池化**：RAGGraph 实例复用，提升性能
- 💬 **流式输出**：支持 SSE 流式响应
- 📊 **多文档支持**：PDF、DOCX、TXT 等格式

---

## 🏗️ 系统架构

```
AdaptiMultiRAG/
├── rag-backend/          # 后端服务 (FastAPI + LangGraph)
│   ├── backend/
│   │   ├── agent/        # LangGraph Agent 实现
│   │   │   ├── graph/    # RAGGraph 核心逻辑
│   │   │   ├── tools/    # MCP 工具集成
│   │   │   ├── states/   # 状态定义
│   │   │   └── prompts/  # 提示词模板
│   │   ├── api/          # FastAPI 路由
│   │   ├── config/       # 配置管理
│   │   ├── model/        # 数据模型
│   │   ├── rag/          # RAG 核心组件
│   │   │   └── storage/  # Milvus + LightRAG 存储
│   │   ├── service/      # 业务逻辑层
│   │   └── utils/        # 工具函数
│   ├── main.py           # 应用入口
│   └── pyproject.toml    # 依赖配置
│
└── rag-frontend/         # 前端应用 (Vue 3 + Element Plus)
    ├── src/
    │   ├── api/          # API 接口封装
    │   ├── components/   # Vue 组件
    │   ├── stores/       # Pinia 状态管理
    │   ├── router/       # 路由配置
    │   └── views/        # 页面视图
    └── package.json      # 依赖配置
```

### 技术栈

**后端**
- FastAPI - 高性能 Web 框架
- LangGraph - 智能 Agent 编排
- LangChain - LLM 应用框架
- Milvus - 向量数据库
- LightRAG - 知识图谱存储
- MySQL - 业务数据存储
- Redis - 缓存层

**前端**
- Vue 3 - 渐进式框架
- Element Plus - UI 组件库
- Pinia - 状态管理
- Vite - 构建工具
- Tailwind CSS - 样式框架

---

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- MySQL 8.0+
- Milvus 2.6+
- Redis 7.0+ (可选)

### 1. 克隆项目

```bash
git clone https://github.com/your-repo/AdaptiMultiRAG.git
cd AdaptiMultiRAG
```

### 2. 后端配置

#### 安装依赖

```bash
cd rag-backend

# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

#### 配置环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env 文件，填写必要配置
```

**必需配置项**：
```env
# 数据库
DB_URL=mysql+pymysql://user:password@localhost:3306/rag_db

# LLM API
DASHSCOPE_API_KEY=your_dashscope_key
LLM_DASHSCOPE_CHAT_MODEL=qwen-plus

# 向量数据库
MILVUS_URI=http://localhost:19530

# JWT 认证
JWT_SECRET_KEY=your_random_secret_key

# 对象存储 (腾讯云 COS)
COS_SECRET_ID=your_cos_secret_id
COS_SECRET_KEY=your_cos_secret_key
COS_BUCKET_NAME=your_bucket_name
COS_REGION=ap-beijing

# 联网搜索 (可选)
TAVILY_API_KEY=your_tavily_key
```

#### 初始化数据库

```bash
# 创建数据库表
python backend/init_db.py
```

#### 启动后端服务

```bash
# 开发模式
python main.py

# 或使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

后端服务运行在 `http://localhost:8000`

### 3. 前端配置

#### 安装依赖

```bash
cd rag-frontend
npm install
```

#### 配置 API 地址

编辑 `src/api/request.js`，确保 `baseURL` 指向后端地址：

```javascript
const baseURL = 'http://localhost:8000'
```

#### 启动前端服务

```bash
npm run dev
```

前端应用运行在 `http://localhost:5173`



<div align="center">



</div>
