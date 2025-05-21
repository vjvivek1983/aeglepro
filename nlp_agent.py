
from transformers import pipeline
import json, requests, re

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
#GROQ_API_KEY = "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"
#GROQ_API_KEY = "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"
GROQ_API_KEY = "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"

# NLP pipeline
nlp = pipeline("ner", grouped_entities=True)

LLM_HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

def get_intent_from_emails(email_thread, existing_appointments_json, state, doctors_json=None):
    
    
    prompt = f"""You are an AI assistant for hospital appointment management via email.

You will receive:

1. A full email thread from a patient.
2. Some existing information about appointment like mobile number, appointment date & time, doctor id etc. Use this information if available else parse it from emails.
3. A list of all available doctors at the clinic with their ids.

Your job is to:
- Determine the patient's intent: BOOK, CANCEL, RESCHEDULE or RESCHEDULE_ALL_FOR_DOCTOR
- Output action should be mapped as follows: BOOK->book_appointment, CANCEL-> cancel_appointment, RESCHEDULE -> reschedule_appointment, RESCHEDULE_ALL_FOR_DOCTOR -> reschedule_all_for_doctor.
- If any of the required information is missing as per below, then action should be "request_more_info". Do not create any other action.
- Whenever complete information is not provided for an action then put the intent in data->INTENDED_ACTION field.
- Fuzzy match the doctor's name from the email and best match with the doctor list provided. Put only validated doctor_name and doctor_id in the output json.
- Extract required data from the whole thread. Start with the recent emails first. As soon as intent is confirmed, do not read the next emails.
- Follow the case-based decision flow below
- Return the appropriate structured response
- Assume all dates are in future. Do NOT assume a date in past unless explicitly mentioned in the email.

---

📅 BOOKING (Required: patient_mobile, appointment_date, appointment_time, doctor)

CASE STATEMENTS:

Case 1 — All 4 fields provided → Book the appointment. DO NOT CONFIRM. 
Case 2 — Partial info → Ask for missing fields.

---

❌ CANCELLATION (Required: patient_mobile, appointment_date, appointment_time)

CASE STATEMENTS:

Case 1 — All 3 fields provided → Cancel that appointment. DO NOT CONFIRM.  
Case 2 — Partial info -> Ask for missing fields.  

---

🔁 RESCHEDULING (Required: patient_mobile, appointment_date, appointment_time, new_date & new_time)

CASE STATEMENTS:

Case 1 — All fields provided → Reschedule the appointment. DO NOT CONFIRM.
Case 2 — Partial info → Ask for missing fields  


RESCHEDULING_ALL_FOR_DOCTOR (Required: doctor_name, appointment_date, appointment_time, duration)

CASE STATEMENTS:
Case 1 - All fields provided -> Reschedule all appointments of the provided doctor after given date and time by the given duration. Give all appointments data in output.
Case 2 - Any field missing -> Ask for missing fields.

---

🎯 INPUTS:

EMAIL THREAD:
{email_thread}

AVAILABLE DOCTOR'S LIST (JSON):
{doctors_json}

APPOINTMENT INFORMATION (JSON):
{json.dumps(state, indent=2, ensure_ascii=False)}
---

🎯 OUTPUT FORMAT — Choose the most appropriate:

✅ Book Appointment:
{{
  "action": "book_appointment",
  "data": {{
    "patient_mobile": "<mobile>",
    "appointment_date": "<yyyy-mm-dd>",
    "appointment_time": "<HH:MM>",
    "doctor_name": "<doctor_name>",
    "doctor_id": "<doctor_id>"
  }},
  "reply_email": "Dear <patient_name>, your appointment with Dr. <doctor_name> is confirmed for <appointment_date> at <appointment_time>. Please arrive 10 minutes early. Regards, Hospital Admin."
}}

❌ Cancel Appointment:
{{
  "action": "cancel_appointment",
  "data": {{
    "patient_mobile": "<mobile>",
    "appointment_date": "<yyyy-mm-dd>",
    "appointment_time": "<HH:MM>",
    "doctor_name": "<doctor_name>",
    "doctor_id": "<doctor_id>"
    }},
  "reply_email": "Dear <patient_name>, your appointment with Dr. <doctor_name> on <appointment_date> at <appointment_time> has been cancelled as requested. Regards, Hospital Admin."
}}

🔁 Reschedule Appointment:
{{
  "action": "reschedule_appointment",
  "data": {{
    "patient_mobile": "<mobile>",
    "appointment_date": "<yyyy-mm-dd>",
    "appointment_time": "<HH:MM>",
    "new_date": "<yyyy-mm-dd>",
    "new_time": "<HH:MM>",
    "doctor_name": "<doctor_name>",
    "doctor_id": "<doctor_id>"
  }},
  "reply_email": "Dear <patient_name>, your appointment on <appointment_date> at <appointment_time> has been successfully rescheduled to <new_date> at <new_time>. Regards, Hospital Admin."
}}

🔁 Reschedule all appointments for a doctor:
{{
  "action": "reschedule_all_for_doctor",
  "data": {{
  "doctor_id": "<doctor_id>",
  "doctor_name": "<doctor_name>",
  "appointment_date": "<yyyy-mm-dd>"
  "appointment_time": "<HH:MM>"
  "duration": "3600"
 
  }},
  "reply_email": "All appointments for <doctor> have been postponed by <duration>/3600 hour(s). All patients have been notified. Regards, Hospital Admin."
}}

🕵️ Ask for Missing Info:
{{
  "action": "request_more_info",
  "data": {{
    "intended_action: "BOOK"
    "patient_mobile": "<mobile>",
    "appointment_date": "<yyyy-mm-dd>",
    "appointment_time": "<HH:MM>",
    "doctor_name": "<doctor_name>",
    "doctor_id": "<doctor_id>"
  }},
  "missing_fields": ["appointment_time"],
  "reply_email": "Dear <patient_name>, to proceed with your request, we need a few more details."
}}
---

📌 RULES:

- Use only the provided email and doctor JSON.
- Do not invent or hallucinate any information.
- Follow all case statements and output formats strictly.
- Your response must be structured JSON with one of the output formats. Put ```json in the beginning of JSON block and ``` at the end."""
    payload = {
        "model": "llama-3.3-70b-versatile",  # Or another GROQ-supported model
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    response = requests.post(GROQ_API_URL, headers=LLM_HEADERS, json=payload)
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except:
        return response.text
    print(content)
    # Use regex to extract the JSON code block
    match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
    if match:
        embedded_json_str = match.group(1)
        def escape_newlines_in_strings(s):
            def replacer(match):
                return match.group(0).replace('\n', '\\n')
            return re.sub(r'\"(.*?)(?<!\\)\"', replacer, s, flags=re.DOTALL)

        safe_json_str = escape_newlines_in_strings(embedded_json_str)
        extracted_data = json.loads(safe_json_str)
        print(extracted_data)
    else:
        print("No JSON block found in message content.")
        
    response.raise_for_status()
    return extracted_data