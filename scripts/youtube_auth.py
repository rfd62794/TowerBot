"""YouTube OAuth authorization script.

Run once to authorize PrivyBot to access your YouTube channel:
    uv run python scripts/youtube_auth.py

This opens a browser for you to authorize the app, then saves
the OAuth token to config/youtube_token.json for future use.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes required for YouTube Analytics and Data API
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",      # ADD: comments, video updates, playlists
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",        # ADD: create/update calendar events
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",             # ADD: send emails (approval gates, notifications)
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",             # ADD: create files in Drive (YAML generation)
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/spreadsheets",           # ADD: write to sheets (RFD_Sheets_MCP)
    "https://www.googleapis.com/auth/documents.readonly",
]

CLIENT_SECRETS_PATH = "config/client_secret.json"
TOKEN_PATH = "config/youtube_token.json"


def main():
    """Run the OAuth flow and save the token."""
    if not os.path.exists(CLIENT_SECRETS_PATH):
        print(f"Error: {CLIENT_SECRETS_PATH} not found.")
        print("Copy your Google OAuth client_secret.json to config/ first.")
        return

    print("Opening browser for OAuth authorization...")
    print("You'll be asked to authorize PrivyBot to access your YouTube channel.")

    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_PATH, scopes=SCOPES
    )
    creds = flow.run_local_server(port=0)

    # Save the credentials
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"\nOAuth token saved to {TOKEN_PATH}")
    print("You can now use YouTube tools in PrivyBot.")
    print("The token will refresh automatically when expired.")


if __name__ == "__main__":
    main()
