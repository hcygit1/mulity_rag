#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Backend 主入口
"""

from backend.config.log import setup_default_logging, get_logger
from fastapi import FastAPI
from backend.api import chat, auth, crawl, knowledge_library, visual_graph, upload, monitor
from dotenv import load_dotenv
import uvicorn
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理"""
    # 启动时执行
    load_dotenv()    # 加载环境变量
    setup_default_logging() # 初始化日志

    logger = get_logger(__name__)
    logger.info("FastAPI 应用启动中...")
    yield
    # 关闭时执行：清理 RAGGraph 实例池
    logger.info("FastAPI 应用关闭中，清理 RAGGraph 实例池...")
    from backend.config.agent import RAGGraphPool
    RAGGraphPool.clear_all()
    logger.info("RAGGraph 实例池清理完成")

app = FastAPI(title="RAG Demo API", version="1.0.0", lifespan=lifespan)

app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(crawl.router)
app.include_router(knowledge_library.router)
app.include_router(visual_graph.router)
app.include_router(monitor.router)
app.include_router(upload.router)

@app.get("/health")
async def read_root():
    return {"message": "Hello, FastAPI!"}    

def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
