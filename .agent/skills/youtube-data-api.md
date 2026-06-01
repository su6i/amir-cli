---
title: "YouTube Data API v3"
description: Automate YouTube uploads, scheduling, thumbnails, playlists, and analytics with Python
location: .agent/skills/youtube-data-api.md
agent_priority: Standard
last_updated: 2026-05-30
---

# YouTube Data API v3

Automate YouTube channel operations using `google-api-python-client` and `google-auth-oauthlib`.

## Dependencies

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

---

## 1. Authentication

### OAuth2 (required for upload, thumbnail, playlist write)

**Scopes:**

| Scope | Purpose |
|---|---|
| `https://www.googleapis.com/auth/youtube.upload` | Upload videos only |
| `https://www.googleapis.com/auth/youtube` | Full channel management |
| `https://www.googleapis.com/auth/youtube.readonly` | Read-only |
| `https://www.googleapis.com/auth/yt-analytics.readonly` | Analytics read |
| `https://www.googleapis.com/auth/yt-analytics-monetary.readonly` | Analytics + revenue |

**Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Enable "YouTube Data API v3"
2. Create OAuth2 credentials → Download as `client_secrets.json`
3. First run opens browser for consent; token cached in `token.pickle`

```python
import os, pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
]
CLIENT_SECRETS = "client_secrets.json"
TOKEN_FILE = "token.pickle"

def get_youtube_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)
```

### Service Account (read-only / public data)

Service accounts cannot upload to a channel unless domain-wide delegation is configured. For uploads, use OAuth2.

---

## 2. Upload Video with Metadata

**Quota cost:** ~100 units (reduced from 1,600 in December 2025)

```python
from googleapiclient.http import MediaFileUpload

CATEGORY_IDS = {
    "Science & Technology": "28",
    "Education": "27",
    "Entertainment": "24",
    "People & Blogs": "22",
    "News & Politics": "25",
}

def upload_video(youtube, file_path: str, title: str, description: str,
                 tags: list[str], category: str = "Science & Technology",
                 privacy: str = "private") -> str:
    """Upload video and return video ID."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_IDS.get(category, "28"),
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,  # "public" | "private" | "unlisted"
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True,
                            mimetype="video/*")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}%")
    video_id = response["id"]
    print(f"Uploaded: https://youtu.be/{video_id}")
    return video_id
```

---

## 3. Set Thumbnail

**Quota cost:** 50 units. Requires channel with 1,000+ subscribers OR YouTube Partner Program for custom thumbnails.

```python
from googleapiclient.http import MediaFileUpload

def set_thumbnail(youtube, video_id: str, image_path: str) -> None:
    """Set custom thumbnail. JPEG/PNG, min 1280x720, max 2 MB."""
    media = MediaFileUpload(image_path, mimetype="image/jpeg")
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()
    print(f"Thumbnail set for {video_id}")
```

---

## 4. Schedule Publish Time

Set `privacyStatus="private"` **and** `publishAt` together. YouTube publishes automatically at the given UTC time.

```python
from datetime import datetime, timezone, timedelta

def schedule_video(youtube, video_id: str, publish_dt: datetime) -> None:
    """Schedule a private video to go public at publish_dt (UTC)."""
    # publishAt must be in the future and video must be private
    publish_str = publish_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    youtube.videos().update(
        part="status",
        body={
            "id": video_id,
            "status": {
                "privacyStatus": "private",
                "publishAt": publish_str,
            },
        },
    ).execute()
    print(f"Scheduled for {publish_str}")

# Example: publish tomorrow at 15:00 UTC
tomorrow_3pm = datetime.now(timezone.utc).replace(
    hour=15, minute=0, second=0, microsecond=0
) + timedelta(days=1)
# schedule_video(youtube, video_id, tomorrow_3pm)
```

---

## 5. Playlist Management

**Quota cost:** playlists.insert = 50 units, playlistItems.insert = 50 units

```python
def create_playlist(youtube, title: str, description: str = "",
                    privacy: str = "public") -> str:
    """Create playlist and return playlist ID."""
    response = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": privacy},
        },
    ).execute()
    playlist_id = response["id"]
    print(f"Playlist created: {playlist_id}")
    return playlist_id


def add_video_to_playlist(youtube, playlist_id: str, video_id: str,
                          position: int = 0) -> None:
    """Add video to playlist at given position."""
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
                "position": position,
            }
        },
    ).execute()
    print(f"Added {video_id} to playlist {playlist_id}")
```

---

## 6. Analytics API

Use a **separate** service for analytics (`youtubeAnalytics`, `v2`). Requires monetary scope for revenue metrics.

```python
def get_analytics_service(creds):
    return build("youtubeAnalytics", "v2", credentials=creds)


def get_video_stats(analytics, channel_id: str,
                    start_date: str, end_date: str,
                    video_id: str | None = None) -> dict:
    """
    Fetch views, watch time, and revenue for a channel or specific video.
    channel_id format: "channel==UCxxxx"
    start/end_date: "YYYY-MM-DD"
    """
    filters = f"channel=={channel_id}"
    if video_id:
        filters += f";video=={video_id}"

    response = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start_date,
        endDate=end_date,
        metrics="views,estimatedMinutesWatched,averageViewDuration,"
                "averageViewPercentage,estimatedRevenue,estimatedAdRevenue",
        dimensions="day",
        filters=filters if video_id else f"channel=={channel_id}",
        sort="day",
    ).execute()

    rows = response.get("rows", [])
    columns = [h["name"] for h in response.get("columnHeaders", [])]
    return [dict(zip(columns, row)) for row in rows]


# Example output row:
# {"day": "2026-05-01", "views": 1234, "estimatedMinutesWatched": 5678,
#  "averageViewDuration": 275, "averageViewPercentage": 42.3,
#  "estimatedRevenue": 3.14, "estimatedAdRevenue": 2.71}
```

---

## 7. Chapters / Timestamps in Description

YouTube auto-detects chapters from timestamps in the description. Rules:
- First timestamp must be `0:00`
- At least 3 timestamps required
- Minimum chapter duration: 10 seconds

```python
def build_description_with_chapters(intro: str,
                                    chapters: list[tuple[int, str]]) -> str:
    """
    chapters: list of (seconds_offset, title)
    Example: [(0, "Intro"), (62, "Setup"), (210, "Demo")]
    """
    def fmt(s: int) -> str:
        h, r = divmod(s, 3600)
        m, sec = divmod(r, 60)
        return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

    lines = [intro, ""]
    for secs, title in sorted(chapters, key=lambda x: x[0]):
        lines.append(f"{fmt(secs)} {title}")
    return "\n".join(lines)


# Example:
description = build_description_with_chapters(
    intro="Full tutorial on YouTube API automation.",
    chapters=[(0, "Intro"), (90, "Authentication"), (300, "Upload"), (600, "Analytics")],
)
```

---

## 8. Common Errors and Quotas

### Daily Quota

| Default | Reset |
|---|---|
| 10,000 units/day | Midnight Pacific Time |

Request a quota increase: [Google Cloud Console → Quotas](https://console.cloud.google.com/iam-admin/quotas)

### Quota Costs per Operation

| Operation | Units |
|---|---|
| `videos.insert` | ~100 (was 1,600 before Dec 2025) |
| `videos.update` | 50 |
| `thumbnails.set` | 50 |
| `playlists.insert` | 50 |
| `playlistItems.insert` | 50 |
| `videos.list` (read) | 1–3 |
| Analytics query | 1 |

### Common Errors

| Error | Cause | Fix |
|---|---|---|
| `quotaExceeded` | Daily 10k units exhausted | Wait for reset or request increase |
| `uploadLimitExceeded` | Channel hit daily upload cap | ~6 uploads/day for new channels |
| `forbidden` (thumbnail) | Channel < 1,000 subscribers | Use default thumbnails or join YPP |
| `invalidValue` (publishAt) | Time is in the past or bad format | Use UTC ISO 8601, future time |
| `invalidValue` (categoryId) | Wrong category ID for region | Use `videoCategories.list` to fetch valid IDs |
| `tokenExpired` | OAuth token expired | Refresh logic in `get_youtube_service()` handles this |

### Full Upload + Schedule + Thumbnail Pipeline

```python
def publish_video(file_path: str, thumbnail_path: str,
                  title: str, description: str, tags: list[str],
                  publish_at: datetime | None = None) -> str:
    youtube = get_youtube_service()

    privacy = "private" if publish_at else "public"
    video_id = upload_video(youtube, file_path, title, description, tags,
                            privacy=privacy)
    set_thumbnail(youtube, video_id, thumbnail_path)

    if publish_at:
        schedule_video(youtube, video_id, publish_at)

    return video_id
```

---

## References

- [YouTube Data API v3 Reference](https://developers.google.com/youtube/v3/docs)
- [Upload Guide](https://developers.google.com/youtube/v3/guides/uploading_a_video)
- [Analytics API](https://developers.google.com/youtube/analytics)
- [Official Python Samples](https://github.com/youtube/api-samples/tree/master/python)
- [google-api-python-client](https://github.com/googleapis/google-api-python-client)
- [Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
