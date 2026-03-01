"""
股票数据获取服务
支持长桥逆向接口搜索 + akshare K线数据
MongoDB 离线时自动降级（只查远程API，不缓存）
"""
import requests
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from config import CACHE_KLINE_EXPIRE, CACHE_STOCK_LIST_EXPIRE

# ============================================================
# 长桥 API 请求头
# ============================================================
LONGBRIDGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "x-device-id": "33f363e3b1a1351e63e7ce9fab4fc23d-longportapp.cn",
    "x-bridge-token": "none",
    "x-app-id": "longport",
    "x-original-app-id": "longbridge",
    "x-domain-region": "CN",
    "x-platform": "web",
    "x-prefer-language": "zh-CN",
    "accept-language": "zh-CN",
    "Referer": "https://longportapp.cn/",
}


def _safe_get_collection(name):
    """安全获取 MongoDB 集合，失败返回 None"""
    try:
        from models.database import get_collection
        return get_collection(name)
    except Exception:
        return None


def search_stock(keyword):
    """
    搜索股票 - 优先使用长桥接口，失败则回退到本地缓存
    """
    lb_results = _search_from_longbridge(keyword)
    if lb_results:
        return lb_results
    return _search_from_cache(keyword)


def _search_from_longbridge(keyword):
    """
    长桥逆向接口搜索
    MongoDB 不可用时仍返回结果（只是不缓存）
    """
    try:
        url = "https://m.lbkrs.com/api/forward/v1/search/container/main"
        params = {"k": keyword, "search_src": "main_search"}
        resp = requests.get(url, params=params, headers=LONGBRIDGE_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return []

        product_list = data.get("data", {}).get("product_list", [])
        if not product_list:
            return []

        results = []
        for item in product_list:
            doc = {
                "code": item.get("code", ""),
                "name": item.get("name", ""),
                "name_cn": item.get("name_cn", ""),
                "name_en": item.get("name_en", ""),
                "name_cn_alias": item.get("name_cn_alias", ""),
                "name_en_alias": item.get("name_en_alias", ""),
                "market": item.get("market", ""),
                "product": item.get("product", ""),
                "counter_id": item.get("counter_id", ""),
                "currency": item.get("currency", ""),
                "lb_id": item.get("id", ""),
                "type": item.get("type", ""),
                "score": item.get("score", 0),
                "source": "longbridge",
                "updated_at": datetime.now(),
            }

            # 尝试存入 MongoDB（失败不影响返回）
            try:
                col = _safe_get_collection("stocks")
                if col is not None:
                    col.update_one(
                        {"code": doc["code"], "market": doc["market"]},
                        {"$set": doc},
                        upsert=True,
                    )
            except Exception:
                pass  # MongoDB 不可用，跳过缓存

            results.append({
                "code": doc["code"],
                "name": doc["name_cn"] or doc["name"],
                "name_en": doc["name_en"],
                "market": doc["market"],
                "product": doc["product"],
                "counter_id": doc["counter_id"],
                "currency": doc["currency"],
            })

        return results

    except Exception as e:
        print(f"[longbridge] 搜索异常: {e}")
        return []


def _search_from_cache(keyword):
    """从本地 MongoDB 缓存搜索"""
    try:
        col = _safe_get_collection("stocks")
        if col is None:
            return []

        results = list(col.find(
            {"$or": [
                {"code": {"$regex": keyword, "$options": "i"}},
                {"name": {"$regex": keyword, "$options": "i"}},
                {"name_cn": {"$regex": keyword, "$options": "i"}},
                {"name_en": {"$regex": keyword, "$options": "i"}},
            ]},
            {"_id": 0, "code": 1, "name": 1, "name_cn": 1, "name_en": 1,
             "market": 1, "product": 1, "counter_id": 1, "currency": 1}
        ).limit(20))

        return [
            {
                "code": r.get("code", ""),
                "name": r.get("name_cn") or r.get("name", ""),
                "name_en": r.get("name_en", ""),
                "market": r.get("market", ""),
                "product": r.get("product", ""),
                "counter_id": r.get("counter_id", ""),
                "currency": r.get("currency", ""),
            }
            for r in results
        ]
    except Exception:
        return []


# ============================================================
# 长桥 K 线 API
# ============================================================
LB_KLINE_URL = "https://m.lbkrs.com/api/forward/v3/quote/kline"
LB_TIMESHARE_URL = "https://m.lbkrs.com/api/forward/v5/quote/stock/timeshares"
LB_MULTI_TIMESHARE_URL = "https://m.lbkrs.com/api/forward/quote/stock/mutitimeshares"

# period -> line_type 映射
PERIOD_LINE_TYPE = {
    "1min": 1,
    "5min": 5,
    "15min": 15,
    "30min": 30,
    "60min": 60,
    "daily": 1000,
    "weekly": 2000,
    "monthly": 3000,
    "yearly": 4000,
}


def _build_counter_id(code, market="US", product="ST"):
    """构建长桥 counter_id: {product}/{market}/{code}"""
    return f"{product}/{market}/{code}"


def fetch_kline(code, period="daily", start_date=None, end_date=None, adjust="qfq",
                market="US", product="ST", kline_session="101"):
    """
    获取K线数据
    优先长桥 API → akshare 降级
    period: 'timeshare', '5day', '1min', '5min', '15min', '30min', '60min',
            'daily', 'weekly', 'monthly', 'yearly'
    kline_session: 100=盘中, 101=全部, 102=盘前, 103=盘后, 104=夜盘
    """
    # 分时图走独立接口
    # kline_session(K线) → trade_session(分时) 映射
    TIMESHARE_SESSION_MAP = {
        100: 0,    # 盘中
        101: 100,  # 全部
        102: 2,    # 盘前
        103: 3,    # 盘后
        104: 4,    # 夜盘
    }
    if period == "timeshare":
        ts = TIMESHARE_SESSION_MAP.get(int(kline_session), 100)
        return _fetch_timeshare(code, market, product, trade_session=ts)
    if period == "5day":
        return _fetch_multi_timeshare(code, market, product)

    # K 线走长桥 API
    line_type = PERIOD_LINE_TYPE.get(period, 1000)
    try:
        result = _fetch_kline_from_longbridge(code, line_type, market, product, kline_session=int(kline_session))
        if result:
            return result
    except Exception as e:
        print(f"[stock_data] 长桥K线API失败: {e}")

    # 降级到 akshare（仅支持A股日/周/月）
    return _fetch_kline_from_akshare(code, period, start_date, end_date, adjust)


def _fetch_kline_from_longbridge(code, line_type, market="US", product="ST", line_num=400, kline_session=101):
    """
    从长桥抓取K线数据
    GET /api/forward/v3/quote/kline
    """
    counter_id = _build_counter_id(code, market, product)

    params = {
        "counter_id": counter_id,
        "line_num": line_num,
        "line_type": line_type,
        "timestamp": "",
        "adjust_type": 1,
        "widget_id": "chart",
        "direction": 0,
        "kline_session": kline_session,
    }

    resp = requests.get(LB_KLINE_URL, params=params, headers=LONGBRIDGE_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        print(f"[stock_data] 长桥K线返回错误: {data.get('message')}")
        return []

    klines = data.get("data", {}).get("klines", [])
    records = []

    def _sf(val, default=0):
        """安全转浮点，处理空字符串"""
        try:
            return float(val) if val else default
        except (ValueError, TypeError):
            return default

    for k in klines:
        ts = int(k.get("timestamp", 0))
        if ts == 0:
            continue

        try:
            dt = datetime.fromtimestamp(ts)
            # 分钟K用 datetime 字符串，日K以上用日期字符串
            if line_type < 1000:
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = dt.strftime("%Y%m%d")
        except (ValueError, OSError):
            continue

        o = _sf(k.get("open"))
        c = _sf(k.get("close"))
        h = _sf(k.get("high"))
        lo = _sf(k.get("low"))
        vol = _sf(k.get("amount"))
        amt = _sf(k.get("balance"))

        # 计算涨跌幅
        prev_close = _sf(k.get("prev_close"))
        if prev_close > 0:
            change_pct = (c - prev_close) / prev_close * 100
        elif len(records) > 0:
            prev_c = records[-1]["close"]
            change_pct = (c - prev_c) / prev_c * 100 if prev_c else 0
        else:
            change_pct = 0

        records.append({
            "code": code,
            "date": date_str,
            "open": o,
            "close": c,
            "high": h,
            "low": lo,
            "volume": vol,
            "amount": amt,
            "change_pct": round(change_pct, 2),
            "turnover": 0,
        })

    return records


def _fetch_timeshare(code, market="US", product="ST", trade_session=100):
    """
    获取当日分时图
    GET /api/forward/v5/quote/stock/timeshares
    trade_session: 0=盘中, 100=全部, 2=盘前, 3=盘后, 4=夜盘
    
    API 返回结构：
    data.timeshares[] → 每天（含 date, pre_close, minutes[], trade_session）
    minutes[] → 每分钟（含 price, amount, balance, timestamp, avg_price）
    """
    counter_id = _build_counter_id(code, market, product)

    params = {
        "counter_id": counter_id,
        "trade_session": trade_session,
    }

    try:
        resp = requests.get(LB_TIMESHARE_URL, params=params, headers=LONGBRIDGE_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return []

        days = data.get("data", {}).get("timeshares", [])
        records = []

        for day_data in days:
            pre_close = float(day_data.get("pre_close", 0) or 0)
            minutes = day_data.get("minutes", [])

            for m in minutes:
                ts = int(m.get("timestamp", 0))
                if ts == 0:
                    continue
                try:
                    dt = datetime.fromtimestamp(ts)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, OSError):
                    continue

                price = float(m.get("price", 0) or 0)
                avg_price = float(m.get("avg_price", 0) or 0)
                vol = float(m.get("amount", 0) or 0)
                amt = float(m.get("balance", 0) or 0) if m.get("balance") else 0

                if price <= 0:
                    continue

                records.append({
                    "code": code,
                    "date": date_str,
                    "open": price,
                    "close": price,
                    "high": price,
                    "low": price,
                    "avg_price": avg_price,
                    "volume": vol,
                    "amount": amt,
                    "change_pct": 0,
                    "turnover": 0,
                    "prev_close": pre_close,
                    "is_timeshare": True,
                })

        return records

    except Exception as e:
        print(f"[stock_data] 分时数据获取失败: {e}")
        return []


def _fetch_multi_timeshare(code, market="US", product="ST"):
    """
    获取5日分时图
    GET /api/forward/quote/stock/mutitimeshares
    """
    counter_id = _build_counter_id(code, market, product)

    params = {
        "counter_id": counter_id,
        "merge_minute": 0,
    }

    try:
        resp = requests.get(LB_MULTI_TIMESHARE_URL, params=params, headers=LONGBRIDGE_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return []

        # 解析多日分时（与单日分时结构一致：timeshares[].minutes[]）
        days = data.get("data", {}).get("timeshares", [])
        records = []
        for day_data in days:
            if not isinstance(day_data, dict):
                continue
            pre_close = float(day_data.get("pre_close", 0) or 0)
            minutes = day_data.get("minutes", [])

            for m in minutes:
                ts = int(m.get("timestamp", 0))
                if ts == 0:
                    continue
                try:
                    dt = datetime.fromtimestamp(ts)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, OSError):
                    continue

                price = float(m.get("price", 0) or 0)
                vol = float(m.get("amount", 0) or 0)

                if price <= 0:
                    continue

                records.append({
                    "code": code,
                    "date": date_str,
                    "open": price,
                    "close": price,
                    "high": price,
                    "low": price,
                    "volume": vol,
                    "amount": 0,
                    "change_pct": 0,
                    "turnover": 0,
                    "prev_close": pre_close,
                    "is_timeshare": True,
                })

        return records

    except Exception as e:
        print(f"[stock_data] 5日分时数据获取失败: {e}")
        return []


def _fetch_kline_from_akshare(code, period="daily", start_date=None, end_date=None, adjust="qfq"):
    """降级到 akshare（仅支持A股）"""
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    # akshare 的周期映射
    ak_period_map = {"daily": "daily", "weekly": "weekly", "yearly": "daily"}
    ak_period = ak_period_map.get(period, "daily")

    cached = []
    col = _safe_get_collection("daily_quotes")
    if col is not None:
        try:
            cached = list(col.find(
                {"code": code, "date": {"$gte": start_date, "$lte": end_date}},
                {"_id": 0}
            ).sort("date", 1))
            if len(cached) > 20:
                return cached
        except Exception:
            pass

    try:
        df = ak.stock_zh_a_hist(
            symbol=code, period=ak_period,
            start_date=start_date, end_date=end_date, adjust=adjust,
        )

        records = []
        for _, row in df.iterrows():
            date_str = str(row["日期"]).replace("-", "")
            record = {
                "code": code,
                "date": date_str,
                "open": float(row["开盘"]),
                "close": float(row["收盘"]),
                "high": float(row["最高"]),
                "low": float(row["最低"]),
                "volume": float(row["成交量"]),
                "amount": float(row.get("成交额", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
                "turnover": float(row.get("换手率", 0)),
                "updated_at": datetime.now(),
            }
            records.append(record)

        if records and col is not None:
            try:
                from pymongo import UpdateOne
                ops = [
                    UpdateOne(
                        {"code": code, "date": r["date"]},
                        {"$set": r}, upsert=True
                    ) for r in records
                ]
                col.bulk_write(ops)
            except Exception:
                pass

        return records

    except Exception as e:
        print(f"[stock_data] akshare 获取K线数据失败: {e}")
        return cached if cached else []


def fetch_stock_info(code):
    """获取个股基本面信息（旧接口兼容）"""
    try:
        col = _safe_get_collection("stocks")
        if col is not None:
            info = col.find_one({"code": code}, {"_id": 0})
            if info:
                return info
    except Exception:
        pass
    return {"code": code}


# ============================================================
# 长桥 股票详情 API
# ============================================================
LB_STOCK_DETAIL_URL = "https://m.lbkrs.com/api/forward/v3/quote/stock/detail"


def fetch_stock_detail(code, market="US", product="ST"):
    """
    获取股票实时详情
    GET /api/forward/v3/quote/stock/detail
    返回: 实时价格、今开、昨收、最高最低、成交量、52周高低、
          市盈率、股息率、市值、换手率、量比等
    """
    counter_id = _build_counter_id(code, market, product)

    try:
        resp = requests.get(
            LB_STOCK_DETAIL_URL,
            params={"counter_id": counter_id},
            headers=LONGBRIDGE_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()

        if raw.get("code") != 0:
            return {"code": code, "error": raw.get("message")}

        d = raw.get("data", {})

        # 安全转浮点
        def _f(val, default=0):
            try:
                return float(val) if val else default
            except (ValueError, TypeError):
                return default

        last_done = _f(d.get("last_done"))
        prev_close = _f(d.get("prev_close"))
        change = last_done - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        # 总市值 = 总股本 × 最新价
        total_shares = _f(d.get("total_shares"))
        market_cap = total_shares * last_done if total_shares and last_done else 0

        result = {
            "code": code,
            "counter_id": counter_id,
            "name": d.get("stock_name", code),
            "currency": d.get("currency", "USD"),
            "exchange": d.get("exchange", ""),

            # 实时价格
            "last_done": last_done,
            "open": _f(d.get("open")),
            "prev_close": prev_close,
            "high": _f(d.get("high")),
            "low": _f(d.get("low")),
            "change": round(change, 3),
            "change_pct": round(change_pct, 2),

            # 成交
            "volume": _f(d.get("amount")),          # 成交量（股）
            "turnover": _f(d.get("balance")),        # 成交额
            "turnover_rate": d.get("turnover_rate", "--"),
            "volume_rate": d.get("volume_rate", "--"),

            # 52周
            "year_high": _f(d.get("year_high")),
            "year_low": _f(d.get("year_low")),

            # 估值
            "eps_ttm": d.get("eps_ttm", "--"),
            "dividend_yield": d.get("dps_rate", "--"),   # 股息率TTM
            "dividend_ttm": d.get("dividend_yield", "--"),  # 股息TTM
            "bps": d.get("bps", "--"),

            # 市值
            "market_cap": market_cap,
            "total_shares": total_shares,
            "circulating_shares": _f(d.get("circulating_shares")),

            # 盘前盘后
            "market_price": _f(d.get("market_price")),
            "market_high": _f(d.get("market_high")),
            "market_low": _f(d.get("market_low")),

            # 单位
            "unit": int(d.get("unit", 1)),

            # 交易状态
            "trade_status": d.get("trade_status"),
            "status_desc": d.get("status_desc", {}).get("status_desc", ""),

            # ETF 参考净值
            "etf_nav": _f(d.get("etf_reference", {}).get("nav")) if d.get("etf_reference") else None,

            # 夜盘
            "overnight_price": d.get("overnight_price"),
        }

        return result

    except Exception as e:
        print(f"[stock_data] 长桥股票详情API失败: {e}")
        return {"code": code, "error": str(e)}


# ============================================================
# 获取大盘指数数据
# ============================================================
LB_FIELDS_URL = "https://m.lbkrs.com/api/forward/v2/quote/stock/fields"

MARKET_INDICES = [
    {"counter_id": "IX/US/.DJI", "index": 0},
    {"counter_id": "IX/US/.IXIC", "index": 0},
    {"counter_id": "IX/US/.SPX", "index": 0},
    {"counter_id": "IX/HK/HSI", "index": 0},
    {"counter_id": "IX/HK/HSTECH", "index": 0},
    {"counter_id": "IX/SH/000001", "index": 0},
    {"counter_id": "IX/SZ/399001", "index": 0},
    {"counter_id": "IX/SZ/399006", "index": 0},
]


def fetch_market_indices():
    """批量获取大盘指数行情"""
    try:
        headers = {**LONGBRIDGE_HEADERS, "Content-Type": "application/json"}
        payload = {
            "securities": MARKET_INDICES,
            "fields": [1, 2, 4, 111],
        }
        resp = requests.post(LB_FIELDS_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return []

        results = []
        for s in data.get("data", {}).get("securities", []):
            f = s.get("field", {})
            name = f.get("stock_name", s.get("counter_id", ""))
            last_done = float(f.get("last_done", 0) or 0)
            prev_close = float(f.get("prev_close", 0) or 0)

            if last_done <= 0:
                continue

            change = last_done - prev_close if prev_close > 0 else 0
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0

            results.append({
                "counter_id": s.get("counter_id"),
                "name": name,
                "last_done": round(last_done, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
            })

        return results

    except Exception as e:
        print(f"[stock_data] 获取大盘指数失败: {e}")
        return []


# ============================================================
# 公司简介 API（带 MongoDB 缓存）
# ============================================================
LB_COMPANY_WIKI_URL = "https://m.lbkrs.com/api/forward/stock-info/company-wiki-agg"


def fetch_company_info(code, market="US", product="ST"):
    """
    获取公司简介信息
    优先从 MongoDB 缓存读取，没有则从长桥 API 抓取并缓存
    """
    counter_id = _build_counter_id(code, market, product)

    # 1. 先查 MongoDB 缓存
    col = _safe_get_collection("company_info")
    if col is not None:
        try:
            cached = col.find_one({"counter_id": counter_id}, {"_id": 0})
            if cached:
                # 转换 datetime 为字符串（兼容旧缓存）
                for k, v in cached.items():
                    if isinstance(v, datetime):
                        cached[k] = v.isoformat()
                return cached
        except Exception:
            pass

    # 2. 从长桥 API 抓取
    try:
        resp = requests.get(
            LB_COMPANY_WIKI_URL,
            params={"counter_id": counter_id},
            headers=LONGBRIDGE_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()

        if raw.get("code") != 0:
            return {"counter_id": counter_id, "error": raw.get("message")}

        data = raw.get("data") or {}
        basic = data.get("basic_info") or {}
        profile = data.get("company_profile") or {}
        industry = basic.get("industry") or {}

        result = {
            "counter_id": counter_id,
            "code": code,
            "name": basic.get("name", code),
            "intro": basic.get("intro", ""),
            "profile": basic.get("profile", ""),
            "icon": basic.get("icon", ""),
            "logo": basic.get("logo", ""),
            "industry_name": industry.get("name", ""),
            "company_name": profile.get("company_name", ""),
            "address": profile.get("address", ""),
            "webpage": profile.get("webpage", ""),
            "updated_at": datetime.now().isoformat(),
        }

        # 3. 缓存到 MongoDB
        if col is not None:
            try:
                col.update_one(
                    {"counter_id": counter_id},
                    {"$set": result},
                    upsert=True,
                )
            except Exception:
                pass

        return result

    except Exception as e:
        print(f"[stock_data] 获取公司简介失败: {e}")
        return {"counter_id": counter_id, "code": code}


# ============================================================
# 日程/公告（分红、拆股等公司事件）
# ============================================================
LB_COMPANY_ACT_URL = "https://m.lbkrs.com/api/forward/v2/stock-info/companyact"

def fetch_company_actions(code, market="US", product="ST"):
    """
    获取公司日程/公告（分红派息、拆股等）
    """
    counter_id = f"{product}/{market}/{code}"

    try:
        resp = requests.get(
            LB_COMPANY_ACT_URL,
            params={
                "counter_id": counter_id,
                "req_type": "1",
                "version": "2",
            },
            headers=LONGBRIDGE_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()

        if raw.get("code") != 0:
            return []

        items = (raw.get("data") or {}).get("items") or []
        return items

    except Exception as e:
        print(f"[stock_data] 获取日程数据失败: {e}")
        return []
