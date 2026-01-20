#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
存储检查脚本
用于查看 MySQL、Milvus、Neo4j、PostgreSQL 中的数据
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', '.env'))


def check_mysql():
    """检查 MySQL 中的知识库和文档"""
    print("\n" + "=" * 60)
    print("📊 MySQL 数据")
    print("=" * 60)
    
    try:
        from backend.config.database import DatabaseFactory
        from backend.model.knowledge_library import KnowledgeLibrary, KnowledgeDocument
        
        db = DatabaseFactory.create_session()
        
        # 查询知识库
        libraries = db.query(KnowledgeLibrary).filter(KnowledgeLibrary.is_active == True).all()
        print(f"\n知识库数量: {len(libraries)}")
        
        for lib in libraries:
            doc_count = db.query(KnowledgeDocument).filter(KnowledgeDocument.library_id == lib.id).count()
            graph_status = "✅ 启用" if lib.enable_graph else "❌ 未启用"
            print(f"  - [{lib.id}] {lib.title}")
            print(f"    collection_id: {lib.collection_id}")
            print(f"    文档数: {doc_count}")
            print(f"    知识图谱: {graph_status}")
        
        db.close()
        
    except Exception as e:
        print(f"❌ MySQL 连接失败: {e}")


def check_milvus():
    """检查 Milvus 中的集合和数据"""
    print("\n" + "=" * 60)
    print("🔷 Milvus 数据")
    print("=" * 60)
    
    try:
        from pymilvus import MilvusClient
        
        uri = os.getenv('MILVUS_URI', 'http://localhost:19530')
        db_name = os.getenv('MILVUS_DB_NAME', 'default')
        
        client = MilvusClient(uri=uri, db_name=db_name)
        
        # 获取所有集合
        collections = client.list_collections()
        print(f"\n集合数量: {len(collections)}")
        
        for coll_name in collections:
            try:
                # 获取集合统计信息
                stats = client.get_collection_stats(coll_name)
                row_count = stats.get('row_count', 0)
                print(f"  - {coll_name}: {row_count} 条记录")
            except Exception as e:
                print(f"  - {coll_name}: 获取统计失败 ({e})")
        
    except Exception as e:
        print(f"❌ Milvus 连接失败: {e}")


def check_milvus_collection_detail(collection_name: str, limit: int = 5):
    """查看 Milvus 集合详细数据"""
    print("\n" + "=" * 60)
    print(f"🔷 Milvus 集合详情: {collection_name}")
    print("=" * 60)
    
    try:
        from pymilvus import MilvusClient
        
        uri = os.getenv('MILVUS_URI', 'http://localhost:19530')
        db_name = os.getenv('MILVUS_DB_NAME', 'default')
        
        client = MilvusClient(uri=uri, db_name=db_name)
        
        # 查询数据
        results = client.query(
            collection_name=collection_name,
            filter="",
            limit=limit,
            output_fields=["document_name", "chunk_index", "chunk_size"]
        )
        
        print(f"\n前 {limit} 条记录:")
        for i, row in enumerate(results):
            print(f"  [{i+1}] 文档: {row.get('document_name', 'N/A')}, "
                  f"块索引: {row.get('chunk_index', 'N/A')}, "
                  f"大小: {row.get('chunk_size', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")


def check_neo4j():
    """检查 Neo4j 中的图数据"""
    print("\n" + "=" * 60)
    print("🔶 Neo4j 图数据")
    print("=" * 60)
    
    try:
        from neo4j import GraphDatabase
        
        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', 'neo4j')
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            # 统计节点数
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]
            
            # 统计关系数
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            
            # 获取节点标签
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
            
            print(f"\n节点数量: {node_count}")
            print(f"关系数量: {rel_count}")
            print(f"节点标签: {labels}")
            
            # 显示部分节点
            if node_count > 0:
                result = session.run("MATCH (n) RETURN n LIMIT 5")
                print("\n前 5 个节点:")
                for record in result:
                    node = record["n"]
                    print(f"  - {dict(node)}")
        
        driver.close()
        
    except Exception as e:
        print(f"❌ Neo4j 连接失败: {e}")


def check_postgres():
    """检查 PostgreSQL 中的 LightRAG 数据"""
    print("\n" + "=" * 60)
    print("🐘 PostgreSQL (LightRAG) 数据")
    print("=" * 60)
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DATABASE', 'rag_checkpoint'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '123456')
        )
        
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\n表数量: {len(tables)}")
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count} 条记录")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ PostgreSQL 连接失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='存储检查脚本')
    parser.add_argument('--mysql', action='store_true', help='检查 MySQL')
    parser.add_argument('--milvus', action='store_true', help='检查 Milvus')
    parser.add_argument('--neo4j', action='store_true', help='检查 Neo4j')
    parser.add_argument('--postgres', action='store_true', help='检查 PostgreSQL')
    parser.add_argument('--collection', type=str, help='查看 Milvus 集合详情')
    parser.add_argument('--all', action='store_true', help='检查所有存储')
    
    args = parser.parse_args()
    
    # 如果没有指定参数，默认检查所有
    if not any([args.mysql, args.milvus, args.neo4j, args.postgres, args.collection, args.all]):
        args.all = True
    
    print("\n🔍 存储检查工具")
    print("=" * 60)
    
    if args.all or args.mysql:
        check_mysql()
    
    if args.all or args.milvus:
        check_milvus()
    
    if args.collection:
        check_milvus_collection_detail(args.collection)
    
    if args.all or args.neo4j:
        check_neo4j()
    
    if args.all or args.postgres:
        check_postgres()
    
    print("\n" + "=" * 60)
    print("✅ 检查完成")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
