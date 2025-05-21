import requests
from flask import jsonify # type: ignore
#from nlp_agent import get_intent_from_emails
#from booking_api import process_action, get_bookings_from_api, parse_appointments
from langgraph_agent.redis_handler import get_session, set_session, append_message_history, get_message_history
from langgraph_agent.graph import build_graph

def handle_whatsapp_webhook(request):
    data = request.get_json()
    print(data)
    if data and data.get("entry"):
        for entry in data["entry"]:
            for change in entry["changes"]:
                value = change["value"]
                messages = value.get("messages")
                if messages:
                    for message in messages:
                        if message.get('type') == 'text' or message.get('type') == 'interactive':
                            phone_number = message["from"]
                            text = message["text"]["body"]
                        else:
                            return "No new user message"
                else:
                    return "No new user message"
    else:
        return "No new user message"
    
    graph = build_graph()
    append_message_history(phone_number, text)
    
    
       # Load session + history
    state = get_session(phone_number) or {"user_id": phone_number}
    history = get_message_history(phone_number)
    state["patient_mobile"] = phone_number[-10:]
    state["last_user_message"] = text
    state["message_history"] = history

    # Run LangGraph
    updated_state = graph.invoke(state)
    
    
    
    """appointments_json, status_code = get_bookings_from_api(7)
    
    if status_code != 200:
        response = "Internal Server Error: Could not connect to booking system. Please call."
        
    else:
        appointments = parse_appointments(appointments_json)
        info = get_intent_from_emails(message, appointments)
        print(info)
        response = process_action(info)"""
        
        
    send_whatsapp_message(phone_number, updated_state["bot_response"])
    set_session(phone_number, updated_state)
    # Send WhatsApp reply using WhatsApp Business API
    return jsonify({"status": "received", "response": updated_state["bot_response"]})

def send_whatsapp_message(to, message):
    url = f"https://graph.facebook.com/v17.0/614819328385049/messages"
    access_token = "EAAJGrjAgvhYBO0ZCjkg2iHFb1pIVaarYYoZA4og5p8x1kZCuK2pzilO9wSH4LZBtUgyTJyvGBIyl6A0Ui1ddZCuIg5PRX6v6IXOBPFONwaI63XIohx45ZCVCEMLJ6YAbzOZA7vhEyHgaOmH6kabaLa9IbfvUZCuZAuUGywZBNr5kdIe0IRJglC6KzUWD2GGyEpB2cxq8Y14eo6v7Bsf28b30LgBNJ8"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=data)
    print(response.text)
    return response.json()

    