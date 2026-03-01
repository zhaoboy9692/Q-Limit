"""
财报分析服务 — 接入长桥 financial-reports API
支持 BS(资产负债表) / IS(利润表) / CF(现金流量表)
"""
import requests
from datetime import datetime
from models.database import get_collection
from services.stock_data import fetch_stock_info

# 长桥财报 API
LB_FINANCIAL_URL = "https://m.lbkrs.com/api/forward/v2/stock-info/financial-reports"

LB_HEADERS = {
    "accept": "application/json",
    "x-app-id": "longport",
    "x-domain-region": "CN",
    "origin": "https://longportapp.cn",
    "referer": "https://longportapp.cn/",
}


def _build_counter_id(code, market="US", product="ST"):
    """构建 counter_id: ST/US/TSLA"""
    if "/" in code:
        return code
    c = code.replace(".US", "").replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    return f"{product}/{market}/{c}"


def fetch_financial_from_longbridge(code, market="US", product="ST", report="qf"):
    """
    从长桥 API 获取财报数据
    report: qf=季报(默认), af=年报
    kind: ALL
    返回原始 API 数据中的 BS/IS/CF
    """
    counter_id = _build_counter_id(code, market, product)

    try:
        resp = requests.get(
            LB_FINANCIAL_URL,
            params={"counter_id": counter_id, "report": report, "kind": "ALL"},
            headers=LB_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()

        if raw.get("code") != 0:
            print(f"[financial] 长桥财报API错误: {raw.get('message')}")
            return None

        data = raw.get("data", {})
        sheet_data = data.get("list", {})

        result = {
            "report_type": report,
            "sheets": {},
            "key_metrics": {},
        }

        # 解析三大报表
        for sheet_key in ["BS", "IS", "CF"]:
            sheet = sheet_data.get(sheet_key, {})
            indicators = sheet.get("indicators", [])
            parsed_indicators = []

            for ind in indicators:
                parsed_accounts = []
                for acc in ind.get("accounts", []):
                    values = acc.get("values", [])
                    parsed_values = []
                    for v in values[:8]:  # 最多8期
                        parsed_values.append({
                            "period": v.get("period", ""),
                            "value": v.get("value", ""),
                            "yoy": v.get("yoy", ""),
                        })
                    parsed_accounts.append({
                        "name": acc.get("name", ""),
                        "field": acc.get("field", ""),
                        "ranking": acc.get("industry_ranking", ""),
                        "percent": acc.get("percent", False),
                        "values": parsed_values,
                    })
                parsed_indicators.append({
                    "title": ind.get("title", ""),
                    "currency": ind.get("currency", ""),
                    "accounts": parsed_accounts,
                })

            result["sheets"][sheet_key] = parsed_indicators

        # 提取关键指标（给前端快速展示）
        result["key_metrics"] = _extract_key_metrics(sheet_data)

        return result

    except Exception as e:
        print(f"[financial] 长桥财报API调用失败: {e}")
        return None


def _extract_key_metrics(sheet_data):
    """从报表数据中提取关键财务指标"""
    metrics = {}

    def _get_latest(sheet_key, field):
        """获取某个字段的最新值"""
        sheet = sheet_data.get(sheet_key, {})
        for ind in sheet.get("indicators", []):
            for acc in ind.get("accounts", []):
                if acc.get("field") == field:
                    vals = acc.get("values", [])
                    if vals and vals[0].get("value"):
                        try:
                            return float(vals[0]["value"])
                        except (ValueError, TypeError):
                            return None
        return None

    def _get_latest_period(sheet_key, field):
        """获取某个字段的最新期间"""
        sheet = sheet_data.get(sheet_key, {})
        for ind in sheet.get("indicators", []):
            for acc in ind.get("accounts", []):
                if acc.get("field") == field:
                    vals = acc.get("values", [])
                    if vals:
                        return vals[0].get("period", "")
        return ""

    # IS 利润表
    metrics["eps"] = _get_latest("IS", "EPS")
    metrics["roe"] = _get_latest("IS", "ROE")
    metrics["revenue"] = _get_latest("IS", "OperatingRevenue")
    metrics["net_profit"] = _get_latest("IS", "NetProfit")
    metrics["operating_income"] = _get_latest("IS", "OperatingIncome")
    metrics["gross_margin"] = _get_latest("IS", "GrossMgn")
    metrics["net_margin"] = _get_latest("IS", "NetProfitMargin")

    # BS 资产负债表
    metrics["total_assets"] = _get_latest("BS", "TotalAssets")
    metrics["total_liability"] = _get_latest("BS", "TotalLiability")
    metrics["bps"] = _get_latest("BS", "BPS")
    metrics["leverage"] = _get_latest("BS", "Leverage")
    metrics["asset_turnover"] = _get_latest("BS", "AssetTurn")

    # CF 现金流
    metrics["operating_cf"] = _get_latest("CF", "NetOperateCashFlow")
    metrics["investing_cf"] = _get_latest("CF", "NetInvestCashFlow")
    metrics["financing_cf"] = _get_latest("CF", "NetFinanceCashFlow")
    metrics["free_cf"] = _get_latest("CF", "NetFreeCashFlow")
    metrics["capex"] = _get_latest("CF", "CapEx")

    # 最新期间
    metrics["latest_period"] = _get_latest_period("IS", "EPS")

    return metrics


def get_financial_report(code, market="US", product="ST"):
    """
    获取财报核心数据（优先长桥 API）
    """
    # 1. 优先长桥 API
    lb_data = fetch_financial_from_longbridge(code, market, product)
    if lb_data:
        km = lb_data.get("key_metrics", {})
        summary = _generate_summary_from_metrics(km)
        lb_data["summary"] = summary
        return lb_data

    # 2. 降级到 MongoDB
    col = get_collection("financial_reports")
    reports = list(col.find(
        {"code": code}, {"_id": 0}
    ).sort("report_date", -1).limit(12))

    if reports:
        latest = reports[0]
        dupont = _calc_dupont(latest)
        yoy = _calc_yoy(reports)
        return {
            "report_type": "cached",
            "sheets": {},
            "key_metrics": {
                "revenue": latest.get("revenue"),
                "net_profit": latest.get("net_profit"),
                "gross_margin": latest.get("gross_margin"),
                "net_margin": latest.get("net_margin"),
                "roe": latest.get("roe"),
                "eps": latest.get("eps"),
            },
            "summary": _generate_summary_old(latest, dupont, yoy),
        }

    # 3. 无数据
    return {
        "report_type": "none",
        "sheets": {},
        "key_metrics": {},
        "summary": f"股票{code}暂无财报数据。",
    }


def _generate_summary_from_metrics(km):
    """从关键指标生成摘要"""
    parts = []
    period = km.get("latest_period", "")
    if period:
        parts.append(f"最新财报({period})")

    if km.get("revenue"):
        parts.append(f"营收{km['revenue']/1e9:.2f}B")
    if km.get("net_profit"):
        parts.append(f"净利润{km['net_profit']/1e9:.2f}B")
    if km.get("eps"):
        parts.append(f"EPS={km['eps']:.4f}")
    if km.get("roe"):
        parts.append(f"ROE={km['roe']:.2f}%")
    if km.get("gross_margin"):
        parts.append(f"毛利率{km['gross_margin']:.1f}%")
    if km.get("net_margin"):
        parts.append(f"净利率{km['net_margin']:.1f}%")

    return "，".join(parts) + "。" if parts else "暂无财报数据。"


# ============================================================
# 旧版兼容函数
# ============================================================

def save_financial_report(reports):
    """存储财报数据（供爬虫调用）"""
    col = get_collection("financial_reports")
    for r in reports:
        r.setdefault("created_at", datetime.now())
        col.update_one(
            {"code": r["code"], "report_date": r["report_date"]},
            {"$set": r},
            upsert=True,
        )


def _calc_dupont(report):
    """杜邦分析"""
    net_margin = report.get("net_margin", 0)
    turnover = report.get("asset_turnover", 0)
    multiplier = report.get("equity_multiplier", 0)
    roe = report.get("roe", 0)
    return {
        "roe": round(roe * 100, 2) if roe else 0,
        "net_margin": round(net_margin * 100, 2) if net_margin else 0,
        "asset_turnover": round(turnover, 4) if turnover else 0,
        "equity_multiplier": round(multiplier, 2) if multiplier else 0,
    }


def _calc_yoy(reports):
    """计算同比变化"""
    if len(reports) < 2:
        return {}
    latest = reports[0]
    prev = reports[-1] if len(reports) > 4 else reports[1]
    changes = {}
    for key in ["revenue", "net_profit", "gross_margin", "net_margin", "roe"]:
        curr_val = latest.get(key, 0)
        prev_val = prev.get(key, 0)
        if prev_val and prev_val != 0:
            change = (curr_val - prev_val) / abs(prev_val) * 100
            changes[key] = round(change, 2)
    return changes


def _generate_summary_old(latest, dupont, yoy):
    """旧版摘要生成"""
    parts = []
    if latest.get("revenue"):
        parts.append(f"营收{latest['revenue'] / 1e8:.1f}亿")
    if latest.get("net_profit"):
        parts.append(f"净利润{latest['net_profit'] / 1e8:.1f}亿")
    if dupont.get("roe"):
        parts.append(f"ROE={dupont['roe']:.1f}%")
    return f"最新财报: {'，'.join(parts)}。" if parts else "财报数据不足。"
