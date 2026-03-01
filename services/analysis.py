"""
技术分析服务 - 压力位/支撑位/技术指标
"""
import numpy as np
import pandas as pd
from services.stock_data import fetch_kline


def calc_support_resistance(code, days=120, period="daily", market="US", product="ST"):
    """
    计算压力位和支撑位
    方法：综合近期高低点 + 均线系统 + 布林带
    period: 使用哪个周期的 K 线数据（daily/weekly/monthly/5min 等）
    :return: {
        "support": [{"price": 100, "type": "近期低点", "strength": "强", "date": "..."}, ...],
        "resistance": [{"price": 120, "type": "MA60", "strength": "中", "date": "..."}, ...],
        "current_price": 110,
    }
    """
    kline = fetch_kline(code, period=period, market=market, product=product)
    if not kline or len(kline) < 20:
        return {"support": [], "resistance": [], "current_price": 0}

    df = pd.DataFrame(kline)
    current_price = df["close"].iloc[-1]

    supports = []
    resistances = []

    # === 方法1: 近期高低点 ===
    recent = df.tail(days)
    highs = recent["high"].values
    lows = recent["low"].values
    dates = recent["date"].values if "date" in recent.columns else [None] * len(recent)

    # 寻找局部极值点（前后5日内的最高/最低）
    window = 5
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i - window: i + window + 1]):
            price = float(highs[i])
            date_raw = str(dates[i])[:10] if dates[i] else ""
            # 格式化日期：20260211 → 2026-02-11
            date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) >= 8 and date_raw[:4].isdigit() else date_raw
            if price > current_price:
                resistances.append({"price": price, "type": "近期高点", "strength": "强", "date": date_str})
        if lows[i] == min(lows[i - window: i + window + 1]):
            price = float(lows[i])
            date_raw = str(dates[i])[:10] if dates[i] else ""
            # 格式化日期：20260211 → 2026-02-11
            date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) >= 8 and date_raw[:4].isdigit() else date_raw
            if price < current_price:
                supports.append({"price": price, "type": "近期低点", "strength": "强", "date": date_str})

    # === 方法2: 均线系统 ===
    ma_periods = [5, 10, 20, 60, 120, 250]
    for period in ma_periods:
        if len(df) >= period:
            ma_value = float(df["close"].tail(period).mean())
            entry = {"price": round(ma_value, 2), "type": f"MA{period}", "strength": "中", "date": f"近{period}日"}
            if ma_value > current_price:
                resistances.append(entry)
            elif ma_value < current_price:
                supports.append(entry)

    # === 方法3: 布林带 ===
    if len(df) >= 20:
        boll = calc_bollinger(df["close"].values)
        if boll:
            if boll["upper"] > current_price:
                resistances.append({"price": boll["upper"], "type": "布林上轨", "strength": "中", "date": "近20日"})
            if boll["lower"] < current_price:
                supports.append({"price": boll["lower"], "type": "布林下轨", "strength": "中", "date": "近20日"})

    # 去重 & 排序（价格接近的合并）
    supports = _deduplicate_levels(supports, threshold=0.02)
    resistances = _deduplicate_levels(resistances, threshold=0.02)

    # 按日期降序（最新在前），非日期格式的排到后面
    def _date_sort_key(item):
        d = item.get("date", "")
        # 标准日期格式 YYYY-MM-DD 可直接比较
        if d and len(d) >= 10 and d[4] == '-':
            return d
        return "0000-00-00"  # 非日期排最后

    supports.sort(key=_date_sort_key, reverse=True)
    resistances.sort(key=_date_sort_key, reverse=True)

    return {
        "support": supports[:5],       # 最多5个
        "resistance": resistances[:5],
        "current_price": round(float(current_price), 2),
    }


def calc_moving_averages(code, market="US", product="ST"):
    """
    计算多周期均线
    :return: {"ma5": [...], "ma10": [...], ...}
    """
    kline = fetch_kline(code, market=market, product=product)
    if not kline:
        return {}

    df = pd.DataFrame(kline)
    closes = df["close"].values
    result = {}

    for period in [5, 10, 20, 60, 120, 250]:
        if len(closes) >= period:
            ma = pd.Series(closes).rolling(window=period).mean()
            result[f"ma{period}"] = [
                {"date": kline[i]["date"], "value": round(float(v), 2)}
                for i, v in enumerate(ma) if not np.isnan(v)
            ]

    return result


def calc_bollinger(closes, period=20, num_std=2):
    """计算布林带"""
    if len(closes) < period:
        return None
    sma = float(np.mean(closes[-period:]))
    std = float(np.std(closes[-period:]))
    return {
        "upper": round(sma + num_std * std, 2),
        "middle": round(sma, 2),
        "lower": round(sma - num_std * std, 2),
    }


def calc_macd(code, fast=12, slow=26, signal=9, market="US", product="ST"):
    """计算 MACD"""
    kline = fetch_kline(code, market=market, product=product)
    if not kline or len(kline) < slow + signal:
        return []

    closes = pd.Series([k["close"] for k in kline])
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = 2 * (dif - dea)

    result = []
    for i in range(len(kline)):
        result.append({
            "date": kline[i]["date"],
            "dif": round(float(dif.iloc[i]), 4),
            "dea": round(float(dea.iloc[i]), 4),
            "macd": round(float(macd_hist.iloc[i]), 4),
        })
    return result


def calc_kdj(code, n=9, m1=3, m2=3, market="US", product="ST"):
    """计算 KDJ"""
    kline = fetch_kline(code, market=market, product=product)
    if not kline or len(kline) < n:
        return []

    df = pd.DataFrame(kline)
    low_list = df["low"].rolling(window=n, min_periods=n).min()
    high_list = df["high"].rolling(window=n, min_periods=n).max()
    rsv = (df["close"] - low_list) / (high_list - low_list) * 100

    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d

    result = []
    for i in range(len(kline)):
        if not np.isnan(k.iloc[i]):
            result.append({
                "date": kline[i]["date"],
                "k": round(float(k.iloc[i]), 2),
                "d": round(float(d.iloc[i]), 2),
                "j": round(float(j.iloc[i]), 2),
            })
    return result


def get_technical_summary(code, market="US", product="ST"):
    """
    获取技术指标综合概要（供 AI Tool Calling 使用）
    """
    sr = calc_support_resistance(code, market=market, product=product)
    macd = calc_macd(code, market=market, product=product)
    kdj = calc_kdj(code, market=market, product=product)
    ma = calc_moving_averages(code, market=market, product=product)

    # 均线排列判断
    ma_arrangement = "未知"
    if ma.get("ma5") and ma.get("ma10") and ma.get("ma20"):
        ma5_val = ma["ma5"][-1]["value"] if ma["ma5"] else 0
        ma10_val = ma["ma10"][-1]["value"] if ma["ma10"] else 0
        ma20_val = ma["ma20"][-1]["value"] if ma["ma20"] else 0
        if ma5_val > ma10_val > ma20_val:
            ma_arrangement = "多头排列（看涨信号）"
        elif ma5_val < ma10_val < ma20_val:
            ma_arrangement = "空头排列（看跌信号）"
        else:
            ma_arrangement = "交叉纠缠（震荡信号）"

    # MACD 状态
    macd_status = "未知"
    if macd:
        latest = macd[-1]
        if latest["dif"] > latest["dea"]:
            macd_status = f"金叉，DIF={latest['dif']}, DEA={latest['dea']}"
        else:
            macd_status = f"死叉，DIF={latest['dif']}, DEA={latest['dea']}"

    # KDJ 状态
    kdj_status = "未知"
    if kdj:
        latest = kdj[-1]
        if latest["k"] > 80:
            kdj_status = f"超买区，K={latest['k']}, D={latest['d']}, J={latest['j']}"
        elif latest["k"] < 20:
            kdj_status = f"超卖区，K={latest['k']}, D={latest['d']}, J={latest['j']}"
        else:
            kdj_status = f"中性区，K={latest['k']}, D={latest['d']}, J={latest['j']}"

    return {
        "current_price": sr["current_price"],
        "support_levels": sr["support"],
        "resistance_levels": sr["resistance"],
        "ma_arrangement": ma_arrangement,
        "macd_status": macd_status,
        "kdj_status": kdj_status,
    }


def _deduplicate_levels(levels, threshold=0.02):
    """去除价格相近的重复位，保留 strength 更强的"""
    if not levels:
        return []
    result = []
    strength_order = {"强": 3, "中": 2, "弱": 1}
    for level in sorted(levels, key=lambda x: -strength_order.get(x["strength"], 0)):
        is_dup = False
        for existing in result:
            if abs(level["price"] - existing["price"]) / existing["price"] < threshold:
                is_dup = True
                break
        if not is_dup:
            result.append(level)
    return result
