#!/usr/bin/env python3
"""清空 Milvus 所有集合"""
from pymilvus import MilvusClient

client = MilvusClient(uri='http://localhost:19530', db_name='default')
collections = client.list_collections()
print(f'删除 {len(collections)} 个集合...')

for coll in collections:
    client.drop_collection(coll)
    print(f'  已删除: {coll}')

print('完成')
