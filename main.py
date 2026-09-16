import os
import sys
import hmac
import hashlib
import threading
from collections import OrderedDict

import requests
from flask import Flask, request

sys.stdout.reconfigure(line_buffering=True)
app = Flask(__name__)

# ===== 環境變數 =====
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
# 名稱沿用舊的，實際存放「Instagram User Token」（新路線，graph.instagram.com）
IG_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
# 選填：填入 Meta 後台的「Instagram 應用程式密鑰」後會啟用簽章驗證
APP_SECRET = os.getenv("IG_APP_SECRET", "")

GRAPH = "https://graph.instagram.com/v21.0"
KEYWORD = "散步"

# 活動連結（純網址，不可用 Markdown 格式）
WALK_LINK = (
    "https://lustrous-baklava-e6e6f4.netlify.app/"
    "?utm_source=ig&utm_medium=social&utm_campaign=walk_1003&utm_content=comment_dm"
)

# ===== 去重（避免 Meta 重送造成重複私訊）=====
_seen = OrderedDict()
_seen_lock = threading.Lock()


def already_handled(key):
    with _seen_lock:
        if key in _seen:
            return True
        _seen[key] = True
        if len(_seen) > 2000:
            _seen.popitem(last=False)
        return False


# ===== 路由 =====
@app.route("/", methods=["GET"])
def home():
    return "NOREST IG Bot is Live!", 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    if (
        request.args.get("hub.mode") == "subscribe"
        and VERIFY_TOKEN
        and request.args.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return request.args.get("hub.challenge", ""), 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_event():
    raw = request.get_data()

    if APP_SECRET:
        sig = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            print("Signature mismatch, ignored")
            return "Forbidden", 403

    data = request.get_json(silent=True) or {}
    print("Received Webhook:", data)

    # 先回 200，實際處理丟到背景執行緒，避免 Meta 逾時重送
    threading.Thread(target=process_event, args=(data,), daemon=True).start()
    return "EVENT_RECEIVED", 200


# ===== 事件處理 =====
def process_event(data):
    try:
        if data.get("object") != "instagram":
            return
        for entry in data.get("entry", []):
            my_id = str(entry.get("id", ""))

            # 1. 留言
            for change in entry.get("changes", []):
                if change.get("field") != "comments":
                    continue
                value = change.get("value", {})
                comment_id = value.get("id")
                text = value.get("text", "") or ""
                from_id = str(value.get("from", {}).get("id", ""))
                if not comment_id or from_id == my_id:
                    continue  # 忽略自己的留言
                if KEYWORD in text and not already_handled("c:" + comment_id):
                    private_reply(comment_id)

            # 2. 私訊
            for m in entry.get("messaging", []):
                msg = m.get("message")
                if not msg or msg.get("is_echo"):
                    continue  # 已讀、反應、自己發出的訊息都略過
                sender_id = str(m.get("sender", {}).get("id", ""))
                text = msg.get("text", "") or ""
                mid = msg.get("mid", "")
                if not sender_id or sender_id == my_id or not text:
                    continue
                if mid and already_handled("m:" + mid):
                    continue
                handle_dm(sender_id, text)
    except Exception as e:
        print("Process Error:", repr(e))


def graph_post(path, payload):
    try:
        res = requests.post(
            f"{GRAPH}/{path}",
            json=payload,
            headers={"Authorization": f"Bearer {IG_TOKEN}"},
            timeout=10,
        )
        try:
            body = res.json()
        except ValueError:
            body = res.text
        return res.status_code, body
    except requests.RequestException as e:
        return None, repr(e)


COMMENT_REPLY_TEXT = (
    "嗨！收到你的留言囉\n"
    "帶 3-8 個月的幼犬出門散步，是不是常常覺得手比腳還酸，又擔心牠留下了不好的記憶呢？"
    "別擔心，社會化不是「什麼都見過」，而是要讓牠「覺得安全」。\n"
    "10/3 (六) 的幼犬散步練習課，我們會依月齡體型分隊，由專業訓練師帶你們從第一步就練對！\n\n"
    "課程完整流程與報名連結：\n"
    "https://lustrous-baklava-e6e6f4.netlify.app\n\n"
    "點擊連結可以看到：\n"
    "當天的完整流程與時間\n"
    "這堂課會練到的 4 件事\n"
    "不帶狗狗也能參加的講座票說明\n"
    "早鳥優惠與報名連結\n"
    "期待陪你跟狗狗一起快樂散步！"
)


def private_reply(comment_id):
    status, body = graph_post(
        "me/messages",
        {"recipient": {"comment_id": comment_id}, "message": {"text": COMMENT_REPLY_TEXT}},
    )
    print("Private Reply Response:", status, body)


def handle_dm(sender_id, text):
    if KEYWORD in text:
        reply = (
            "🐶 歡迎了解 NOREST「從心出發的散步練習」（10/3）！\n"
            f"請點擊下方連結查看活動指南與詳情：\n{WALK_LINK}"
        )
    else:
        reply = call_claude(text)
    status, body = graph_post(
        "me/messages",
        {"recipient": {"id": sender_id}, "message": {"text": reply}},
    )
    print("DM Response:", status, body)


def call_claude(user_message):
    fallback = "感謝您的訊息！NOREST 客服團隊會儘快回覆您。"
    if not CLAUDE_API_KEY:
        return fallback
    system = (
        "你是 NOREST 品牌的 Instagram 線上客服。品牌活動：「從心出發的散步練習」，日期 10/3。"
        f"活動詳情與報名請引導至：{WALK_LINK}。"
        "請用繁體中文，親切、簡短（150 字內）回覆；不確定的資訊不要編造，請對方留下問題由真人客服回覆。"
        "不要使用 Markdown 語法。"
    )
    try:
        res = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 400,
                "system": system,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=20,
        )
        if res.status_code == 200:
            parts = res.json().get("content", [])
            reply = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
            return reply[:950] or fallback
        print("Claude API Error:", res.status_code, res.text[:300])
    except Exception as e:
        print("Claude API Error:", repr(e))
    return fallback


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
