from typing import TypedDict, Optional

class ConversationState(TypedDict, total=False):
    user_id: str
    last_user_message: str
    intent: Optional[str]
    stage: Optional[str]
    doctor: Optional[str]
    date: Optional[str]
    time: Optional[str]
    bot_response: Optional[str]
    appointment_id: Optional[str]
    requested_info: Optional[str]
    patient_mobile: Optional[str]
    message_history: Optional[str]
    duration: Optional[str]
