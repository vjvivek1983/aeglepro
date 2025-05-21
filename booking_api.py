from datetime import datetime, timezone, timedelta
import requests, os, pytz, time
from typing import List, Dict, Optional

API_BASE = "https://api.aeglepro.com"  

from requests.structures import CaseInsensitiveDict

# Function to refresh credentials every hour.
def read_credentials():
    filename = 'cred.txt'

    def parse_file():
        with open(filename, 'r') as file:
            lines = file.readlines()
        return {line.split('=')[0].strip(): line.split('=')[1].strip() for line in lines if '=' in line}

    def update_access_token_in_file(creds, new_token):
        creds['access_token'] = new_token
        with open(filename, 'w') as file:
            for k, v in creds.items():
                file.write(f"{k}={v}\n")

    # Get file modification time
    file_mtime = os.path.getmtime(filename)
    file_mtime_dt = datetime.fromtimestamp(file_mtime)

    # Get start of current hour
    now = datetime.now()
    start_of_hour = now.replace(minute=0, second=0, microsecond=0)

    creds = parse_file()

    if file_mtime_dt >= start_of_hour:
        return creds['access_token']
    else:
        # Make POST call to refresh token
        url = "https://securetoken.googleapis.com/v1/token"
        params = {
            'key': creds['key']
        }
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': creds['refresh_token']
        }
        response = requests.post(url, params=params, data=payload)
        response.raise_for_status()
        access_token = response.json()['access_token']

        update_access_token_in_file(creds, access_token)
        return access_token
    


def get_headers():
    headers = CaseInsensitiveDict()
    headers["Org-Id"] = "1299"
    headers["timezone-offset"] = "330"
    headers["Authorization"] = "Bearer " + read_credentials()
    return headers



# Get all bookings by clinicId for next n day
def get_bookings_from_api(n=3):
    headers = get_headers()
    response = requests.get(f"{API_BASE}/appointments", params={"clinicId" : 1, "from": round(time.time() * 1000) , "to": round(time.time() * 1000) + n*24*3600*1000}, headers=headers)
    return response.json(), response.status_code

# Parse the appointments data into a neat JSON. This will be used by LLM agent.
def parse_appointments(json_data):
    ist = pytz.timezone("Asia/Kolkata")
    result = []
    
    for appt in json_data:
        # Convert milliseconds to datetime and adjust to IST
        if appt.get("status") != 'CNF':
            continue
        utc_time = datetime.fromtimestamp(appt["stTime"] / 1000.0, tz=timezone.utc)
        ist_date = utc_time.astimezone(ist).strftime("%Y-%m-%d")
        ist_time = utc_time.astimezone(ist).strftime("%H:%M")

        parsed = {
            "appointment_id": appt["id"],
            "doctor_id": appt.get("doctor", {}).get("id"),
            "doctor_name": appt.get("doctor", {}).get("name"),
            "patient_id": appt.get("patient", {}).get("id"),
            "patient_name": appt.get("patient", {}).get("name"),
            "patient_mobile": appt.get("patient", {}).get("phone"),
            "clinic_id": appt.get("clinic", {}).get("id"),
            "appointment_date": ist_date,
            "appointment_time": ist_time,
            "status": appt.get("status")
        }

        result.append(parsed)

    return result
# Get patient id using mobile number
def get_patient_id(mobile):
    headers = get_headers()
    r = requests.get(f"{API_BASE}/patients/", params={"name": mobile, "searchType": "Phone"},headers=headers)
    return r.json()['patients'][0]['id']


# Book appointment using patient's mobile, doctor name and datetime in UNIX epoch
def book_appointment(patient_mobile, doctor_id, current_date, current_time):
    headers = get_headers()
    patient_id = get_patient_id(patient_mobile)
    ist = pytz.timezone('Asia/Kolkata')
    stTime = int(ist.localize(datetime.strptime(f"{current_date} {current_time}", "%Y-%m-%d %H:%M")).timestamp() * 1000)    
    payload = {"doctorId": doctor_id,"patientId": patient_id,"type":"Out Patient","stTime":stTime,"endTime":stTime+3600000,"details":{"appt_cat_val1":[],"appt_cat_val2":[],"appt_cat_val3":[],"appt_cat_val4":[],"appt_cat_val5":[],"appt_cat_val6":[],"apptFee":200,"netFee":200,"disc":0,"tax":0,"doctorNotes":""},"notification":{"sms":"false","app":"true","email":"true","whatsapp":"true","none":"false"}}
    r =  requests.post(f"{API_BASE}/appointments", json=payload, headers=headers)
    return r.json(), r.status_code


#Cancel appointment by appointment id
def cancel_appointment_by_id(appt_id):
    headers = get_headers()
    payload = {"status":"PCANCEL"}
    r = requests.delete(f"{API_BASE}/appointments/{appt_id}",json=payload, headers=headers)
    return r.json(), r.status_code

# Get appointment by id
def get_appointment_by_id(appt_id):
    headers = get_headers()
    r = requests.get(f"{API_BASE}/appointments/{appt_id}", params={},headers=headers)
    return r.json()

#Reschedule appointment by appointment id, doctor id, new date, new time
def reschedule_appointment_by_id(appt_id, doctor_id, new_date, new_time):
    headers = get_headers()
    ist = pytz.timezone('Asia/Kolkata')
    stTime = int(ist.localize(datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M")).timestamp() * 1000)
    appointment = get_appointment_by_id(appt_id)
    if appointment.get("status") == "CNF":
        payload = {
            "doctorId": doctor_id,
            "patientId": str(appointment["patientId"]),
            "type": appointment["type"],
            "stTime": stTime,
            "endTime": stTime + 60*60*1000
        }
    r =  requests.put(f"{API_BASE}/reschedule-appointment/{appt_id}", json=payload, headers=headers)
    return r.json(), r.status_code

# Map numeric dayId to weekday name
day_map = {
    1: "Monday", 2: "Tuesday", 3: "Wednesday",
    4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"
}

def format_time(minutes):
    """Convert time like 930 to HH:MM"""
    hours = minutes // 100
    mins = minutes % 100
    return f"{hours:02}:{mins:02}"

def epoch_to_local_str(epoch_ms):
    if epoch_ms is None:
        return None
    dt = datetime.fromtimestamp(epoch_ms / 1000, pytz.timezone('Asia/Kolkata'))
    return dt.strftime('%H:%M')

def get_doctor_ids_from_api():
    headers = get_headers()
    response = requests.get(f"{API_BASE}/doctors/", params={"clinicId" : 1},headers=headers)
    doctors = response.json()
    return [(doc["id"], doc["name"]) for doc in doctors]

# Simulated API call (replace with actual HTTP request if needed)
def get_doctor_schedule_from_api(doctor_id):
    headers = get_headers()
    response = requests.get(f"{API_BASE}/doctors/{doctor_id}/schedule",  headers=headers)
    return response.json()

def build_doctor_schedule(doctor_info):
    schedules = {}
    for doc_id, doc_name in doctor_info:
        schedule_by_day = get_doctor_schedule_from_api(doc_id)  # Now returns a list of days with rows
        doc_schedule = {day: [] for day in day_map.values()}

        for day_entry in schedule_by_day:
            day_name = day_map.get(day_entry["dayId"])
            if not day_name:
                continue

            for row in day_entry.get("rows", []):
                start = format_time(row["stTime"])
                end = format_time(row["endTime"])
                doc_schedule[day_name].append((start, end))

        schedules[(doc_id, doc_name)] = doc_schedule
    return schedules

def create_availability_matrix():
    doctor_schedules = build_doctor_schedule(get_doctor_ids_from_api())
    bookings, status = get_bookings_from_api(7)
    matrix = {}
    for booking in bookings:
        doc_id = booking['doctorId']
        date = datetime.fromtimestamp(booking['stTime'] / 1000, pytz.timezone('Asia/Kolkata')).date()
        st_time = epoch_to_local_str(booking['stTime'])
        end_time = epoch_to_local_str(booking['endTime'])
        matrix.setdefault(doc_id, {}).setdefault(str(date), []).append((st_time, end_time))

    today = datetime.now(pytz.timezone('Asia/Kolkata')).date()
    next_3_days = [today + timedelta(days=i) for i in range(3)]

    doctor_availability = {}
    for (doc_id, doc_name), schedule in doctor_schedules.items():
        doctor_availability[doc_name] = {}

        for day in next_3_days:
            weekday = day.strftime('%A')
            slots = schedule.get(weekday, [])
            booked_slots = matrix.get(doc_id, {}).get(str(day), [])
            available = []

            for start, end in slots:
                slot_start = datetime.strptime(start, '%H:%M')
                slot_end = datetime.strptime(end, '%H:%M')

                current = slot_start
                slot_minutes = 60
                while current + timedelta(minutes=slot_minutes) <= slot_end:
                    slot_str = current.strftime('%H:%M')
                    slot_end_str = (current + timedelta(minutes=slot_minutes)).strftime('%H:%M')
                    if not any(bs <= slot_str < be for bs, be in booked_slots):
                        available.append(slot_str)
                    current += timedelta(minutes=slot_minutes)

            doctor_availability[doc_name][str(day)] = available
    return doctor_availability

def get_available_slots(doctor=None, date=None, time=None):
    
    result = {}
    data = create_availability_matrix()
    # Convert to set for quick lookup
    next_3_days = [(datetime.today() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]

        
    result = {
        "doctor": doctor,
        "date": date,
        "time": time,
        "available_doctors": [],
        "available_times": [],
        "available_dates": []
    }

    if not doctor and not date and not time:
        result["available_doctors"] = list(data.keys())
        return "Available doctors: " + ", ".join(result["available_doctors"])

    if doctor and not date and not time:
        if doctor in data:
            availability = {
                d: data[doctor][d]
                for d in next_3_days
                if d in data[doctor] and data[doctor][d]
            }
            if not availability:
                return f"No available slots for Dr. {doctor} in the next 3 days."
            readable = "\n".join([f"{d}: {', '.join(times)}" for d, times in availability.items()])
            return f"Available slots for Dr. {doctor} in the next 3 days:\n{readable}"
        else:
            return f"Doctor '{doctor}' not found."

    if date and not doctor and not time:
        availability = []
        for dname, schedule in data.items():
            times = schedule.get(date, [])
            if times:
                availability.append(f"- Dr. {dname}: {', '.join(times)}")
        if availability:
            return f"Doctor availability on {date}:\n" + "\n".join(availability)
        else:
            return f"No doctors available on {date}."

    if time and not doctor and not date:
        availability = []
        for dname, schedule in data.items():
            available_dates = []
            for d in next_3_days:
                if time in schedule.get(d, []):
                    available_dates.append(d)
            if available_dates:
                availability.append(f"- Dr. {dname}: {', '.join(available_dates)}")
        if availability:
            return f"Doctors available at {time}:\n" + "\n".join(availability)
        else:
            return f"No doctors available at {time} in the next 3 days."

    if date and time and not doctor:
        for dname, schedule in data.items():
            if time in schedule.get(date, []):
                result["available_doctors"].append(dname)
        return f"Doctors available on {date} at {time}: " + ", ".join(result["available_doctors"]) if result["available_doctors"] else f"No doctors available on {date} at {time}."

    if doctor and date and not time:
        if doctor in data:
            result["available_times"] = data[doctor].get(date, [])
        return f"Available time slots for Dr. {doctor} on {date}: " + ", ".join(result["available_times"]) if result["available_times"] else f"No available slots for Dr. {doctor} on {date}."

    if doctor and time and not date:
        if doctor in data:
            for d in next_3_days:
                if time in data[doctor].get(d, []):
                    result["available_dates"].append(d)
        return f"Dr. {doctor} is available at {time} on: " + ", ".join(result["available_dates"]) if result["available_dates"] else f"Dr. {doctor} is not available at {time} in the next 3 days."

    return "No matching availability found."


def get_appointment_list(
    appointments: List[Dict],
    patient_mobile: str,
    doctor_name: Optional[str] = None,
    appointment_date: Optional[str] = None,
    appointment_time: Optional[str] = None,
    time_window: Optional[int] = None  # in hours
) -> List[Dict]:
    """
    Filters appointments based on the given criteria.

    Parameters:
        appointments (list): List of appointment dictionaries.
        patient_mobile (str): Mobile number of the patient (ignored if time_window is provided).
        doctor_name (str): Doctor's name (optional).
        appointment_date (str): Appointment date in YYYY-MM-DD (optional).
        appointment_time (str): Appointment time in HH:MM (optional).
        time_window (int): Optional window in hours from appointment_time.

    Returns:
        list: Filtered list of matching appointments.
    """
    filtered = []
    

    for appt in appointments:
        # Ignore patient_mobile filter when time_window is used
        if not time_window and appt.get("patient_mobile") != patient_mobile:
            continue

        if doctor_name and appt.get("doctor_name") != doctor_name:
            continue
        if appointment_date and appt.get("appointment_date") != appointment_date:
            continue

        if appointment_time and time_window:
            try:
                appt_time_str = appt.get("appointment_time")
                appt_datetime = datetime.strptime(f"{appt['appointment_date']} {appt_time_str}", "%Y-%m-%d %H:%M")
                start_time = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
                end_time = start_time + timedelta(hours=time_window)

                if not (start_time <= appt_datetime < end_time):
                    continue
            except Exception:
                continue  # Skip appointments with malformed date/time
        elif appointment_time:
            if appt.get("appointment_time") != appointment_time:
                continue

        filtered.append(appt)

    return filtered

def get_appointment_list_with_window(
    appointments: List[Dict],
    time_window: Optional[int] = None,
    doctor_name: Optional[str] = None,
    appointment_date: Optional[str] = None,
    appointment_time: Optional[str] = None
      # in hours
) -> List[Dict]:
    """
    Filters appointments based on the given criteria.

    Parameters:
        appointments (list): List of appointment dictionaries.
        patient_mobile (str): Mobile number of the patient (ignored if time_window is provided).
        doctor_name (str): Doctor's name (optional).
        appointment_date (str): Appointment date in YYYY-MM-DD (optional).
        appointment_time (str): Appointment time in HH:MM (optional).
        time_window (int): Optional window in hours from appointment_time.

    Returns:
        list: Filtered list of matching appointments.
    """
    filtered = []
    
    for appt in appointments:
        # Ignore patient_mobile filter when time_window is used
        
        if doctor_name and appt.get("doctor_name") != doctor_name:
            continue
        if appointment_date and appt.get("appointment_date") != appointment_date:
            continue

        if appointment_time and time_window:
            try:
                appt_time_str = appt.get("appointment_time")
                appt_datetime = datetime.strptime(f"{appt['appointment_date']} {appt_time_str}", "%Y-%m-%d %H:%M")
                start_time = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
                end_time = start_time + timedelta(hours=time_window)

                if not (start_time <= appt_datetime < end_time):
                    continue
            except Exception:
                continue  # Skip appointments with malformed date/time
        elif appointment_time:
            if appt.get("appointment_time") != appointment_time:
                continue

        filtered.append(appt)
        
    return filtered


