import os
import csv
import json
import urllib.request
import urllib.error
import sqlite3
from pathlib import Path
from typing import Any

import gradio as gr
from dotenv import load_dotenv



BASE_DIR = Path(__file__).resolve().parent

# 先載入 .env，再讀取環境變數
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "unocha.db"
SHOP_INFO_CSV = BASE_DIR / "shop_info.csv"
MENU_CSV = BASE_DIR / "menu.csv"

LLM_API_URL = os.getenv(
    "LLM_API_URL",
    "https://www.iai.nkust.edu.tw/aihub/v1/"
).rstrip("/")

MODEL_NAME = os.getenv("MODEL_NAME", "Furen-large").strip()
MAX_MODEL_STEPS = 5


SYSTEM_PROMPT = """
You are the customer-service agent for a student-built UNOCHA (烏弄) drink-shop demo.
IMPORTANT: This is an educational prototype, not an official UNOCHA customer-service channel.
Grounding: Use tool results for all specific store, menu, availability, and price claims.
If data is missing, say it is not available in this demo database and offer human handover.
Never invent a store address, opening hours, delivery policy, payment method, stock status, discount, or price.
Scope: Answer only questions about UNOCHA drinks, menu, ordering calculations, and store service.
Politely refuse unrelated requests and redirect to the shop.
Routing:
- Store policies / hours / address / payment / delivery -> get_shop_info.
- Menu, price, size, category, availability -> search_drinks.
- Order total -> calculate_order_total; never calculate the bill mentally.
- Complaint, special case, or missing information -> transfer_to_human.
Language: Reply in the customer's language, usually Traditional Chinese. Be concise (three sentences or less).
Pricing: The menu data contains regional reference prices, not guaranteed live prices for any specific branch.
Always disclose that actual prices and availability must be confirmed with the selected store when relevant.
Do not claim that a human has actually been contacted; handover is a demo record only.
【工具使用的強制規則】
1. 只要使用者詢問品牌資訊、門市資訊、營業時間、飲料品項、分類、價格或供應狀態，都必須先呼叫對應的工具查詢資料，不可直接根據常識或本提示詞回答。
2. 品牌與門市相關問題使用 get_shop_info。
3. 飲料品項、分類、價格與供應狀態使用 search_drinks。
3a. 呼叫 search_drinks 時，必須依照使用者意圖設定 intent：
- 詢問原茶或原茶價格時，使用 intent="base_tea"。
- 詢問某種茶有哪些調飲、以某種茶為基底的調飲時，使用 intent="mixed_drinks"。
- 明確要求列出該茶種的所有相關品項時，使用 intent="all"。
- 意圖不明確時，使用 intent="auto"。
- 不得只因 keyword 是茶種名稱，就忽略使用者要求搜尋調飲的意圖。
4. 計算訂單金額使用 calculate_order_total。
5. 投訴、異物、食品安全問題或使用者要求真人協助時，使用 transfer_to_human。
6. 取得工具結果後，才能根據工具回傳的資料回答使用者。
7. 不得自行編造資料庫沒有提供的品牌、門市、營業時間或價格。"""

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def build_database():
    """Build SQLite tables from the submitted CSV files on every app start."""
    if not SHOP_INFO_CSV.exists() or not MENU_CSV.exists():
        raise FileNotFoundError("shop_info.csv and menu.csv must be next to app.py.")
    with connect_db() as conn:
        conn.execute("DROP TABLE IF EXISTS shop_info")
        conn.execute("DROP TABLE IF EXISTS menu")
        conn.execute("""
            CREATE TABLE shop_info (
                topic TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source_status TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE menu (
                drink_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                size TEXT NOT NULL,
                price_ntd INTEGER NOT NULL,
                available INTEGER NOT NULL,
                notes TEXT NOT NULL,
                price_status TEXT NOT NULL,
                source_url TEXT NOT NULL
            )
        """)
        with open(SHOP_INFO_CSV, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        conn.executemany(
            "INSERT INTO shop_info(topic, content, source_status) VALUES(?,?,?)",
            [(r["topic"], r["content"], r["source_status"]) for r in rows]
        )
        with open(MENU_CSV, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        conn.executemany(
            """INSERT INTO menu(drink_id,name,category,size,price_ntd,available,notes,price_status,source_url)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            [(r["drink_id"], r["name"], r["category"], r["size"], int(r["price_ntd"]),
              int(r["available"]), r["notes"], r["price_status"], r["source_url"]) for r in rows]
        )

def get_shop_info(topic: str) -> dict[str, Any]:
    """Look up one shop information topic, such as opening_hours, address, payment_methods, delivery_and_pickup, or menu_source."""
    topic = (topic or "").strip().lower()
    with connect_db() as conn:
        row = conn.execute("SELECT topic, content, source_status FROM shop_info WHERE topic = ?", (topic,)).fetchone()
    if not row:
        return {"found": False, "message": "No matching information topic was found. Do not guess; offer human handover."}
    return {"found": True, "topic": row["topic"], "content": row["content"], "source_status": row["source_status"]}






def search_drinks(
    keyword: str = "",
    category: str = "",
    available_only: bool = True,
    intent: str = "auto",
) -> dict[str, Any]:
    """Search menu items by tea name and customer intent."""
    import unicodedata

    def normalize(text: str) -> str:
        text = unicodedata.normalize("NFKC", text or "").casefold()
        return "".join(ch for ch in text if ch.isalnum())

    keyword = (keyword or "").strip()
    category = (category or "").strip()
    query = normalize(keyword)
    normalized_category = normalize(category)

    valid_intents = {"auto", "base_tea", "mixed_drinks", "all"}
    if intent not in valid_intents:
        intent = "auto"

    aliases = {
        "名間鄉冬片": "名間鄉冬片仔",
        "冬片仔": "名間鄉冬片仔",
        "台茶18號紅玉": "台茶十八號紅玉",
        "台茶十八號紅茶": "台茶十八號紅玉",
        "紅玉": "台茶十八號紅玉",
        "碧螺春綠茶": "碧螺春綠",
        "碧螺春綠": "碧螺春綠",
        "碧螺春": "碧螺春綠",
        "蕎麥茶": "不苦蕎麥茶",
    }

    normalized_aliases = {
        normalize(alias): normalize(name)
        for alias, name in aliases.items()
    }
    canonical_query = normalized_aliases.get(query, query)

    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT drink_id, name, category, size, price_ntd,
                   available, notes, price_status
            FROM menu
            ORDER BY drink_id
            """
        ).fetchall()

    drinks = [dict(row) for row in rows]

    if available_only:
        drinks = [d for d in drinks if d["available"] == 1]

    if category:
        drinks = [
            d for d in drinks
            if normalized_category in normalize(d["category"])
        ]

    base_category = "台灣原茶"
    mixed_category = "原茶調飲"

    if intent == "base_tea":
        drinks = [
            d for d in drinks if d["category"] == base_category
        ]
    elif intent == "mixed_drinks":
        drinks = [
            d for d in drinks if d["category"] != base_category
        ]

    if not query:
        matches = drinks

    else:
        # Search official product names first.
        exact_matches = [
            d for d in drinks
            if normalize(d["name"]) in {query, canonical_query}
        ]

        # In auto mode, an exact official product name wins.
        if exact_matches and intent == "auto":
            matches = exact_matches

        else:
            # Match the customer's original wording against product names.
            # This allows a base-tea keyword to find related mixed drinks.
            name_matches = [
                d for d in drinks
                if query in normalize(d["name"])
                or (
                    canonical_query != query
                    and canonical_query in normalize(d["name"])
                )
            ]

            if name_matches:
                matches = name_matches

            else:
                # For broad tea queries, prefer original tea matches.
                # Do not let notes alone override product-name matches.
                notes_matches = [
                    d for d in drinks
                    if query in normalize(d["notes"] or "")
                    or (
                        canonical_query != query
                        and canonical_query in normalize(d["notes"] or "")
                    )
                ]

                if intent == "auto":
                    base_matches = [
                        d for d in notes_matches
                        if d["category"] == base_category
                    ]
                    matches = base_matches or notes_matches
                else:
                    matches = notes_matches

    # Remove duplicate database records.
    unique_matches = []
    seen_ids = set()

    for drink in matches:
        if drink["drink_id"] not in seen_ids:
            unique_matches.append(drink)
            seen_ids.add(drink["drink_id"])

    if not unique_matches:
        return {
            "found": False,
            "count": 0,
            "drinks": [],
            "multiple_matches": False,
            "message": (
                "找不到符合的品項。請勿猜測商品或價格；"
                "可以詢問客人是否要查看相近品項。"
            ),
        }

    return {
        "found": True,
        "count": len(unique_matches),
        "drinks": unique_matches[:30],
        "multiple_matches": len(unique_matches) > 1,
        "message": (
            "找到多個候選品項。請列出品名並詢問客人選擇，"
            "不要自行決定商品。"
            if len(unique_matches) > 1
            else "找到符合的品項。請以資料庫價格與供應狀態為準。"
        ),
    }




def calculate_order_total(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate the order total from menu database prices. Each item must contain name, size (M or L), and quantity."""
    if not isinstance(items, list) or not items:
        return {"ok": False, "message": "Provide a non-empty list of items with name, size, and quantity."}
    line_items = []
    total = 0
    with connect_db() as conn:
        for item in items:
            name = str(item.get("name", "")).strip()
            size = str(item.get("size", "")).strip().upper()
            try:
                quantity = int(item.get("quantity", 0))
            except (TypeError, ValueError):
                return {"ok": False, "message": f"Invalid quantity for {name or 'an item'}."}
            if not name or size not in {"M", "L"} or quantity < 1 or quantity > 99:
                return {"ok": False, "message": "Each item needs a valid name, size M/L, and quantity from 1 to 99."}
            row = conn.execute(
                "SELECT name,size,price_ntd,available,price_status FROM menu WHERE name = ? AND size = ?",
                (name, size)
            ).fetchone()
            if not row:
                return {"ok": False, "message": f"{name} ({size}) is not found in the menu database. No total was calculated."}
            if not row["available"]:
                return {"ok": False, "message": f"{name} ({size}) is marked unavailable. No total was calculated."}
            subtotal = int(row["price_ntd"]) * quantity
            total += subtotal
            line_items.append({
                "name": row["name"], "size": row["size"], "quantity": quantity,
                "unit_price_ntd": int(row["price_ntd"]), "subtotal_ntd": subtotal,
                "price_status": row["price_status"]
            })
    return {
        "ok": True, "currency": "TWD", "line_items": line_items,
        "total_ntd": total,
        "disclaimer": "Calculated from regional reference prices in the demo database; confirm the actual price with the selected store."
    }

def transfer_to_human(reason: str) -> dict[str, Any]:
    """Create a demo handover record for a complaint, special request, or question that the database cannot answer."""
    reason = (reason or "").strip()[:500]
    if not reason:
        reason = "Customer requested human assistance."
    # This is only a demonstration; it does not send a real message to a store.
    return {
        "handover_created": True,
        "reason": reason,
        "message": "Demo handover recorded. No real store employee has been contacted; please contact the selected branch directly."
    }

TOOL_DECLARATIONS = [
    {
        "name": "get_shop_info",
        "description": "Look up a store information topic. Use this for hours, address, payment, delivery, pickup, store policies, or menu source. Never guess if not found.",
        "parameters": {"type": "object", "properties": {"topic": {"type": "string", "description": "The exact topic key, e.g. opening_hours, address, payment_methods, delivery_and_pickup, menu_source"}}, "required": ["topic"]}
    },
        
    {
        "name": "search_drinks",
        "description": (
            "Search drink menu records by name keyword, category, and intent. "
            "Use intent='base_tea' for original tea, "
            "intent='mixed_drinks' when the customer asks for mixed drinks "
            "made with a tea, intent='all' for all matching products, "
            "and intent='auto' when the intent is unclear."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "Drink name or tea-base keyword. "
                        "Use the tea name even when searching related mixed drinks."
                    )
                },
                "category": {
                    "type": "string",
                    "description": (
                        "Optional category such as 台灣原茶, 水果調飲, 香醇鮮乳."
                    )
                },
                "available_only": {
                    "type": "boolean",
                    "description": "Whether to return only records marked available."
                },
                "intent": {
                    "type": "string",
                    "enum": ["auto", "base_tea", "mixed_drinks", "all"],
                    "description": (
                        "Search intent: auto, base_tea, mixed_drinks, or all."
                    )
                }
            },
            "required": ["keyword", "category", "available_only"]
        }
    },
    {
        "name": "calculate_order_total",
        "description": "Calculate an order total from the menu database. Always use this tool for arithmetic. Each item needs exact database name, size M/L, and quantity.",
        "parameters": {"type": "object", "properties": {
            "items": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "size": {"type": "string", "enum": ["M", "L"]},
                "quantity": {"type": "integer"}
            }, "required": ["name", "size", "quantity"]}}
        }, "required": ["items"]}
    },
    {
        "name": "transfer_to_human",
        "description": "Record a demo handover when the customer complains, asks for a person, or asks something the database cannot answer. Do not claim a real employee was contacted.",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string", "description": "Short reason for the handover"}}, "required": ["reason"]}
    }
]
TOOL_MAP = {
    "get_shop_info": get_shop_info,
    "search_drinks": search_drinks,
    "calculate_order_total": calculate_order_total,
    "transfer_to_human": transfer_to_human,
}


def _to_iai_tools():
    """將原有工具宣告轉成 OpenAI 相容的 iAI Tool Calling 格式。"""
    def normalize_schema(value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key == "type" and isinstance(item, str):
                    result[key] = item.lower()
                else:
                    result[key] = normalize_schema(item)
            return result
        if isinstance(value, list):
            return [normalize_schema(item) for item in value]
        return value

    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": normalize_schema(tool["parameters"]),
            },
        }
        for tool in TOOL_DECLARATIONS
    ]


def _to_iai_history(history, message):
    """整理 Gradio 對話紀錄，轉成 iAI 所需的 messages 格式。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for item in (history or [])[-10:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content", "")

        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue

        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})
    return messages


def _iai_chat(messages, tools=None):
    """向學校 iAI Chat Completions API 發送請求。"""
    api_key = os.getenv("API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "讀取不到 API_KEY，請確認專案根目錄的 .env 設定。"
        )

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
    }

    if tools is not None:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    request = urllib.request.Request(
        LLM_API_URL + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8"))

    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError("iAI 回應中沒有 choices。")

    return choices[0].get("message", {})


def run_agent(message, history):
    """執行 iAI Agent 工具呼叫循環，最多呼叫模型 MAX_MODEL_STEPS 次。"""
    trace = []

    try:
        messages = _to_iai_history(history, message)
        tools = _to_iai_tools()

        for step in range(1, MAX_MODEL_STEPS + 1):
            model_message = _iai_chat(messages, tools=tools)
            tool_calls = model_message.get("tool_calls", [])

            if not tool_calls:
                answer = (model_message.get("content") or "").strip()
                if not answer:
                    answer = "目前沒有可用的文字回覆，請聯繫門市確認。"
                return answer, "\n\n".join(trace) or "本次未呼叫工具。"

            # 保留模型原始工具呼叫訊息，讓下一輪能正確銜接
            messages.append(model_message)

            for call in tool_calls:
                call_id = call.get("id", "")
                function = call.get("function", {})
                name = function.get("name", "")
                raw_args = function.get("arguments", "{}")

                try:
                    args = (
                        json.loads(raw_args)
                        if isinstance(raw_args, str)
                        else raw_args
                    )
                    if not isinstance(args, dict):
                        raise ValueError("工具參數必須是 JSON 物件")
                except (json.JSONDecodeError, ValueError, TypeError):
                    args = {}
                    result = {"error": "Invalid tool arguments."}
                else:
                    if name not in TOOL_MAP:
                        result = {
                            "error": "Unknown tool refused. Only the four defined tools are allowed."
                        }
                    else:
                        try:
                            result = TOOL_MAP[name](**args)
                        except Exception as exc:
                            result = {
                                "error": (
                                    "Tool execution failed safely: "
                                    f"{type(exc).__name__}"
                                )
                            }

                trace.append(
                    f"**Step {step} — `{name or 'unknown'}`**\n\n"
                    f"- Arguments: `{json.dumps(args, ensure_ascii=False)}`\n"
                    f"- Result: `{json.dumps(result, ensure_ascii=False)}`"
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return (
            "我目前無法完成這個問題，為避免提供錯誤資訊，"
            "請聯繫實際門市確認。",
            "\n\n".join(trace) + "\n\n已達模型呼叫上限，已停止。",
        )

    except urllib.error.HTTPError as exc:
        # 不顯示 API 金鑰，只顯示伺服器回傳的錯誤內容
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = "無法讀取錯誤內容。"

        return (
            f"iAI API 請求失敗（HTTP {exc.code}）。請檢查模型設定或稍後再試。",
            detail,
        )

    except urllib.error.URLError:
        return (
            "目前無法連線至 iAI，請確認網路連線後再試。",
            "iAI 連線失敗。",
        )

    except Exception as exc:
        return (
            "客服系統暫時發生錯誤，請稍後再試。",
            f"錯誤類型：{type(exc).__name__}",
        )


def respond(message, history):
    if not message or not message.strip():
        return history, "", "請先輸入問題。"
    history = list(history or [])
    answer, trace = run_agent(message.strip(), history)
    history = history + [
        {"role": "user", "content": message.strip()},
        {"role": "assistant", "content": answer},
    ]
    return history, "", trace

build_database()



build_database()

with gr.Blocks(title="烏弄 UNOCHA AI 客服 Agent") as demo:
    gr.Markdown(
        "# 烏弄 UNOCHA AI 客服 Agent\n"
        "課堂作業示範版｜非烏弄官方客服。"
        "菜單價格為區域參考資料，實際售價與供應請以門市為準。"
    )

    greeting = (
    "您好，我是烏弄的客服機器人，很高興為您服務，"
    "請問有什麼可以協助您？"
    )

    initial_history = [
        {"role": "assistant", "content": greeting}
    ]

    history_state = gr.State(initial_history)

    with gr.Row(equal_height=False):
        # 客服對話
        with gr.Column(scale=3, min_width=450):
            chatbot = gr.Chatbot(
                value=initial_history,
                label="客服對話",
                height=430,
            )

        # 輸入問題、範例、工具紀錄
        with gr.Column(scale=2, min_width=350):
            with gr.Row():
                message_box = gr.Textbox(
                    label="輸入問題",
                    placeholder="例如：玉霞紅茶拿鐵大杯多少錢？",
                    scale=5,
                    lines=2,
                )
                send_btn = gr.Button(
                    "送出",
                    variant="primary",
                    scale=1,
                    min_width=80,
                )

            gr.Markdown("### 常用測試問題")
            gr.Examples(
                examples=[
                    ["名間鄉冬片仔多少錢？"],
                    ["我要兩杯大杯玉霞紅茶拿鐵，總共多少錢？"],
                    ["請問你們高雄某門市今天幾點打烊？"],
                    ["我想投訴飲料有異物。"],
                    ["幫我解釋微積分。"],
                ],
                inputs=message_box,
            )

            trace_box = gr.Markdown(
                "### Tools used\n本次尚未呼叫工具。"
            )

    send_btn.click(
        respond,
        inputs=[message_box, history_state],
        outputs=[history_state, message_box, trace_box],
    ).then(
        lambda h: h,
        inputs=history_state,
        outputs=chatbot,
    )

    message_box.submit(
        respond,
        inputs=[message_box, history_state],
        outputs=[history_state, message_box, trace_box],
    ).then(
        lambda h: h,
        inputs=history_state,
        outputs=chatbot,
    )



if __name__ == "__main__":
    demo.launch()
