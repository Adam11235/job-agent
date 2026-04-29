import os.path
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        return build('calendar', 'v3', credentials=creds)
    return None

def schedule_job_event(title, start_dt, end_dt=None, event_type="", meeting_link=None):
    service = get_calendar_service()
    if not service or not start_dt:
        return

    # Helper to determine if it's a full timestamp or just a date
    def format_time(time_str):
        if "T" in time_str:
            return {"dateTime": time_str, "timeZone": "Europe/Warsaw"}
        return {"date": time_str}

    # If no end time, default to +1 hour for dateTime or same day for date
    if not end_dt:
        if "T" in start_dt:
            try:
                dt_obj = datetime.fromisoformat(start_dt.replace('Z', '+00:00'))
                end_dt = (dt_obj + timedelta(hours=1)).isoformat()
            except: end_dt = start_dt
        else:
            end_dt = start_dt

    description = f"Type: {event_type}"
    if meeting_link:
        description += f"\nLink: {meeting_link}"

    event_body = {
        'summary': title or "Job Event",
        'description': description,
        'location': meeting_link or "",
        'start': format_time(start_dt),
        'end': format_time(end_dt)
    }

    try:
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        print(f"📅 Scheduled: {event.get('htmlLink')}")
    except Exception as e:
        print(f"❌ API Error: {e}")