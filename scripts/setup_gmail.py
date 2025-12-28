"""Gmail API setup and authentication script."""

import os.path
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> None:
    """Run Gmail API authentication flow."""
    creds = None
    credentials_file = "credentials.json"
    token_file = "token.json"

    # Check if credentials.json exists
    if not os.path.exists(credentials_file):
        print(f"Error: {credentials_file} not found!")
        print("\nPlease follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing")
        print("3. Enable Gmail API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print(f"5. Download credentials and save as '{credentials_file}'")
        sys.exit(1)

    # The file token.json stores the user's access and refresh tokens
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("Starting authentication flow...")
            print("A browser window will open. Please authorize the application.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_file, "w") as token:
            token.write(creds.to_json())
        print(f"\nCredentials saved to {token_file}")

    print("\n✓ Gmail API setup complete!")
    print(f"✓ Credentials file: {credentials_file}")
    print(f"✓ Token file: {token_file}")
    print("\nYou can now use the Gmail API to fetch newsletters.")


if __name__ == "__main__":
    main()
