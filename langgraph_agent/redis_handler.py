import redis # type: ignore
import json, time
from datetime import timedelta

# Connect to Redis (local by default)
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

SESSION_TIMEOUT = 600  # 1 hour in seconds

def get_session(user_id):
    """Retrieve the session data for a user."""
    session_data = r.get(user_id)
    if session_data:
        return json.loads(session_data)
    return None

def set_session(user_id, session_data):
    """Store session data for a user with a TTL."""
    r.setex(user_id, timedelta(seconds=SESSION_TIMEOUT), json.dumps(session_data))

def delete_session(user_id):
    """Delete the session data for a user."""
    r.delete(user_id)

def clean_up_sessions():
    """Clean up inactive sessions."""
    # Redis automatically deletes sessions after TTL expiration, but if needed:
    # You can manually remove sessions here if they go beyond TTL for more control.
    pass

def append_message_history(user_id, message):
    key = f"history:{user_id}"
    history = r.get(key)
    history_list = json.loads(history) if history else []
    history_list.append({"text": message, "timestamp": time.time()})
    r.set(key, json.dumps(history_list), ex=SESSION_TIMEOUT)

def get_message_history(user_id):
    key = f"history:{user_id}"
    history = r.get(key)
    return json.loads(history) if history else []

def clear_user_data(user_id):
    r.delete(f"session:{user_id}")
    r.delete(f"history:{user_id}")