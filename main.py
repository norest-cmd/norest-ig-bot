import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "norest_secret_token_123")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")

@app.route("/", methods=["GET"])
def home():
    return "NOREST IG Bot is running!", 200

@app.route("/webhook", methods=["GET"])
def verify_webhook():
   # 1. 供 Meta 驗證 Webhook 的 GET 介面
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")
        return str(challenge), 200, {'Content-Type': 'text/plain'}
    return "Forbidden", 403
@app.route("/webhook", methods=["POST"])
def webhook_event():
    data = request.get_json()
    print("Received Webhook Event:", data)
    return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
