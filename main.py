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
    return "NOREST IG Bot is Live!", 200

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
    print("Received Webhook:", data)
    
    if data.get("object") == "instagram":
        for entry in data.get("entry", []):
            # 1. 處理私訊事件 (Messaging)
            for messaging in entry.get("messaging", []):
                sender_id = messaging.get("sender", {}).get("id")
                message_text = messaging.get("message", {}).get("text", "")
                if sender_id and message_text:
                    handle_dm_logic(sender_id, message_text)
                    
            # 2. 處理貼文留言事件 (Comments)
            for change in entry.get("changes", []):
                value = change.get("value", {})
                comment_id = value.get("id")
                comment_text = value.get("text", "")
                
                if comment_id and comment_text and "散步" in comment_text:
                    reply_to_comment(comment_id)
                    
    return "EVENT_RECEIVED", 200

# 回覆留言私訊 (Private Reply)
def reply_to_comment(comment_id):
    url = f"https://graph.facebook.com/v20.0/{comment_id}/messages?access_token={PAGE_ACCESS_TOKEN}"
    text = (
        "🐶 哈囉！很高興收到您的留言～\n\n"
        "關於 NOREST「從心出發的散步練習」（10/3）的活動詳情與指南，"
        "請點擊下方連結查看最新資訊喔！👇\n\n"
        f"{WALK_LINK}\n\n"
        "如果有任何問題，隨時留言給我們，NOREST 客服會即時為您服務！🐾"
    )
    payload = {"recipient": {"comment_id": comment_id}, "message": {"text": text}}
    res = requests.post(url, json=payload)
    print("Private Reply Response:", res.json())

# 一般私訊處理
def handle_dm_logic(sender_id, text):
    if "散步" in text:
        reply = (
            "🐶 歡迎了解 NOREST「從心出發的散步練習」（10/3）！\n"
            f"請點擊下方連結查看活動指南與詳情：\n{WALK_LINK}"
        )
    else:
        reply = call_claude_api(text)
    send_instagram_dm(sender_id, reply)

def call_claude_api(user_message):
    if not CLAUDE_API_KEY:
        return "感謝您的訊息！NOREST 客服團隊會儘快回覆您。"
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    prompt = (
        f"你現在是 NOREST 品牌的線上客服 AI 助手。品牌活動資訊：NOREST「從心出發的散步練習」，活動日期為 10/3。"
        f"請親切、簡短且專業地回答使用者的問題：{user_message}"
    )
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
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, json=payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
