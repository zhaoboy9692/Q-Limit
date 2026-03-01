"""
MongoDB 数据库连接与集合定义
延迟初始化，连接失败时不阻塞启动
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from config import MONGO_URI, MONGO_DB_NAME

# 全局数据库连接
_client = None
_db = None
_indexes_created = False


def get_db():
    """获取数据库连接"""
    global _client, _db, _indexes_created
    if _db is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _client[MONGO_DB_NAME]

    if not _indexes_created:
        try:
            _ensure_indexes()
            _indexes_created = True
        except Exception as e:
            print(f"[database] 索引创建跳过（MongoDB可能未运行）: {e}")

    return _db


def _ensure_indexes():
    """创建必要的索引"""
    db = _db

    # 股票基础信息（code+market 联合唯一）
    db.stocks.create_index(
        [("code", ASCENDING), ("market", ASCENDING)], unique=True
    )
    db.stocks.create_index([("name", ASCENDING)])
    db.stocks.create_index([("name_cn", ASCENDING)])

    # 日K线数据
    db.daily_quotes.create_index(
        [("code", ASCENDING), ("date", ASCENDING)], unique=True
    )

    # 分析结果缓存
    db.analysis_cache.create_index(
        [("code", ASCENDING), ("type", ASCENDING)]
    )
    db.analysis_cache.create_index(
        [("updated_at", ASCENDING)], expireAfterSeconds=3600
    )

    # 资讯数据
    db.news.create_index([("stock_code", ASCENDING), ("publish_time", DESCENDING)])
    db.news.create_index([("source", ASCENDING)])

    # 财报数据
    db.financial_reports.create_index(
        [("code", ASCENDING), ("report_date", DESCENDING)]
    )

    # AI 聊天记录
    db.chat_history.create_index(
        [("stock_code", ASCENDING), ("session_id", ASCENDING), ("created_at", ASCENDING)]
    )


def get_collection(name):
    """获取指定集合"""
    return get_db()[name]
