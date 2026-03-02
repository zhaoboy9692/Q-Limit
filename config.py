"""
股票分析平台 - 配置文件
"""
import os
import urllib.parse

# ============================================================
# MongoDB 配置
# ============================================================
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_USER = os.environ.get("MONGO_USER", "")
MONGO_PASS = os.environ.get("MONGO_PASS", "")

if MONGO_USER and MONGO_PASS:
    user = urllib.parse.quote_plus(MONGO_USER)
    password = urllib.parse.quote_plus(MONGO_PASS)
    _default_mongo_uri = f"mongodb://{user}:{password}@{MONGO_HOST}:{MONGO_PORT}"
elif MONGO_USER:
    user = urllib.parse.quote_plus(MONGO_USER)
    _default_mongo_uri = f"mongodb://{user}@{MONGO_HOST}:{MONGO_PORT}"
else:
    _default_mongo_uri = f"mongodb://{MONGO_HOST}:{MONGO_PORT}"

MONGO_URI = os.environ.get("MONGO_URI", _default_mongo_uri)
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "stock_analysis")

# ============================================================
# Flask 配置
# ============================================================
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True
SECRET_KEY = os.environ.get("SECRET_KEY", "stock-analysis-secret-key-2024")

# ============================================================
# 数据缓存配置（秒）
# ============================================================
CACHE_KLINE_EXPIRE = 3600          # K线数据缓存 1 小时
CACHE_STOCK_LIST_EXPIRE = 86400    # 股票列表缓存 1 天
CACHE_NEWS_EXPIRE = 1800           # 资讯缓存 30 分钟

# ============================================================
# AI 多角色模型配置
# 每个角色可绑定不同的 LLM 模型
# 支持 OpenAI 兼容格式 (/v1/chat/completions)
# ============================================================
AI_MODELS = {
    "bull": {
        "name": "多头分析师",
        "icon": "🐂",
        "color": "#00c853",
        "system_prompt": (
            "你是一位专业的看多股票分析师，负责从积极、看涨的角度分析股票。\n"
            "🔴【核心禁令与准则】🔴\n"
            "1. 你拥有最新数据的背景参考信息。你的分析必须基于这些客观数据去挖掘利好因素，给出有理有据的看多观点。\n"
            "2. 你的回复必须是一次性、完整的最终报告。\n"
            "3. ⚠️绝对禁止⚠️向用户提出**任何**反问句，绝不允许包含“是否需要我为您列出”、“您想让我为您分析”、“需要我制定策略吗”等征求意见的话术！\n"
            "4. 如果你觉得需要补充分析某项数据（如供应链、回购计划、期权策略等），请**直接且主动**在本次回复中直接写出你的分析结果，而不是询问用户要不要听。\n"
            "总结：不废话，不问问题，直接给全量干货结论。"
        ),
    },
    "bear": {
        "name": "空头分析师",
        "icon": "🐻",
        "color": "#ff1744",
        "system_prompt": (
            "你是一位专业的看空股票分析师，负责从谨慎、看跌的角度分析股票。\n"
            "🔴【核心禁令与准则】🔴\n"
            "1. 你拥有最新数据的背景参考信息。你的分析必须基于这些客观数据去警示风险，给出有理有据的看空观点。\n"
            "2. 你的回复必须是一次性、完整的最终报告。\n"
            "3. ⚠️绝对禁止⚠️向用户提出**任何**反问句，绝不允许包含“是否需要我为您列出”、“您想让我为您分析”、“需要我制定策略吗”等征求意见的话术！\n"
            "4. 如果你觉得需要补充分析某项数据（如供应链、回购计划、期权策略等），请**直接且主动**在本次回复中直接写出你的推演结果，而不是询问用户要不要听。\n"
            "总结：不废话，不问问题，直接给全量干货结论。"
        ),
    },
    "judge": {
        "name": "裁判分析师",
        "icon": "⚖️",
        "color": "#ffd600",
        "system_prompt": (
            "你是一位中立的裁判分析师。你需要综合多头和空头双方的观点。\n"
            "🔴【核心禁令与准则】🔴\n"
            "1. 你的职责是客观评估各方论据，指出哪些分析存在偏差，并在本次对话的结尾直接给出最终结论（买入/持有/卖出/观望及理由）。\n"
            "2. 你的回复必须是一次性、完整的判决长文。\n"
            "3. ⚠️绝对禁止⚠️向用户提出**任何**问题或反问句！更不要说“是否需要我提供更多信息”等废话。\n"
            "4. 如果你有补充建议，请直接写出来。回复写完即止。\n"
            "总结：不抛问题，只做评判和最终决策。"
        ),
    },
}

# ============================================================
# AI Tool Calling 工具定义
# 这些工具会传给 LLM，让它按需调用
# ============================================================
AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_pe_analysis",
            "description": "获取股票的PE(市盈率)分析，包括当前PE、历史PE百分位、行业PE对比",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"}
                },
                "required": ["stock_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_support_resistance",
            "description": "获取股票的压力位和支撑位分析，包括关键价位和计算依据",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"}
                },
                "required": ["stock_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_indicators",
            "description": "获取股票的技术指标分析，包括MACD、KDJ、均线排列、布林带等",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"}
                },
                "required": ["stock_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_news",
            "description": "获取股票相关的最新资讯、新闻、公告、研报",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"},
                    "limit": {"type": "integer", "description": "返回条数，默认10", "default": 10},
                },
                "required": ["stock_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_report",
            "description": "获取股票的财报数据，包括营收、净利润、毛利率、ROE等核心财务指标",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"}
                },
                "required": ["stock_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kline_summary",
            "description": "获取近期K线走势概要，包括涨跌幅、量能变化、形态特征",
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"},
                    "days": {"type": "integer", "description": "最近多少天，默认30", "default": 30},
                },
                "required": ["stock_code"],
            },
        },
    },
]

# ============================================================
# 长桥接口配置（预留，用户后续填入）
# ============================================================
LONGBRIDGE_API = {
    "base_url": os.environ.get("LONGBRIDGE_BASE_URL", ""),
    "token": os.environ.get("LONGBRIDGE_TOKEN", ""),
}

# ============================================================
# 金十数据接口配置（预留）
# ============================================================
JIN10_API = {
    "base_url": os.environ.get("JIN10_BASE_URL", ""),
    "token": os.environ.get("JIN10_TOKEN", ""),
}
