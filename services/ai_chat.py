"""
AI 多角色辩论聊天服务
支持 Tool Calling，api_key/base_url/model 由前端传入
"""
import json
import requests
from datetime import datetime
from config import AI_MODELS, AI_TOOLS
from models.database import get_collection

# Tool Calling 函数映射
from services.analysis import get_technical_summary, calc_support_resistance
from services.valuation import get_valuation_summary
from services.news import get_news_for_ai
from services.financial import get_financial_report

TOOL_FUNCTIONS = {
    "get_pe_analysis": lambda args: get_valuation_summary(args["stock_code"]),
    "get_support_resistance": lambda args: calc_support_resistance(args["stock_code"]),
    "get_technical_indicators": lambda args: get_technical_summary(args["stock_code"]),
    "get_stock_news": lambda args: get_news_for_ai(args["stock_code"], args.get("limit", 10)),
    "get_financial_report": lambda args: get_financial_report(args["stock_code"]),
    "get_kline_summary": lambda args: _get_kline_summary(args["stock_code"], args.get("days", 30)),
}


def chat_with_role(role, message, stock_code, api_config, session_id=None):
    """
    与指定角色对话（纯聊天模式，适配 Web2API 中转）
    api_config: {"api_key": "xxx", "base_url": "http://...", "model": "gemini-3.0-flash"}
    """
    role_meta = AI_MODELS.get(role)
    if not role_meta:
        yield {"error": f"未知角色: {role}"}
        return

    api_key = api_config.get("api_key", "")
    base_url = api_config.get("base_url", "")
    model = api_config.get("model", "")

    if not api_key or not base_url or not model:
        yield {"error": f"请先在设置中配置 API Key、API 地址和模型。"}
        return

    llm_config = {"api_key": api_key, "base_url": base_url, "model": model}

    messages = _build_messages(role, message, stock_code, session_id)

    # 纯Web2API聊天模式，不传递 tools，防止解析错误
    response_data = _call_llm(llm_config, messages, tools=None)
    
    if not response_data:
        yield {"error": "AI 接口调用失败，请检查 API 地址和密钥"}
        return

    choice = response_data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    
    content = msg.get("content", "")
    if content:
        yield {"content": content, "role": role}
        _save_chat(stock_code, session_id, role, message, content)
    else:
        yield {"error": "AI 未返回有效内容"}


def debate(stock_code, api_config, session_id=None, user_prompt=None):
    """一键辩论：多头→空头→裁判"""
    prompt = user_prompt or f"请对股票 {stock_code} 进行全面分析"

    for role in ["bull", "bear", "judge"]:
        yield {"role": role, "status": "thinking", "content": ""}

        role_prompt = prompt
        if role == "judge":
            role_prompt = f"请综合前面多头和空头的分析，对股票 {stock_code} 给出裁判意见。\n\n用户原始问题: {prompt}"

        # 从传递的大 api_config 对象中提取当前角色的配置
        role_config = api_config.get(role, {})

        full_content = ""
        for chunk in chat_with_role(role, role_prompt, stock_code, role_config, session_id):
            if "content" in chunk:
                full_content = chunk["content"]
            elif "tool_call" in chunk:
                yield {"role": role, "status": "calling_tool", "tool": chunk["tool_call"]}
            elif "error" in chunk:
                yield {"role": role, "status": "error", "content": chunk["error"]}
                break

        if full_content:
            yield {"role": role, "status": "done", "content": full_content}


def get_chat_history(stock_code, session_id=None, limit=50):
    col = get_collection("chat_history")
    if col is None:
        return []
    query = {"stock_code": stock_code}
    if session_id:
        query["session_id"] = session_id
    return list(col.find(query, {"_id": 0}).sort("created_at", -1).limit(limit))


def get_model_configs():
    """获取角色元数据（不含密钥，密钥在前端 localStorage）"""
    configs = {}
    for role, cfg in AI_MODELS.items():
        configs[role] = {
            "name": cfg["name"],
            "icon": cfg["icon"],
            "color": cfg["color"],
        }
    return configs


# ============================================================
# 内部函数
# ============================================================

def _build_background_context(stock_code):
    """为纯聊天模型自动在后台抓取当前股票的各项数据指标，拼凑为纯文本上下文"""
    try:
        from services.analysis import get_technical_summary
        from services.valuation import get_valuation_summary
        from services.news import get_news_for_ai
        
        kline = _get_kline_summary(stock_code, 30)
        tech = get_technical_summary(stock_code)
        val = get_valuation_summary(stock_code)
        news = get_news_for_ai(stock_code, limit=3)
        
        ctx = "【系统自动为您检索到的这只股票当前最新数据参考】\n"
        ctx += f"- 近期走势: {kline.get('summary', '无')}\n"
        if "macd" in tech:
            ctx += f"- 技术面: MACD({tech.get('macd', '无')}), KDJ({tech.get('kdj', '无')}), 均线({tech.get('ma_status', '无')})\n"
        if "description" in val:
            ctx += f"- 估值面: {val['description']}\n"
        elif "pe" in val:
            ctx += f"- 估值面: 当前PE {val['pe']}, 历史分位 {val.get('pe_percentile', '未知')}%\n"
        
        if news and isinstance(news, list) and len(news) > 0:
            titles = [n.get("title", str(n)) for n in news]
            ctx += f"- 最新动态: {' | '.join(titles)}\n"
            
        return ctx
    except Exception as e:
        print(f"[AI Chat Context Error] {e}")
        return "【系统提示：当前这只股票后台数据获取失败，可以直接依常识或默认回复】"

def _build_messages(role, user_message, stock_code, session_id):
    role_meta = AI_MODELS[role]
    messages = [
        {"role": "system", "content": role_meta["system_prompt"]},
    ]
    if session_id:
        history = get_chat_history(stock_code, session_id, limit=10)
        for h in reversed(history):
            messages.append({"role": "user", "content": h.get("user_message", "")})
            messages.append({"role": "assistant", "content": h.get("ai_response", "")})

    user_msg = user_message
    if stock_code:
        bg_info = _build_background_context(stock_code)
        user_msg = f"[当前分析股票代码: {stock_code}]\n\n{bg_info}\n\n[用户的提问]:\n{user_message}"
        
    messages.append({"role": "user", "content": user_msg})
    return messages


def _call_llm(llm_config, messages, tools=None):
    """调用 LLM — 标准 OpenAI Chat Completions 格式"""
    try:
        url = f"{llm_config['base_url'].rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {llm_config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": llm_config["model"],
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        print(f"[ai_chat] POST {url} model={llm_config['model']}")
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[ai_chat] LLM调用失败: {e}")
        return None


def _save_chat(stock_code, session_id, role, user_message, ai_response):
    col = get_collection("chat_history")
    if col is None:
        return
    col.insert_one({
        "stock_code": stock_code,
        "session_id": session_id or "default",
        "role": role,
        "user_message": user_message,
        "ai_response": ai_response,
        "created_at": datetime.now(),
    })


def _get_kline_summary(stock_code, days=30):
    from services.stock_data import fetch_kline
    kline = fetch_kline(stock_code)
    if not kline:
        return {"summary": "无K线数据"}

    recent = kline[-days:] if len(kline) >= days else kline
    if not recent:
        return {"summary": "数据不足"}

    closes = [k["close"] for k in recent]
    start_price = closes[0]
    end_price = closes[-1]
    max_price = max(closes)
    min_price = min(closes)
    change_pct = (end_price - start_price) / start_price * 100

    volumes = [k["volume"] for k in recent]
    avg_vol = sum(volumes) / len(volumes)
    recent_vol = sum(volumes[-5:]) / min(5, len(volumes[-5:]))
    vol_change = "放量" if recent_vol > avg_vol * 1.2 else ("缩量" if recent_vol < avg_vol * 0.8 else "平量")

    return {
        "stock_code": stock_code,
        "period": f"近{len(recent)}个交易日",
        "start_price": round(start_price, 2),
        "end_price": round(end_price, 2),
        "max_price": round(max_price, 2),
        "min_price": round(min_price, 2),
        "change_pct": round(change_pct, 2),
        "amplitude": round((max_price - min_price) / min_price * 100, 2),
        "volume_status": vol_change,
        "trend": "上涨" if change_pct > 3 else ("下跌" if change_pct < -3 else "震荡"),
        "summary": (
            f"近{len(recent)}日{'上涨' if change_pct > 0 else '下跌'}{abs(change_pct):.1f}%，"
            f"最高{max_price:.2f}，最低{min_price:.2f}，{vol_change}。"
        ),
    }
