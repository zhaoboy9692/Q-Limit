"""
K线形态识别 + 趋势结构检测 + 假突破预警
综合技术分析预警模块
"""
import numpy as np
import pandas as pd
from services.stock_data import fetch_kline


# ============================================================
# 1. 经典K线形态识别
# ============================================================

def detect_candlestick_patterns(kline_data, lookback=5):
    """
    检测经典K线形态
    返回: [{"date": "...", "pattern": "锤子线", "signal": "看涨", "desc": "..."}, ...]
    """
    if not kline_data or len(kline_data) < 3:
        return []

    df = pd.DataFrame(kline_data)
    results = []

    for i in range(2, len(df)):
        o, h, l, c = df.iloc[i]["open"], df.iloc[i]["high"], df.iloc[i]["low"], df.iloc[i]["close"]
        body = abs(c - o)
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        total_range = h - l

        if total_range == 0:
            continue

        date = df.iloc[i].get("date", "")

        # 前一根K线
        o1, h1, l1, c1 = df.iloc[i-1]["open"], df.iloc[i-1]["high"], df.iloc[i-1]["low"], df.iloc[i-1]["close"]
        body1 = abs(c1 - o1)

        # 前两根K线
        o2, h2, l2, c2 = df.iloc[i-2]["open"], df.iloc[i-2]["high"], df.iloc[i-2]["low"], df.iloc[i-2]["close"]

        # === 锤子线 (Hammer) ===
        # 下影线是实体的2倍以上，上影线很短，出现在下跌趋势中
        if lower_shadow >= body * 2 and upper_shadow < body * 0.5 and body > 0:
            if _is_downtrend(df, i):
                results.append({
                    "date": str(date)[:10], "pattern": "🔨 锤子线",
                    "signal": "看涨", "strength": "中",
                    "desc": "长下影线表示空方力竭，多方反攻信号"
                })

        # === 上吊线 (Hanging Man) ===
        if lower_shadow >= body * 2 and upper_shadow < body * 0.5 and body > 0:
            if _is_uptrend(df, i):
                results.append({
                    "date": str(date)[:10], "pattern": "☠️ 上吊线",
                    "signal": "看跌", "strength": "中",
                    "desc": "出现在上涨趋势顶部，预示可能反转下跌"
                })

        # === 十字星 (Doji) ===
        if body < total_range * 0.1 and total_range > 0:
            results.append({
                "date": str(date)[:10], "pattern": "✝️ 十字星",
                "signal": "观望", "strength": "弱",
                "desc": "多空力量均衡，趋势可能反转"
            })

        # === 吞没形态 (Engulfing) ===
        if body1 > 0 and body > body1 * 1.2:
            # 看涨吞没
            if c1 < o1 and c > o and o <= c1 and c >= o1:
                if _is_downtrend(df, i):
                    results.append({
                        "date": str(date)[:10], "pattern": "🐂 看涨吞没",
                        "signal": "看涨", "strength": "强",
                        "desc": "大阳线完全包裹前一根阴线，强烈反转信号"
                    })
            # 看跌吞没
            if c1 > o1 and c < o and o >= c1 and c <= o1:
                if _is_uptrend(df, i):
                    results.append({
                        "date": str(date)[:10], "pattern": "🐻 看跌吞没",
                        "signal": "看跌", "strength": "强",
                        "desc": "大阴线完全包裹前一根阳线，强烈反转信号"
                    })

        # === 黄昏之星 (Evening Star) ===
        if i >= 2:
            body2 = abs(c2 - o2)
            if (c2 > o2 and body2 > total_range * 0.3 and  # 第一根：大阳线
                abs(c1 - o1) < body2 * 0.3 and             # 第二根：小实体（星）
                min(o1, c1) > max(o2, c2) and               # 向上跳空
                c < o and body > body2 * 0.5):              # 第三根：大阴线
                results.append({
                    "date": str(date)[:10], "pattern": "🌇 黄昏之星",
                    "signal": "看跌", "strength": "强",
                    "desc": "经典顶部反转形态，大阳+星+大阴"
                })

        # === 黎明之星 (Morning Star) ===
        if i >= 2:
            body2 = abs(c2 - o2)
            if (c2 < o2 and body2 > total_range * 0.3 and  # 第一根：大阴线
                abs(c1 - o1) < body2 * 0.3 and             # 第二根：小实体（星）
                max(o1, c1) < min(o2, c2) and               # 向下跳空
                c > o and body > body2 * 0.5):              # 第三根：大阳线
                results.append({
                    "date": str(date)[:10], "pattern": "🌅 黎明之星",
                    "signal": "看涨", "strength": "强",
                    "desc": "经典底部反转形态，大阴+星+大阳"
                })

        # === 射击之星 (Shooting Star) ===
        if upper_shadow >= body * 2 and lower_shadow < body * 0.5 and body > 0:
            if _is_uptrend(df, i):
                results.append({
                    "date": str(date)[:10], "pattern": "💫 射击之星",
                    "signal": "看跌", "strength": "中",
                    "desc": "长上影线表示上方承压严重，可能反转下跌"
                })

        # === 三只乌鸦 (Three Black Crows) ===
        if i >= 2:
            if (c2 < o2 and c1 < o1 and c < o and
                c1 < c2 and c < c1 and
                abs(c2-o2) > total_range * 0.2 and
                abs(c1-o1) > total_range * 0.2):
                results.append({
                    "date": str(date)[:10], "pattern": "🦅 三只乌鸦",
                    "signal": "看跌", "strength": "强",
                    "desc": "连续三根阴线，空头强势，趋势延续"
                })

        # === 三白兵 (Three White Soldiers) ===
        if i >= 2:
            if (c2 > o2 and c1 > o1 and c > o and
                c1 > c2 and c > c1 and
                abs(c2-o2) > total_range * 0.2 and
                abs(c1-o1) > total_range * 0.2):
                results.append({
                    "date": str(date)[:10], "pattern": "🕊️ 三白兵",
                    "signal": "看涨", "strength": "强",
                    "desc": "连续三根阳线，多头强势，趋势延续"
                })

    # 只返回最近的若干个形态
    return results[-lookback:]


def _is_downtrend(df, idx, period=5):
    """判断前几根K线是否处于下跌趋势"""
    if idx < period:
        return False
    closes = df["close"].iloc[idx-period: idx].values
    return closes[0] > closes[-1] and np.mean(np.diff(closes)) < 0


def _is_uptrend(df, idx, period=5):
    """判断前几根K线是否处于上涨趋势"""
    if idx < period:
        return False
    closes = df["close"].iloc[idx-period: idx].values
    return closes[0] < closes[-1] and np.mean(np.diff(closes)) > 0


# ============================================================
# 2. 趋势结构识别
# ============================================================

def detect_trend_structures(kline_data, lookback=3):
    """
    检测趋势结构形态
    返回: [{"pattern": "头肩顶", "signal": "看跌", "desc": "..."}, ...]
    """
    if not kline_data or len(kline_data) < 30:
        return []

    df = pd.DataFrame(kline_data)
    closes = df["close"].values
    results = []

    # === MACD 背离检测 ===
    results.extend(_detect_divergence(df))

    # === 头肩顶/底检测 ===
    results.extend(_detect_head_shoulders(df))

    # === 楔形结构检测 ===
    results.extend(_detect_wedge(df))

    # === 双顶/双底 ===
    results.extend(_detect_double_top_bottom(df))

    return results[-lookback:]


def _detect_divergence(df):
    """检测 MACD 顶背离 / 底背离"""
    results = []
    closes = df["close"].values

    if len(closes) < 26:
        return results

    # 计算 MACD
    ema12 = pd.Series(closes).ewm(span=12, adjust=False).mean()
    ema26 = pd.Series(closes).ewm(span=26, adjust=False).mean()
    dif = (ema12 - ema26).values

    # 寻找最近两个价格高点/低点
    window = 10
    n = len(closes)

    # ---- 顶背离：价格新高但 DIF 没有新高 ----
    highs_idx = []
    for i in range(window, n - 2):
        if closes[i] == max(closes[max(0, i-window):min(n, i+window+1)]):
            highs_idx.append(i)

    if len(highs_idx) >= 2:
        i1, i2 = highs_idx[-2], highs_idx[-1]
        if closes[i2] > closes[i1] and dif[i2] < dif[i1]:
            date = str(df.iloc[i2].get("date", ""))[:10]
            results.append({
                "date": date, "pattern": "📉 顶背离",
                "signal": "看跌", "strength": "强",
                "desc": f"价格创新高但MACD未创新高，趋势可能反转下跌"
            })

    # ---- 底背离：价格新低但 DIF 没有新低 ----
    lows_idx = []
    for i in range(window, n - 2):
        if closes[i] == min(closes[max(0, i-window):min(n, i+window+1)]):
            lows_idx.append(i)

    if len(lows_idx) >= 2:
        i1, i2 = lows_idx[-2], lows_idx[-1]
        if closes[i2] < closes[i1] and dif[i2] > dif[i1]:
            date = str(df.iloc[i2].get("date", ""))[:10]
            results.append({
                "date": date, "pattern": "📈 底背离",
                "signal": "看涨", "strength": "强",
                "desc": f"价格创新低但MACD未创新低，趋势可能反转上涨"
            })

    return results


def _detect_head_shoulders(df):
    """检测头肩顶/头肩底"""
    results = []
    closes = df["close"].values
    n = len(closes)
    if n < 30:
        return results

    window = 5
    peaks = []
    troughs = []

    for i in range(window, n - window):
        if closes[i] == max(closes[i-window: i+window+1]):
            peaks.append((i, closes[i]))
        if closes[i] == min(closes[i-window: i+window+1]):
            troughs.append((i, closes[i]))

    # 头肩顶: 3个峰，中间最高
    if len(peaks) >= 3:
        p1, p2, p3 = peaks[-3], peaks[-2], peaks[-1]
        if p2[1] > p1[1] and p2[1] > p3[1] and abs(p1[1] - p3[1]) / p2[1] < 0.05:
            date = str(df.iloc[p3[0]].get("date", ""))[:10]
            results.append({
                "date": date, "pattern": "👤 头肩顶",
                "signal": "看跌", "strength": "强",
                "desc": "经典反转形态：左肩-头-右肩，预示上升趋势终结"
            })

    # 头肩底: 3个谷，中间最低
    if len(troughs) >= 3:
        t1, t2, t3 = troughs[-3], troughs[-2], troughs[-1]
        if t2[1] < t1[1] and t2[1] < t3[1] and abs(t1[1] - t3[1]) / t2[1] < 0.05:
            date = str(df.iloc[t3[0]].get("date", ""))[:10]
            results.append({
                "date": date, "pattern": "🙃 头肩底",
                "signal": "看涨", "strength": "强",
                "desc": "经典反转形态：左肩-底-右肩，预示下降趋势终结"
            })

    return results


def _detect_wedge(df):
    """检测楔形结构（收敛三角形）"""
    results = []
    closes = df["close"].values
    n = len(closes)
    if n < 20:
        return results

    # 使用最近20根K线
    recent = closes[-20:]
    highs = df["high"].values[-20:]
    lows = df["low"].values[-20:]

    # 拟合高点和低点的线性趋势
    x = np.arange(len(recent))

    high_slope = np.polyfit(x, highs, 1)[0]
    low_slope = np.polyfit(x, lows, 1)[0]

    # 上升楔形：高点和低点都上升，但高点斜率变小（收敛）
    if high_slope > 0 and low_slope > 0 and high_slope < low_slope:
        date = str(df.iloc[-1].get("date", ""))[:10]
        results.append({
            "date": date, "pattern": "📐 上升楔形",
            "signal": "看跌", "strength": "中",
            "desc": "价格高低点收敛上行，突破方向通常向下"
        })

    # 下降楔形：高点和低点都下降，但低点斜率变小（收敛）
    if high_slope < 0 and low_slope < 0 and abs(low_slope) < abs(high_slope):
        date = str(df.iloc[-1].get("date", ""))[:10]
        results.append({
            "date": date, "pattern": "📐 下降楔形",
            "signal": "看涨", "strength": "中",
            "desc": "价格高低点收敛下行，突破方向通常向上"
        })

    # 对称三角形
    if high_slope < 0 and low_slope > 0:
        date = str(df.iloc[-1].get("date", ""))[:10]
        results.append({
            "date": date, "pattern": "🔺 对称三角形",
            "signal": "观望", "strength": "中",
            "desc": "价格高低点收敛，即将选择方向突破"
        })

    return results


def _detect_double_top_bottom(df):
    """检测双顶/双底"""
    results = []
    closes = df["close"].values
    n = len(closes)
    if n < 20:
        return results

    window = 5
    peaks = []
    troughs = []

    for i in range(window, n - window):
        if closes[i] == max(closes[i-window: i+window+1]):
            peaks.append((i, closes[i]))
        if closes[i] == min(closes[i-window: i+window+1]):
            troughs.append((i, closes[i]))

    # 双顶 (M头)
    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        if abs(p1[1] - p2[1]) / p1[1] < 0.02 and p2[0] - p1[0] >= 5:
            date = str(df.iloc[p2[0]].get("date", ""))[:10]
            results.append({
                "date": date, "pattern": "🔝 M头（双顶）",
                "signal": "看跌", "strength": "强",
                "desc": "两次触及相似高点后回落，上方压力强"
            })

    # 双底 (W底)
    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        if abs(t1[1] - t2[1]) / t1[1] < 0.02 and t2[0] - t1[0] >= 5:
            date = str(df.iloc[t2[0]].get("date", ""))[:10]
            results.append({
                "date": date, "pattern": "🔻 W底（双底）",
                "signal": "看涨", "strength": "强",
                "desc": "两次触及相似低点后反弹，下方支撑强"
            })

    return results


# ============================================================
# 3. 假突破预警
# ============================================================

def detect_false_breakout(kline_data, support_resistance=None):
    """
    假突破预警（量价背离检测）
    - 突破支撑位/压力位后成交量未放大 → 假突破
    - 突破后快速回收 → 诱多/诱空
    返回: [{"date": "...", "warning": "疑似假突破...", "type": "诱多/诱空"}, ...]
    """
    if not kline_data or len(kline_data) < 10:
        return []

    df = pd.DataFrame(kline_data)
    results = []

    # 计算平均成交量（20日）
    volumes = df["volume"].values
    avg_vol_20 = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)

    # 从最近5根K线检测突破行为
    for i in range(max(len(df) - 5, 1), len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i - 1]
        date = str(curr.get("date", ""))[:10]

        curr_vol = curr["volume"]
        close = curr["close"]
        prev_close = prev["close"]

        # === 假向上突破（诱多）===
        # 价格向上突破前期高点，但成交量低于平均
        if close > prev_close and curr_vol < avg_vol_20 * 0.8:
            # 检查是否突破了近期阻力位
            recent_high = df["high"].iloc[max(0, i-20):i].max()
            if curr["high"] >= recent_high * 0.995:
                results.append({
                    "date": date,
                    "warning": f"⚠️ 疑似诱多：价格突破 {recent_high:.2f} 附近高点但成交量萎缩({curr_vol/avg_vol_20*100:.0f}%均量)",
                    "type": "诱多",
                    "strength": "中",
                    "price": round(close, 2),
                    "volume_ratio": round(curr_vol / avg_vol_20 * 100, 1),
                })

        # === 假向下突破（诱空）===
        if close < prev_close and curr_vol < avg_vol_20 * 0.8:
            recent_low = df["low"].iloc[max(0, i-20):i].min()
            if curr["low"] <= recent_low * 1.005:
                results.append({
                    "date": date,
                    "warning": f"⚠️ 疑似诱空：价格跌破 {recent_low:.2f} 附近低点但成交量萎缩({curr_vol/avg_vol_20*100:.0f}%均量)",
                    "type": "诱空",
                    "strength": "中",
                    "price": round(close, 2),
                    "volume_ratio": round(curr_vol / avg_vol_20 * 100, 1),
                })

        # === 冲高回落（上影线长 + 放量）===
        upper_shadow = curr["high"] - max(curr["open"], close)
        body = abs(close - curr["open"])
        if upper_shadow > body * 2 and curr_vol > avg_vol_20 * 1.5 and close < curr["open"]:
            results.append({
                "date": date,
                "warning": f"⚠️ 放量冲高回落：上影线极长，主力可能出货",
                "type": "诱多",
                "strength": "强",
                "price": round(close, 2),
                "volume_ratio": round(curr_vol / avg_vol_20 * 100, 1),
            })

        # === 急跌反弹（下影线长 + 放量）===
        lower_shadow = min(curr["open"], close) - curr["low"]
        if lower_shadow > body * 2 and curr_vol > avg_vol_20 * 1.5 and close > curr["open"]:
            results.append({
                "date": date,
                "warning": f"⚠️ 放量急跌反弹：下影线极长，可能是洗盘吸筹",
                "type": "洗盘",
                "strength": "中",
                "price": round(close, 2),
                "volume_ratio": round(curr_vol / avg_vol_20 * 100, 1),
            })

    return results[-3:]


# ============================================================
# 综合分析入口
# ============================================================

def analyze_patterns(code, period="daily", market="US", product="ST"):
    """
    综合分析：K线形态 + 趋势结构 + 假突破预警
    """
    kline = fetch_kline(code, period=period, market=market, product=product)
    if not kline:
        return {
            "candlestick_patterns": [],
            "trend_structures": [],
            "false_breakouts": [],
            "summary": "暂无数据",
        }

    patterns = detect_candlestick_patterns(kline, lookback=5)
    trends = detect_trend_structures(kline, lookback=3)
    breakouts = detect_false_breakout(kline)

    # 按日期降序排列（最新在前）
    patterns.sort(key=lambda x: x.get("date", ""), reverse=True)
    trends.sort(key=lambda x: x.get("date", ""), reverse=True)
    breakouts.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 生成综合摘要
    signals = []
    bullish = sum(1 for p in patterns + trends if p.get("signal") == "看涨")
    bearish = sum(1 for p in patterns + trends if p.get("signal") == "看跌")
    warnings = len(breakouts)

    if bullish > bearish:
        signals.append(f"多头信号较强（看涨{bullish}个 vs 看跌{bearish}个）")
    elif bearish > bullish:
        signals.append(f"空头信号较强（看跌{bearish}个 vs 看涨{bullish}个）")
    else:
        signals.append("多空信号均衡，建议观望")

    if warnings > 0:
        signals.append(f"⚠️ 检测到{warnings}个假突破预警，注意风险")

    return {
        "candlestick_patterns": patterns,
        "trend_structures": trends,
        "false_breakouts": breakouts,
        "summary": "；".join(signals),
    }
