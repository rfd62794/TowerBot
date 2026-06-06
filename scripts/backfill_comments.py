import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from infra.db import init_db
init_db()

from api.google.youtube_api import youtube_api
from tools.content.videos import post_video_comment
import yaml

youtube = youtube_api._build_data_client()

# Get uploads playlist ID
channel = youtube.channels().list(part="contentDetails", mine=True).execute()
uploads_id = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

# Get all videos
videos = []
page_token = None
while True:
    resp = youtube.playlistItems().list(
        part="snippet", playlistId=uploads_id,
        maxResults=50, pageToken=page_token
    ).execute()
    for item in resp["items"]:
        videos.append({
            "id": item["snippet"]["resourceId"]["videoId"],
            "title": item["snippet"]["title"]
        })
    page_token = resp.get("nextPageToken")
    if not page_token:
        break

# Get channel ID to check existing comments
me = youtube.channels().list(part="id", mine=True).execute()
my_channel_id = me["items"][0]["id"]

posted = 0
skipped = 0
for v in videos:
    threads = youtube.commentThreads().list(
        part="snippet", videoId=v["id"], maxResults=20
    ).execute()
    owner_commented = any(
        t["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"] == my_channel_id
        for t in threads.get("items", [])
    )
    if owner_commented:
        print(f"SKIP (has comment): {v['title']}")
        skipped += 1
        continue
    # Determine series
    title = v["title"]
    series = None
    for s in ["Everything is Crab", "Dune: Awakening", "VoidDrift", 
              "Scritchy Scratchy", "My Little Universe", "Raccoin", 
              "Escape From Duckov", "Fishing Inc"]:
        if s.lower() in title.lower():
            series = s
            break
    result = post_video_comment(video_id=v["id"], series=series)
    if result.get("ok"):
        print(f"POSTED: {v['title']}")
        posted += 1
    else:
        print(f"FAILED: {v['title']} — {result.get('error')}")

print(f"\nDone: {posted} posted, {skipped} skipped")
