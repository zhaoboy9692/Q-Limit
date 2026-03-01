"""
估值分析服务 - PE/PB 分析 + ETF 加仓指标
"""
import numpy as np
import pandas as pd
from services.stock_data import fetch_stock_info, fetch_stock_detail, fetch_kline
from models.database import get_collection


def _get_pe_pb_from_detail(code, market="US", product="ST"):
    """
    从长桥详情 API 获取 PE/PB
    - PE = last_done / eps_ttm
    - PB = last_done / bps
    """
    detail = fetch_stock_detail(code, market=market, product=product)
    if not detail or detail.get("error"):
        return 0, 0, 0

    last_done = detail.get("last_done", 0)
    eps_ttm = detail.get("eps_ttm", "--")
    bps = detail.get("bps", "--")

    pe = 0
    pb = 0
    try:
        eps_val = float(eps_ttm) if eps_ttm not in ("--", "", None) else 0
        if eps_val > 0 and last_done > 0:
            pe = round(last_done / eps_val, 2)
    except (ValueError, TypeError):
        pass

    try:
        bps_val = float(bps) if bps not in ("--", "", None) else 0
        if bps_val > 0 and last_done > 0:
            pb = round(last_done / bps_val, 2)
    except (ValueError, TypeError):
        pass

    return pe, pb, last_done


# ============================================================
# 绝对 PE 区间判断（不依赖历史百分位）
# ============================================================
def _pe_level(pe):
    """
    按绝对 PE 值判断估值水平
    返回 (status, percentile_position)
    percentile_position: 0-100 在进度条上的位置
    """
    if pe <= 0:
        return "--", 50
    if pe < 5:
        return "极低", 5
    elif pe < 10:
        return "低估", 20
    elif pe < 30:
        return "合理", 45
    elif pe < 40:
        return "高", 70
    else:
        return "极高", 95


def _pb_level(pb):
    """
    按绝对 PB 值判断估值水平
    返回 (status, percentile_position)
    """
    if pb <= 0:
        return "--", 50
    if pb < 1:
        return "极低(破净)", 5
    elif pb < 1.5:
        return "偏低", 20
    elif pb < 3:
        return "适中", 40
    elif pb < 5:
        return "适中偏高", 55
    elif pb < 8:
        return "偏高", 65
    elif pb < 15:
        return "高", 80
    elif pb < 30:
        return "很高", 90
    else:
        return "极高", 95


def get_pe_analysis(code, market="US", product="ST"):
    """PE（市盈率）分析"""
    current_pe, _, _ = _get_pe_pb_from_detail(code, market, product)

    # 回退到 stock_info（MongoDB 缓存）
    if current_pe <= 0:
        info = fetch_stock_info(code)
        current_pe = info.get("pe", 0)

    status, position = _pe_level(current_pe)

    # 生成摘要
    if current_pe > 0:
        summary = f"当前PE为{current_pe:.1f}，估值{status}。"
    else:
        summary = "PE数据暂无。"

    return {
        "current_pe": round(current_pe, 2),
        "pe_percentile": round(position, 1),
        "pe_status": status,
        "summary": summary,
    }


def get_pb_analysis(code, market="US", product="ST"):
    """PB（市净率）分析"""
    _, current_pb, _ = _get_pe_pb_from_detail(code, market, product)

    # 回退到 stock_info
    if current_pb <= 0:
        info = fetch_stock_info(code)
        current_pb = info.get("pb", 0)

    status, position = _pb_level(current_pb)

    if current_pb > 0:
        summary = f"当前PB为{current_pb:.2f}，估值{status}。"
    else:
        summary = "PB数据暂无。"

    return {
        "current_pb": round(current_pb, 2),
        "pb_percentile": round(position, 1),
        "pb_status": status,
        "summary": summary,
    }


def get_valuation_summary(code):
    """综合估值概要（供 AI Tool Calling 使用）"""
    pe = get_pe_analysis(code)
    pb = get_pb_analysis(code)

    return {
        "pe": {
            "current": pe["current_pe"],
            "percentile": pe["pe_percentile"],
            "status": pe["pe_status"],
        },
        "pb": {
            "current": pb["current_pb"],
            "percentile": pb["pb_percentile"],
            "status": pb["pb_status"],
        },
        "summary": pe["summary"] + " " + pb["summary"],
    }


def get_stock_advice(pe_data, pb_data):
    """
    根据 PE/PB 综合评分给出加仓/观望/减仓建议
    """
    pe_val = pe_data.get("current_pe", 0)
    pb_val = pb_data.get("current_pb", 0)
    pe_status = pe_data.get("pe_status", "--")
    pb_status = pb_data.get("pb_status", "--")

    if pe_val <= 0 and pb_val <= 0:
        return None

    score = 0  # 正=高估，负=低估
    reasons = []

    # PE 打分
    if pe_val > 0:
        if pe_val < 10:
            score -= 2
            reasons.append(f"📊 PE={pe_val:.1f}，估值极低")
        elif pe_val < 15:
            score -= 1
            reasons.append(f"📊 PE={pe_val:.1f}，估值偏低")
        elif pe_val < 30:
            reasons.append(f"📊 PE={pe_val:.1f}，估值合理")
        elif pe_val < 50:
            score += 1
            reasons.append(f"📊 PE={pe_val:.1f}，估值偏高")
        else:
            score += 2
            reasons.append(f"📊 PE={pe_val:.1f}，估值极高")

    # PB 打分
    if pb_val > 0:
        if pb_val < 1:
            score -= 2
            reasons.append(f"📗 PB={pb_val:.2f}，破净")
        elif pb_val < 1.5:
            score -= 1
            reasons.append(f"📗 PB={pb_val:.2f}，偏低")
        elif pb_val < 5:
            reasons.append(f"📗 PB={pb_val:.2f}，适中")
        elif pb_val < 15:
            score += 1
            reasons.append(f"📗 PB={pb_val:.2f}，偏高")
        else:
            score += 2
            reasons.append(f"📗 PB={pb_val:.2f}，很高")

    # 综合建议
    if score <= -3:
        advice = "💚 强力加仓区"
        advice_desc = "PE/PB 均处于极低区间，估值优势明显"
        level = "strong_buy"
    elif score <= -1:
        advice = "🟢 适合加仓"
        advice_desc = "估值偏低，可考虑适当加仓"
        level = "buy"
    elif score <= 1:
        advice = "🟡 正常持有"
        advice_desc = "估值合理区间，维持当前仓位"
        level = "hold"
    elif score <= 2:
        advice = "🟠 谨慎观望"
        advice_desc = "估值偏高，建议暂停加仓"
        level = "caution"
    else:
        advice = "🔴 建议减仓"
        advice_desc = "估值过高，注意风险控制"
        level = "sell"

    return {
        "advice": advice,
        "advice_desc": advice_desc,
        "advice_level": level,
        "reasons": reasons,
    }


# ============================================================
# ETF / 指数基金 专属加仓指标
# ============================================================

def _calc_rsi(closes, period=14):
    """计算 RSI"""
    if len(closes) < period + 1:
        return 50
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 1)


def get_etf_analysis(code, market="US", product="ST"):
    """
    ETF 专属分析：ATH回撤、RSI、均线偏离率、加仓建议
    当 PE/PB 不可用时（ETF/基金/指数），使用此分析
    """
    kline = fetch_kline(code, period="daily", market=market, product=product)
    if not kline or len(kline) < 20:
        return None

    df = pd.DataFrame(kline)
    closes = df["close"].values
    current_price = float(closes[-1])

    # 1. ATH 回撤
    ath = float(np.max(closes))
    drawdown = round((1 - current_price / ath) * 100, 1) if ath > 0 else 0
    ath_date = ""
    ath_idx = int(np.argmax(closes))
    if ath_idx < len(kline):
        ath_date = str(kline[ath_idx].get("date", ""))[:10]

    # 2. RSI
    rsi = _calc_rsi(closes, 14)
    if rsi < 30:
        rsi_signal = "超卖 — 适合加仓"
        rsi_color = "green"
    elif rsi < 40:
        rsi_signal = "偏弱 — 可考虑加仓"
        rsi_color = "green"
    elif rsi > 70:
        rsi_signal = "超买 — 建议暂停"
        rsi_color = "red"
    elif rsi > 60:
        rsi_signal = "偏强 — 正常持有"
        rsi_color = "yellow"
    else:
        rsi_signal = "中性区间"
        rsi_color = "gray"

    # 3. 均线偏离率
    ma_deviations = {}
    for period in [20, 60, 200]:
        if len(closes) >= period:
            ma = float(np.mean(closes[-period:]))
            dev = round((current_price / ma - 1) * 100, 1)
            ma_deviations[f"ma{period}"] = {
                "ma_value": round(ma, 2),
                "deviation": dev,
                "desc": f"{'高于' if dev >= 0 else '低于'}MA{period} {abs(dev)}%",
            }

    # 4. 综合加仓建议
    score = 0  # 越低越适合加仓
    reasons = []

    # ATH 回撤打分
    if drawdown >= 30:
        score += 3
        reasons.append(f"📉 距高位回撤{drawdown}%，深度回调区")
    elif drawdown >= 20:
        score += 2
        reasons.append(f"📉 距高位回撤{drawdown}%，中度回调")
    elif drawdown >= 10:
        score += 1
        reasons.append(f"📉 距高位回撤{drawdown}%，轻度回调")
    else:
        reasons.append(f"📈 距高位仅回撤{drawdown}%，接近高位")

    # RSI 打分
    if rsi < 30:
        score += 2
        reasons.append(f"🔋 RSI={rsi}，严重超卖")
    elif rsi < 40:
        score += 1
        reasons.append(f"🔋 RSI={rsi}，偏弱")
    elif rsi > 70:
        score -= 1
        reasons.append(f"⚡ RSI={rsi}，超买警告")

    # MA200 偏离率打分
    ma200 = ma_deviations.get("ma200")
    if ma200:
        dev200 = ma200["deviation"]
        if dev200 < -10:
            score += 2
            reasons.append(f"📏 低于MA200 {abs(dev200)}%，严重偏离")
        elif dev200 < -5:
            score += 1
            reasons.append(f"📏 低于MA200 {abs(dev200)}%")
        elif dev200 > 15:
            score -= 1
            reasons.append(f"📏 高于MA200 {dev200}%，过热")

    # 综合建议
    if score >= 4:
        advice = "💚 强力加仓区"
        advice_desc = "多项指标显示超跌，可大幅加仓"
        advice_level = "strong_buy"
    elif score >= 2:
        advice = "🟢 适合加仓"
        advice_desc = "指标偏低位，建议适当加仓"
        advice_level = "buy"
    elif score >= 0:
        advice = "🟡 正常定投"
        advice_desc = "指标中性，维持正常定投节奏"
        advice_level = "hold"
    else:
        advice = "🔴 暂停观望"
        advice_desc = "指标偏高位，建议暂停加仓等回调"
        advice_level = "wait"

    return {
        "current_price": current_price,
        "ath": round(ath, 2),
        "ath_date": ath_date,
        "drawdown": drawdown,
        "rsi": rsi,
        "rsi_signal": rsi_signal,
        "rsi_color": rsi_color,
        "ma_deviations": ma_deviations,
        "advice": advice,
        "advice_desc": advice_desc,
        "advice_level": advice_level,
        "reasons": reasons,
    }
