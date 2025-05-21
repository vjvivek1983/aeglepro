from booking_api import  get_bookings_from_api, parse_appointments, reschedule_appointment_by_id, book_appointment, cancel_appointment_by_id, create_availability_matrix, get_available_slots, get_doctor_ids_from_api,get_appointment_list, get_appointment_list_with_window
from nlp_agent import get_intent_from_emails
from langgraph_agent.schema import ConversationState
from langgraph_agent.redis_handler import delete_session
from datetime import datetime, timedelta


def process_graph_action(state: ConversationState, data, appointments) -> ConversationState:
    print("----------------In processing information---------")
    action = data.get("action", "").lower()
    print("Before:" + str(data))
    reply_email = data.get("reply_email")
    data = data.get("data","")
    print("After: "+ str(data))

    if action == "reschedule_appointment":
        state["intent"] = action
        state["patient_mobile"] = data.get("patient_mobile")
        state["appointment_id"] = get_appointment_list(appointments, *(data.get(k) for k in ["patient_mobile", "doctor_name", "appointment_date", "appointment_time"] if data.get(k) is not None))[0]["appointment_id"]
        state["date"] = data.get("new_date")
        state["time"] = data.get("new_time")
        state["doctor"] = data.get("doctor_id")
        state["bot_response"] = reply_email
        
        if not state["appointment_id"] and not state["date"] and not state["time"]:
            state["stage"] = 'INCOMPLETE_INFO'
        else:
            state["stage"] = "confirm_reschedule"
    
    elif action == "book_appointment" or action == "schedule_appointment":
        state["intent"] = action
        state["date"] = data.get("appointment_date")
        state["time"] = data.get("appointment_time")
        state["patient_mobile"] = data.get("patient_mobile")
        state["doctor"] = data.get("doctor_id")
        state["bot_response"] = reply_email
        
        if not state["patient_mobile"] and not state["doctor"] and not state["date"] and not state["time"]:
            state["stage"] = 'INCOMPLETE_INFO'
        else:
            state["stage"] = "confirm_booking"
    
    elif action == "cancel_appointment":
        state["intent"] = action
        state["patient_mobile"] = data.get("patient_mobile")
        state["appointment_id"] = get_appointment_list(appointments, *(data.get(k) for k in ["patient_mobile", "doctor_name", "appointment_date", "appointment_time"] if data.get(k) is not None))[0]["appointment_id"]
        state["bot_response"] = reply_email
        if not state["appointment_id"]:
            state["stage"] = 'INCOMPLETE_INFO'
        else:
            state["stage"] = "confirm_cancellation"
    
    elif action == "reschedule_all_for_doctor":
        state["intent"] = action
        state["appointment_id"] = get_appointment_list_with_window(appointments,12, *(data.get(k) for k in [ "doctor_name", "appointment_date", "appointment_time"] if data.get(k) is not None))
        state["duration"] = data.get("duration")
        state["bot_response"] = reply_email
        if not state["appointment_id"] or not state["duration"]:
            state["stage"] = 'error'
        else:
            state["stage"] = "confirm_reschedule_all_for_doctor"     

    elif action == "request_more_info" or action == "request_reschedule_info" or action == "confirm_cancel_choice_date_filtered" or action == "confirm_cancel_choice_all":
        additional_info = []
        additional_text=""
        state["intent"] = action
        if data != "":
            state["date"] = data.get("appointment_date")
            state["time"] = data.get("appointment_time")
            state["patient_mobile"] = data.get("patient_mobile")
            state["doctor"] = data.get("doctor_id")
        
        if data.get("intended_action") == "BOOK":
            if isinstance(data, dict):    
                additional_text = get_available_slots( *(data.get(k) for k in ["doctor_name", "appointment_date", "appointment_time"] if data.get(k) is not None))
                #additional_text = f"Availability for Dr. {additional_info['doctor']}:\n" + "\n".join( [f"{date}: {', '.join(times)}" for date, times in additional_info['availability'].items()])
            else:
                additional_text = get_available_slots()
        
        elif data.get("intended_action") == "CANCEL":
            if data.get("patient_mobile") is not None:
                if isinstance(data, dict):
                    additional_info = get_appointment_list(appointments, *(data.get(k) for k in ["patient_mobile", "doctor_name", "appointment_date", "appointment_time"] if data.get(k) is not None))
                    additional_text = "Your existing appointments are: \n"
                    additional_text += "\n".join([f"Dr. {a['doctor_name']} on {a['appointment_date']} at {a['appointment_time']}" for a in additional_info])
                
        elif data.get("intended_action") == "RESCHEDULE":
            if data.get("patient_mobile") is not None:
                if isinstance(data, dict):
                    if data.get("appointment_date") is None or data.get("appointment_time") is None:
                        additional_info = get_appointment_list(appointments, *(data.get(k) for k in ["patient_mobile", "doctor_name", "appointment_date", "appointment_time"] if data.get(k) is not None))
                        additional_text = "Your existing appointments are: \n"
                        additional_text = "\n".join([f"Dr. {a['doctor_name']} on {a['appointment_date']} at {a['appointment_time']}" for a in additional_info])
                    else:
                        additional_text = get_available_slots( *(data.get(k) for k in ["doctor_name", "new_date", "new_time"] if data.get(k) is not None))
                        #additional_text = f"Availability for Dr. {additional_info['doctor']}:\n" + "\n".join( [f"{date}: {', '.join(times)}" for date, times in additional_info['availability'].items()])
            

        
        state["bot_response"] = reply_email + "\n" + str(additional_text)
        state["stage"] = 'INCOMPLETE_INFO' 
        
    else:
        state["bot_response"] = "❓ Unknown action: "+ action
        state["stage"] = "done"
    
    return state    


def validate_and_extract_node(state: ConversationState) -> ConversationState:
    
    message = state["message_history"]
    print("------------ Message History provided to LLM --------------------")
    print(message)
    print("-----------------------------------------------------------------")
    
    
    requested = state.get("requested_info")
    
    

    appointments_json, status_code = get_bookings_from_api(7)
       
    if status_code != 200:
        state["stage"] = "error"
        state["bot_response"] = "Internal Server Error: Could not connect to booking system. Please call."
        
    else:
        appointments = parse_appointments(appointments_json)
        print("----------------Appointments-----------------")
        print(appointments)
        doctors_json = get_doctor_ids_from_api()
        info = get_intent_from_emails(message, appointments, state, doctors_json)
        state = process_graph_action(state, info, appointments)    
    
    return state

def confirm_reschedule_node(state):
    status, status_code = reschedule_appointment_by_id(state["appointment_id"], state["doctor"], state["date"], state["time"])
    if status_code != 200:
        state["bot_response"] = "Internal Server Error: Appointment not rescheduled. Please call."
        state["stage"] = "error"
    else:
        state["stage"] = "done"
        print("Deleting session info for the user: " + state["user_id"])
        delete_session(state["user_id"])
    return state

def confirm_booking_node(state):
    status, status_code = book_appointment(state["patient_mobile"], state["doctor"], state["date"], state["time"])
    if status_code != 200:
        state["stage"] = "error"
        state["bot_response"] = "Internal Server Error: Appointment not booked. Please call."
    else:
        state["stage"] = "done"
        print("Deleting session info for the user: " + state["user_id"])
        delete_session(state["user_id"])
    return state

def confirm_cancellation_node(state):
    status, status_code = cancel_appointment_by_id(state["appointment_id"])
    if status_code != 200:
        state["bot_response"] = "Internal Server Error: Appointment not cancelled. Please call."
        state["stage"] = "error"
    else:
        state["stage"] = "done"
        print("Deleting session info for the user: " + state["user_id"])
        delete_session(state["user_id"])
    return state

def confirm_reschedule_all_for_doctor_node(state):
    duration = state["duration"]
    appointments = state["appointment_id"]
    for appointment in appointments:
        print("Appointment info--->" + str(appointment))
        status, status_code = reschedule_appointment_by_id(appointment["appointment_id"], appointment['doctor_id'], appointment['appointment_date'],  (datetime.strptime(appointment['appointment_time'], "%H:%M") + timedelta(seconds=int(duration))).strftime("%H:%M"))
        if status_code != 200:
            state["stage"] = "error"
            return state
            
    state["stage"] = "done"
    print("Deleting session info for the user: " + state["user_id"])
    delete_session(state["user_id"])
    return state

def completion_node(state):
    print("Deleting session info for the user: " + state["user_id"])
    delete_session(state["user_id"])
    return state

def error_node(state):
    delete_session(state["user_id"])
    return state

def back_to_top_node(state):
    return state

