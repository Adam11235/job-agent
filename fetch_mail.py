import os.path
import base64
from datetime import datetime # <-- NEW IMPORT
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/calendar.events']

def get_services():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

def fetch_todays_emails():
    gmail = get_services()
    
    # Generate today's date in YYYY/MM/DD format for the Gmail query
    today = datetime.now().strftime('%Y/%m/%d')
    
    # Query: inbox only, strictly AFTER midnight today
    query = f"in:inbox after:{today}"
    
    results = gmail.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        print(f"No new emails found for today ({today}).")
        return []

    email_data = []

    for msg in messages:
        full_msg = gmail.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        payload = full_msg['payload']
        
        headers = payload['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        snippet = full_msg.get('snippet', '')

        # Recursively hunt for the HTML part of the email
        def get_html_body(part):
            if part.get('mimeType') == 'text/html':
                return part['body'].get('data', '')
            if 'parts' in part:
                for p in part['parts']:
                    res = get_html_body(p)
                    if res: return res
            return ''

        html_data = get_html_body(payload)
        extracted_links = []

        if html_data:
            # Decode the base64 email body
            decoded_html = base64.urlsafe_b64decode(html_data).decode('utf-8', errors='ignore')
            soup = BeautifulSoup(decoded_html, 'html.parser')
            
            # Extract only Pracuj.pl job links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if "pracuj.pl/praca/" in href:
                    extracted_links.append(href)

        # Separate the short text (for AI) from the links (for the buffer)
        email_data.append({
            "subject": subject, 
            "content": snippet, 
            "links": list(set(extracted_links))
        })

    return email_data