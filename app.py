from flask import Flask, request, jsonify # type: ignore
from email_handler import check_email_and_respond
from whatsapp_handler import handle_whatsapp_webhook
import base64, json, os
from flask_cors import CORS # type: ignore

app = Flask(__name__)
CORS(app)
VERIFY_TOKEN = os.environ.get("WHATSAPP_HOOK_TOKEN")

@app.route('/')
def index():
    return "Email & WhatsApp Agent is running."

@app.route('/email/process', methods=['POST'])
def process_email():
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        return 'Bad Request: invalid Pub/Sub message format', 400

    message = envelope['message']
    data_str = message.get('data', '')
    if data_str:
        # Decode base64url-encoded string to bytes
        decoded_bytes = base64.urlsafe_b64decode(data_str + '==')  # pad if needed
        # Convert bytes to string
        decoded_str = decoded_bytes.decode('utf-8')
        # Parse JSON string to dict
        decoded_json = json.loads(decoded_str)
        history_id = decoded_json['historyId']
        print("History Id received in the subscription: " + str(history_id))
    
    try:
        with open('history_id.json') as f:
            last_known = json.load(f).get('historyId')
    except FileNotFoundError:
        print("No last known historyId found.")
        return False
    
    result = check_email_and_respond(last_known)
    return '', 204
    #return jsonify(result)

@app.route('/whatsapp/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    print(VERIFY_TOKEN)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

@app.route('/whatsapp/webhook', methods=['POST'])
def whatsapp_webhook():
    handle_whatsapp_webhook(request)
    return "OK", 200


if __name__ == '__main__':
    app.run(port=5000, debug=True)
