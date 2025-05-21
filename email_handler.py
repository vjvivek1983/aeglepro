from langgraph_agent.redis_handler import get_session, set_session, append_message_history, get_message_history
from get_gmail_service import get_latest_thread_and_sender, send_email_reply
from langgraph_agent.graph import build_graph

def check_email_and_respond(history_id):
    full_thread_text, sender_email, subject = get_latest_thread_and_sender(history_id)
    if full_thread_text == "No New Messages":
        return {"sender": sender_email, "response": full_thread_text}
    
    graph = build_graph()
    
    # Save message history
    append_message_history(sender_email, full_thread_text)

    # Load session + history
    state = get_session(sender_email) or {"user_id": sender_email}
    history = get_message_history(sender_email)
    state["last_user_message"] = full_thread_text
    state["message_history"] = history

    # Run LangGraph
    updated_state = graph.invoke(state)
    
    send_email_reply(sender_email, subject, updated_state["bot_response"])
    set_session(sender_email, updated_state)
    return {"sender": sender_email, "response": updated_state["bot_response"]}
