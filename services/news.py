"""
资讯新闻服务
数据源：长桥全景 stock_news/posts API
"""
import requests
from datetime import datetime
from models.database import get_collection

# 长桥新闻 API
LB_NEWS_URL = "https://m.lbkrs.com/api/forward/content/stock_news/posts"

LB_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN",
    "content-type": "application/json",
    "x-app-id": "longport",
    "x-bridge-token": "none",
    "x-device-id": "33f363e3b1a1351e63e7ce9fab4fc23d-longportapp.cn",
    "x-domain-region": "CN",
    "x-original-app-id": "longbridge",
    "x-platform": "web",
    "x-prefer-language": "zh-CN",
    "referer": "https://longportapp.cn/",
    "origin": "https://longportapp.cn",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "x-saas-host": "",
}


def build_counter_id(code, market="US", product="ST"):
    """
    构建长桥 counter_id
    格式: {product}/{market}/{code}
    例: ST/US/AAPL, ETF/US/QQQM
    """
    return f"{product}/{market}/{code}"


def fetch_news(stock_code, limit=50, market="US", product="ST"):
    """
    获取个股相关资讯 — 优先走长桥 API，失败则降级到 MongoDB
    支持去重（按标题去重）
    """
    # 1. 先尝试长桥 API
    try:
        articles = fetch_from_longbridge(stock_code, market=market, product=product, limit=limit)
        if articles:
            # 异步缓存到 MongoDB (best effort)
            try:
                _cache_news(articles, stock_code)
            except Exception as e:
                print(f'[News] 缓存到MongoDB失败: {e}')
            return _deduplicate_news(articles)
    except Exception as e:
        print(f"[News] 长桥 API 失败: {e}")

    # 2. 降级到 MongoDB 缓存
    try:
        col = get_collection("news")
        if col is not None:
            news_list = list(col.find(
                {"stock_code": stock_code},
                {"_id": 0}
            ).sort("publish_time", -1).limit(limit))
            if news_list:
                return _deduplicate_news(news_list)
    except Exception:
        pass

    return []


def _deduplicate_news(news_list):
    """按标题去重，保留第一次出现的"""
    seen_titles = set()
    result = []
    for item in news_list:
        title = (item.get("title") or "").strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            result.append(item)
        elif not title:
            # 无标题的保留（如快讯），用 id 去重
            item_id = item.get("id", "")
            if item_id and item_id not in seen_titles:
                seen_titles.add(item_id)
                result.append(item)
    return result


def fetch_from_longbridge(stock_code, market="US", product="ST", limit=20):
    """
    从长桥全景抓取资讯
    POST /api/forward/content/stock_news/posts
    Body: {"next_params":{}, "counter_ids":["ST/US/AAPL"], "has_derivatives":true}
    """
    counter_id = build_counter_id(stock_code, market, product)
    payload = {
        "next_params": {},
        "counter_ids": [counter_id],
        "has_derivatives": True
    }

    resp = requests.post(LB_NEWS_URL, json=payload, headers=LB_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        print(f"[News] 长桥返回错误: {data.get('message')}")
        return []

    articles_raw = data.get("data", {}).get("articles", [])
    result = []

    for art in articles_raw[:limit]:
        # 提取标题 (快讯可能没标题，用 description 代替)
        title = art.get("title", "")
        desc_html = art.get("description_html", "")

        # 从 HTML 中提取纯文本作为内容
        content = _strip_html(desc_html)

        if not title and content:
            title = content[:60] + ("..." if len(content) > 60 else "")

        # 时间戳
        ts = art.get("published_at", "0")
        try:
            pub_time = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):
            pub_time = ""

        # 来源
        source = (art.get("post_source") or {}).get("name", "长桥")
        source_logo = (art.get("post_source") or {}).get("logo", "")

        # 是否重要
        important = art.get("important", False)

        # 封面图
        cover = art.get("cover", "")
        images = art.get("images", [])
        if images and not cover:
            cover = images[0].get("url", "")

        # 关联股票
        related_stocks = []
        for s in (art.get("derivatives", {}).get("stocks", []) or [])[:5]:
            related_stocks.append({
                "code": s.get("code", ""),
                "name": s.get("name", ""),
                "market": s.get("market", ""),
                "change": s.get("change", ""),
                "logo": s.get("logo", ""),
            })

        # AI 摘要
        portai_summary = art.get("portai_summary", "")

        # 链接
        detail_url = art.get("web_url") or art.get("detail_url") or art.get("source_url", "")

        # 类型: 1=文章, 2=快讯
        kind = art.get("kind", 1)

        result.append({
            "id": art.get("id", ""),
            "title": title,
            "content": content,
            "source": source,
            "source_logo": source_logo,
            "publish_time": pub_time,
            "url": detail_url,
            "cover": cover,
            "important": important,
            "kind": kind,  # 1=文章, 2=快讯
            "related_stocks": related_stocks,
            "ai_summary": portai_summary,
        })

    return result


def _strip_html(html_str):
    """简易去掉 HTML 标签"""
    import re
    text = re.sub(r'<[^>]+>', '', html_str or '')
    return text.strip()


def _cache_news(articles, stock_code):
    """缓存新闻到 MongoDB"""
    col = get_collection("news")
    if col is None:
        return
    for art in articles:
        art_copy = dict(art)
        art_copy["stock_code"] = stock_code
        art_copy.setdefault("created_at", datetime.now())
        try:
            col.update_one(
                {"id": art_copy["id"]},
                {"$set": art_copy},
                upsert=True,
            )
        except Exception as e:
            print(f'[News] MongoDB写入失败: {e}')


def save_news(news_items):
    """
    批量保存资讯（供爬虫/接口调用）
    """
    col = get_collection("news")
    if col is None:
        return
    for item in news_items:
        item.setdefault("created_at", datetime.now())
        item.setdefault("publish_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        col.update_one(
            {"title": item["title"], "source": item.get("source", "")},
            {"$set": item},
            upsert=True,
        )


def search_news(keyword=None, stock_code=None, start_date=None, end_date=None, limit=50):
    """搜索资讯"""
    col = get_collection("news")
    if col is None:
        return []
    query = {}
    if stock_code:
        query["stock_code"] = stock_code
    if keyword:
        query["$or"] = [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"content": {"$regex": keyword, "$options": "i"}},
        ]
    if start_date or end_date:
        date_q = {}
        if start_date:
            date_q["$gte"] = start_date
        if end_date:
            date_q["$lte"] = end_date
        query["publish_time"] = date_q

    return list(col.find(query, {"_id": 0}).sort("publish_time", -1).limit(limit))


def get_news_for_ai(stock_code, limit=10, market="US", product="ST"):
    """
    获取资讯摘要（供 AI Tool Calling 使用）
    """
    news_list = fetch_news(stock_code, limit=limit, market=market, product=product)
    if not news_list:
        return {"stock_code": stock_code, "news": [], "summary": "暂无相关资讯数据"}

    simplified = []
    for n in news_list:
        simplified.append({
            "title": n.get("title", ""),
            "content": (n.get("content", "") or "")[:200],
            "source": n.get("source", ""),
            "time": n.get("publish_time", ""),
            "important": n.get("important", False),
        })

    return {
        "stock_code": stock_code,
        "news_count": len(simplified),
        "news": simplified,
        "summary": f"共找到 {len(simplified)} 条相关资讯，请基于股票具体情况分析其影响。",
    }
