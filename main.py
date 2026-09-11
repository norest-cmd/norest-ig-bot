import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# 環境變數設定
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "norest_secret_token_123")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# 專屬連結
WALK_LINK = "https://lustrous-baklava-e6e6f4.netlify.app/?utm_source=ig&utm_medium=social&utm_content=link_in_bio&fbclid=PAcGRvZgJleHRuA2FlbQIxMQBzcnRjBmFwcF9pZA85MzY2MTk3NDMzOTI0NTkAAaf5b9U05XDq-FaxewP029fulWGHZxMOQw9leHbAce5I19LWwYj8vIWXgHB7UQ_aem_H1k8Wk9icXuJhvZo2_baVQ"

@app.route("/", methods=["GET"])
def home():
    return "NOREST IG Bot with Link Reply is Live!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook_event():
    data = request.get_json()
    
    if data.get("object") == "instagram":
        for entry in data.get("entry", []):
            # 1. 處理私訊事件 (Messaging)
            for messaging in entry.get("messaging", []):
                sender_id = messaging.get("sender", {}).get("id")
                message_text = messaging.get("message", {}).get("text", "")
                if sender_id and message_text:
                    handle_logic(sender_id, message_text)
                    
            # 2. 處理貼文留言事件 (Changes / Comments)
            for change in entry.get("changes", []):
                value = change.get("value", {})
                user_id = value.get("from", {}).get("id")
                comment_text = value.get("text", "")
                if user_id and comment_text:
                    handle_logic(user_id, comment_text)
                    
    return "EVENT_RECEIVED", 200

def handle_logic(user_id, text):
    # 觸發關鍵字：散步
    if "散步" in text:
        reply = (
            "🐶 哈囉！很高興收到您的留言～\n\n"
            "關於 NOREST × IF DOG CAN「從心出發的散步練習」的散步地圖與活動詳情，"
            "請點擊下方連結查看最新指南喔！👇\n\n"
            f"{WALK_LINK}\n\n"
            "如果有任何活動或商品問題，隨時留言給我們，NOREST 客服會即時為您服務！🐾"
        )
    # 觸發關鍵字：感官大冒險
    elif "感官大冒險" in text:
        reply = "🐶 歡迎參加 NOREST × IF DOG CAN「從心出發的散步練習」（10/3）！請點擊專屬連結體驗指南..."
    # 其他非關鍵字：交由 Claude API 回答
    else:
        reply = call_claude_api(text)
        
    send_instagram_dm(user_id, reply)

def call_claude_api(user_message):
    if not CLAUDE_API_KEY:
        return "感謝您的訊息！NOREST 客服團隊會儘快回覆您。"

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    prompt = f"""你現在是 NOREST 品牌的線上客服 AI 助手。活動資訊：NOREST × IF DOG CAN「夏日毛孩感官大冒險」，日期 8/1–8/2。
請親切、簡短地回答使用者的問題：{user_message}"""

    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        res = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()["content"][0]["text"]
    except Exception as e:
        print("Claude API Error:", e)
        
    return "感謝您的訊息！我們會盡快為您解答。"

def send_instagram_dm(recipient_id, text):
    url = f"https://graph.facebook.com/v20.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
