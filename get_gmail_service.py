import re, base64, os, json
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow # type: ignore
from googleapiclient.discovery import build # type: ignore

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def get_latest_thread_and_sender(history_id):
    service = get_service()    
    response = service.users().history().list(userId='me', historyTypes=['messageAdded'], startHistoryId=history_id ).execute()
        
    new_messages = []
    for record in response.get('history', []):
        for msg in record.get('messagesAdded', []):
            message = msg['message']
            message_id = message['id']
            
            if 'SENT' not in message.get('labelIds', []):
                full_message = service.users().messages().get(userId='me', id=message_id, format='full' ).execute()
                headers = full_message['payload']['headers']
                sender = next((h['value'] for h in headers if h['name'] == 'From'), None)
                match = re.search(r'<(.+?)>', sender) if sender else None
                sender_email = match.group(1) if match else sender
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
                    # Walk through parts and fetch the plain text body
                def extract_body(payload):
                    if 'parts' in payload:
                        for part in payload['parts']:
                            if part['mimeType'] == 'text/plain':
                                return base64.urlsafe_b64decode(part['body']['data']).decode()
                            else:
                                continue
                                #return  base64.urlsafe_b64decode(payload['body']['data']).decode()

                full_message_text =  extract_body(full_message['payload'])
                new_messages.append(full_message_text)

    with open('history_id.json', 'w') as f:
            json.dump({'historyId': response['historyId']}, f)
    
    if len(new_messages) == 0:
        return "No New Messages","noreply@noreply.com","no_subject"
    
    return full_message_text, sender_email, subject

def send_email_reply(to_email, subject, message_text):
    service = get_service()
    message = MIMEText(message_text)
    message['to'] = to_email
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw}
    service.users().messages().send(userId='me', body=body).execute()
