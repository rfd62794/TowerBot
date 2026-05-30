"""RFD IT Services Google OAuth authorization script.

Run once to authorize PrivyBot to read the RFDITServices@gmail.com account:
    uv run python scripts/rfd_auth.py

Opens a browser — sign in as RFDITServices@gmail.com — authorize all scopes.
Token saved to config/rfd_token.json for future use.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

CLIENT_SECRETS_PATH = os.getenv("YOUTUBE_CLIENT_SECRETS", "config/client_secret.json")
TOKEN_PATH = os.getenv("RFD_GMAIL_TOKEN_PATH", "config/rfd_token.json")


def main():
    if not os.path.exists(CLIENT_SECRETS_PATH):
        print(f"Error: {CLIENT_SECRETS_PATH} not found.")
        print("Copy your Google OAuth client_secret.json to config/ first.")
        return

    print("Opening browser for OAuth authorization...")
    print("Sign in as RFDITServices@gmail.com when prompted.")
    print("Authorizing: Gmail, Calendar, Drive, Sheets, Docs (all readonly)")

    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_PATH, scopes=SCOPES
    )
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"\nRFD IT Services Gmail authorized.")
    print(f"Token saved to {TOKEN_PATH}")
    print("Gmail, Calendar, Drive, Sheets, and Docs are now readable for RFDITServices@gmail.com.")


if __name__ == "__main__":
    main()
