from googleapiclient.discovery import build # type: ignore
from google.oauth2.credentials import Credentials # type: ignore
import json


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']


def setup_gmail_watch():
    # Load your OAuth2 credentials (make sure token.json is present)
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Build the Gmail service
    service = build('gmail', 'v1', credentials=creds)

    # Set up watch request
    request = {
        'labelIds': ['CATEGORY_PERSONAL'],  # Only watch "Primary" tab
        'topicName': 'projects/gmail-trigger-457610/topics/gmail-notifications',
        'labelFilterBehavior': 'include'
    }

    response = service.users().watch(userId='me', body=request).execute()
    history_id = response.get('historyId')
    
    with open('history_id.json', 'w') as f:
        json.dump({'historyId': history_id}, f)
        
    print("Watch set. History ID:", history_id)

# Call the function
setup_gmail_watch()
