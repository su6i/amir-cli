---
title: "YouTube Analytics & Optimization Automation"
description: Track views, CTR, watch time via YouTube Analytics API — automated A/B testing, performance monitoring, content optimization
location: .agent/skills/youtube-analytics.md
agent_priority: Standard
last_updated: 2026-05-30
---

**Related Skills:**
- [YouTube Data API v3](youtube-data-api.md) — upload, thumbnails, scheduling
- [YouTube Automation Pipeline](youtube-automation-pipeline.md) — end-to-end production
- [YouTube SEO](youtube-seo.md) — title/tag optimization

---

# YouTube Analytics & Optimization Automation

Deep analytics, CTR tracking, thumbnail A/B testing, and automated reporting using YouTube Analytics API v2 and YouTube Data API v3.

## 1. Auth Setup (Analytics-Specific)

Analytics API v2 is a **separate service** from the Data API v3. Build both from the same OAuth credentials.

**Scopes required:**

| Scope | Purpose |
|---|---|
| `https://www.googleapis.com/auth/yt-analytics.readonly` | Views, watch time, CTR, retention |
| `https://www.googleapis.com/auth/yt-analytics-monetary.readonly` | + revenue metrics |
| `https://www.googleapis.com/auth/youtube.readonly` | Video list (for channel ID) |
| `https://www.googleapis.com/auth/youtube` | Upload thumbnails (A/B test) |

```python
import os, pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
    "https://www.googleapis.com/auth/youtube",
]
TOKEN_FILE = os.path.expanduser("~/.config/yt_analytics_token.pickle")
CLIENT_SECRETS = os.path.expanduser("~/.config/yt_client_secrets.json")


def get_services():
    """Returns (youtube, analytics) service tuple."""
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
    youtube = build("youtube", "v3", credentials=creds)
    analytics = build("youtubeAnalytics", "v2", credentials=creds)
    return youtube, analytics


def get_channel_id(youtube) -> str:
    """Fetch the authenticated user's channel ID."""
    resp = youtube.channels().list(part="id", mine=True).execute()
    return resp["items"][0]["id"]
```

---

## 2. Key Metrics Reference

### Analytics API v2 Metrics

| Metric | Description | Typical Range |
|---|---|---|
| `views` | Total video views | — |
| `estimatedMinutesWatched` | Cumulative watch time in minutes | — |
| `averageViewDuration` | Mean seconds watched per view | 100–400s |
| `averageViewPercentage` | Mean % of video watched | 30–55% |
| `subscribersGained` | Net new subs from this video's watch page | — |
| `subscribersLost` | Unsubs attributed to watch page | — |
| `impressions` | Times thumbnail shown to logged-in users | — |
| `impressionClickThroughRate` | impressions → clicks ratio | 2–10% |
| `cardClickRate` | Card click / card impression | — |
| `cardTeaserClickRate` | Card teaser click / teaser shown | — |
| `likes` | Likes received | — |
| `comments` | Comments received | — |
| `shares` | External shares | — |
| `estimatedRevenue` | Total estimated revenue (USD) | monetary scope |
| `estimatedAdRevenue` | Ad revenue only | monetary scope |
| `cpm` | Cost per 1000 impressions | monetary scope |

### Key Dimensions

| Dimension | Description |
|---|---|
| `day` | Daily breakdown (YYYY-MM-DD) |
| `month` | Monthly breakdown (YYYY-MM) |
| `video` | Per-video breakdown |
| `country` | ISO 3166-1 alpha-2 |
| `ageGroup` | `age13-17`, `age18-24`, `age25-34`, … |
| `gender` | `female`, `male`, `userSpecified` |
| `deviceType` | `DESKTOP`, `MOBILE`, `TABLET`, `TV` |
| `liveOrOnDemand` | `LIVE`, `ON_DEMAND` |
| `elapsedVideoTimeRatio` | 0.01–1.00 (audience retention) |

### Audience Retention Dimension (Special)
Retention reports are **per-video only** and return 100 data points. Dimension `elapsedVideoTimeRatio=0.40` means 40% through the video.

---

## 3. Fetch Channel Performance Report

```python
import pandas as pd
from datetime import date, timedelta


def channel_performance(analytics, channel_id: str,
                        days: int = 28) -> pd.DataFrame:
    """
    Daily views, watch time, CTR, avg view duration for the last N days.
    Returns a DataFrame indexed by date.
    """
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()

    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics=(
            "views,estimatedMinutesWatched,averageViewDuration,"
            "averageViewPercentage,impressions,impressionClickThroughRate,"
            "subscribersGained,subscribersLost,likes,shares"
        ),
        dimensions="day",
        sort="day",
    ).execute()

    cols = [h["name"] for h in resp["columnHeaders"]]
    rows = resp.get("rows", [])
    df = pd.DataFrame(rows, columns=cols)
    df["day"] = pd.to_datetime(df["day"])
    df = df.set_index("day")
    return df


# Usage:
# youtube, analytics = get_services()
# channel_id = get_channel_id(youtube)
# df = channel_performance(analytics, channel_id, days=28)
# print(df[["views", "impressionClickThroughRate", "averageViewDuration"]].tail(7))
```

---

## 4. CTR Monitoring Per Video

Track `impressionClickThroughRate` per video to identify underperformers.

```python
def video_ctr_report(analytics, channel_id: str,
                     days: int = 28, min_impressions: int = 500) -> pd.DataFrame:
    """
    Returns CTR and impression count per video.
    Filters to videos with >= min_impressions for statistical significance.
    """
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()

    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics="views,impressions,impressionClickThroughRate,averageViewDuration",
        dimensions="video",
        sort="-impressions",
        maxResults=50,
    ).execute()

    cols = [h["name"] for h in resp["columnHeaders"]]
    df = pd.DataFrame(resp.get("rows", []), columns=cols)
    df = df[df["impressions"].astype(float) >= min_impressions].copy()
    df["impressionClickThroughRate"] = df["impressionClickThroughRate"].astype(float)
    df = df.sort_values("impressionClickThroughRate")

    # Flag low CTR (below channel median)
    median_ctr = df["impressionClickThroughRate"].median()
    df["ctr_flag"] = df["impressionClickThroughRate"] < median_ctr * 0.7
    return df
```

---

## 5. Thumbnail A/B Testing

YouTube (2026) natively supports up to 5 title/thumbnail variants with auto-rollout at 10k impressions. The Data API v3 also allows programmatic thumbnail rotation.

### 5.1 Native YouTube A/B (Recommended)

YouTube Studio → Content → select video → "Test & compare" (available to channels with >1,000 subs). Results auto-select winner based on **watch time share** after 14 days or 10k impressions.

### 5.2 Manual A/B via API (Programmatic)

Upload thumbnail variant B after N hours, then compare CTR windows.

```python
import time
from googleapiclient.http import MediaFileUpload


def run_thumbnail_ab_test(
    youtube,
    analytics,
    channel_id: str,
    video_id: str,
    thumbnail_a: str,       # path to variant A (current)
    thumbnail_b: str,       # path to variant B
    observe_hours: int = 24,
) -> dict:
    """
    Simple A/B: set thumbnail A, wait, record CTR.
    Set thumbnail B, wait same period, record CTR. Return comparison dict.

    NOTE: Each thumbnails.set() costs 50 quota units.
    For channels with native A/B test access, prefer YouTube Studio.
    """

    def set_thumb(path: str):
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(path, mimetype="image/jpeg"),
        ).execute()

    def get_ctr_window(hours: int) -> float:
        end = date.today().isoformat()
        start = (date.today() - timedelta(days=1)).isoformat()
        resp = analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start,
            endDate=end,
            metrics="impressions,impressionClickThroughRate",
            filters=f"video=={video_id}",
        ).execute()
        rows = resp.get("rows", [])
        return float(rows[0][1]) if rows else 0.0

    print("Setting thumbnail A...")
    set_thumb(thumbnail_a)
    time.sleep(observe_hours * 3600)
    ctr_a = get_ctr_window(observe_hours)
    print(f"CTR A: {ctr_a:.2%}")

    print("Setting thumbnail B...")
    set_thumb(thumbnail_b)
    time.sleep(observe_hours * 3600)
    ctr_b = get_ctr_window(observe_hours)
    print(f"CTR B: {ctr_b:.2%}")

    winner = thumbnail_b if ctr_b > ctr_a else thumbnail_a
    winner_label = "B" if ctr_b > ctr_a else "A"

    # Auto-set winning thumbnail
    set_thumb(winner)
    print(f"Winner: {winner_label} ({max(ctr_a, ctr_b):.2%} CTR)")

    return {
        "video_id": video_id,
        "ctr_a": ctr_a,
        "ctr_b": ctr_b,
        "winner": winner_label,
        "lift": abs(ctr_b - ctr_a) / max(ctr_a, 1e-6),
    }
```

---

## 6. Watch Time Funnel — Audience Retention

Identify drop-off points. Analytics returns 100 evenly-spaced data points per video.

```python
def audience_retention(analytics, channel_id: str,
                       video_id: str) -> pd.DataFrame:
    """
    Returns DataFrame with columns: ratio (0.01-1.0), audienceWatchRatio.
    ratio=0.5 means 50% through the video.
    """
    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate="2000-01-01",
        endDate=date.today().isoformat(),
        metrics="audienceWatchRatio,relativeRetentionPerformance",
        dimensions="elapsedVideoTimeRatio",
        filters=f"video=={video_id}",
        sort="elapsedVideoTimeRatio",
    ).execute()

    cols = [h["name"] for h in resp["columnHeaders"]]
    df = pd.DataFrame(resp.get("rows", []), columns=cols)
    df = df.astype(float)
    df["pct_through"] = (df["elapsedVideoTimeRatio"] * 100).round(0).astype(int)

    # Detect major drop-off points (>10% relative drop between consecutive points)
    df["drop"] = df["audienceWatchRatio"].pct_change() < -0.10
    drop_points = df[df["drop"]]["pct_through"].tolist()
    if drop_points:
        print(f"Major drop-offs at: {drop_points}% through video")

    return df


def retention_summary(df: pd.DataFrame) -> dict:
    """Key retention milestones."""
    def at(pct: int) -> float:
        row = df[df["pct_through"] == pct]
        return float(row["audienceWatchRatio"].iloc[0]) if not row.empty else None

    return {
        "30s_retention": at(5),      # approx 30s in a 10-min video
        "at_25pct": at(25),
        "at_50pct": at(50),
        "at_75pct": at(75),
        "at_end": at(100),
    }
```

---

## 7. Weekly Automated Report

Generate a channel performance summary and send via Telegram or email.

```python
import httpx
from datetime import date, timedelta


def weekly_report_text(analytics, channel_id: str) -> str:
    """Build a plain-text weekly summary."""
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=7)).isoformat()

    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics=(
            "views,estimatedMinutesWatched,impressions,"
            "impressionClickThroughRate,subscribersGained,subscribersLost"
        ),
    ).execute()

    row = resp.get("rows", [[0] * 6])[0]
    cols = [h["name"] for h in resp["columnHeaders"]]
    data = dict(zip(cols, row))

    net_subs = int(data.get("subscribersGained", 0)) - int(data.get("subscribersLost", 0))
    hours_watched = int(data.get("estimatedMinutesWatched", 0)) // 60

    return (
        f"YouTube Weekly Report ({start} → {end})\n"
        f"Views:          {int(data.get('views', 0)):,}\n"
        f"Watch Hours:    {hours_watched:,}h\n"
        f"Impressions:    {int(data.get('impressions', 0)):,}\n"
        f"CTR:            {float(data.get('impressionClickThroughRate', 0)):.2%}\n"
        f"Net Subscribers:{net_subs:+d}\n"
    )


def send_telegram(text: str, bot_token: str, chat_id: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    httpx.post(url, json={"chat_id": chat_id, "text": text})


# Cron: run every Monday at 09:00
# youtube, analytics = get_services()
# channel_id = get_channel_id(youtube)
# report = weekly_report_text(analytics, channel_id)
# send_telegram(report, os.environ["TG_BOT_TOKEN"], os.environ["TG_CHAT_ID"])
```

---

## 8. Best Upload Time Detection

Analyse historical `day`+`hour` data to find when your audience is most active.

```python
def best_upload_times(analytics, channel_id: str, days: int = 90) -> pd.DataFrame:
    """
    Aggregate views by day-of-week and hour to find peak engagement windows.
    Uses the Reporting API bulk CSV (avoids per-query quota pressure).

    Fallback: use Analytics API with 'day' dimension + video publish times
    correlated with first-48h views.
    """
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()

    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics="views,estimatedMinutesWatched",
        dimensions="day",
        sort="day",
    ).execute()

    cols = [h["name"] for h in resp["columnHeaders"]]
    df = pd.DataFrame(resp.get("rows", []), columns=cols)
    df["day"] = pd.to_datetime(df["day"])
    df["dayofweek"] = df["day"].dt.day_name()
    df["views"] = df["views"].astype(float)

    pivot = df.groupby("dayofweek")["views"].mean().sort_values(ascending=False)
    print("Best days to publish (avg views):")
    print(pivot.to_string())
    return pivot


# Note: Hour-level analysis requires YouTube Studio → Analytics → Audience tab
# (not available via API). Day-of-week is the best API-accessible proxy.
```

---

## 9. Content Gap Analysis

Identify which topics drive the most watch time relative to views — high watch-time-per-view topics signal strong audience interest.

```python
def content_gap_analysis(analytics, youtube, channel_id: str,
                         days: int = 90) -> pd.DataFrame:
    """
    Per-video: watch time per view, CTR, and subscriber conversion rate.
    High watchTimePerView + low CTR → good content, weak thumbnail/title.
    High CTR + low watchTimePerView → misleading thumbnail, fix the video hook.
    """
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=days)).isoformat()

    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start,
        endDate=end,
        metrics=(
            "views,estimatedMinutesWatched,averageViewDuration,"
            "impressions,impressionClickThroughRate,subscribersGained"
        ),
        dimensions="video",
        sort="-estimatedMinutesWatched",
        maxResults=50,
    ).execute()

    cols = [h["name"] for h in resp["columnHeaders"]]
    df = pd.DataFrame(resp.get("rows", []), columns=cols)

    # Enrich with video titles
    video_ids = df["video"].tolist()
    titles = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        r = youtube.videos().list(
            part="snippet", id=",".join(batch)
        ).execute()
        for item in r.get("items", []):
            titles[item["id"]] = item["snippet"]["title"]

    df["title"] = df["video"].map(titles)
    df["views"] = df["views"].astype(float)
    df["estimatedMinutesWatched"] = df["estimatedMinutesWatched"].astype(float)
    df["impressionClickThroughRate"] = df["impressionClickThroughRate"].astype(float)
    df["subscribersGained"] = df["subscribersGained"].astype(float)

    df["watchMinPerView"] = df["estimatedMinutesWatched"] / df["views"].replace(0, 1)
    df["subConversionRate"] = df["subscribersGained"] / df["views"].replace(0, 1)

    df["diagnosis"] = "OK"
    df.loc[
        (df["watchMinPerView"] > df["watchMinPerView"].median()) &
        (df["impressionClickThroughRate"] < df["impressionClickThroughRate"].median()),
        "diagnosis"
    ] = "Fix thumbnail/title"
    df.loc[
        (df["watchMinPerView"] < df["watchMinPerView"].median()) &
        (df["impressionClickThroughRate"] > df["impressionClickThroughRate"].median()),
        "diagnosis"
    ] = "Fix hook/content"

    return df[["title", "views", "watchMinPerView", "impressionClickThroughRate",
               "subConversionRate", "diagnosis"]].sort_values(
        "watchMinPerView", ascending=False
    )
```

---

## 10. Quota Reference

| Operation | Units | Daily limit |
|---|---|---|
| Analytics `reports.query` | 1 | 10,000/project |
| `videos.list` (read) | 1 | — |
| `thumbnails.set` | 50 | — |
| Reporting API (bulk CSV) | 0 | separate quota |

**Quota-saving tips:**
- Query channel-level aggregates daily; drill into per-video only for top/bottom performers
- Cache results — analytics data is final after 48h delay (not real-time)
- Use YouTube Reporting API for bulk historical exports instead of many `reports.query` calls

---

## 11. Gotchas

| Issue | Cause | Fix |
|---|---|---|
| `impressions` / `impressionClickThroughRate` missing | Only available for **logged-in** YouTube users | Expected — partial data |
| Retention report returns no rows | Video must have ≥ a few thousand views | Normal for new videos |
| Data is delayed 48–72h | Analytics pipeline lag | Do not query yesterday for real-time decisions |
| `forbidden` on monetary metrics | Wrong scope | Add `yt-analytics-monetary.readonly` |
| `thumbnail.set` returns 403 | Channel < 1,000 subs or not in YPP | Cannot be worked around programmatically |
| A/B test CTR swings wildly | Low impression volume | Wait for 1,000+ impressions per variant |

---

## References

- [YouTube Analytics API v2 Reference](https://developers.google.com/youtube/analytics/v2/reference)
- [Metrics Reference](https://developers.google.com/youtube/analytics/metrics)
- [Dimensions Reference](https://developers.google.com/youtube/analytics/dimensions)
- [Channel Reports](https://developers.google.com/youtube/analytics/channel_reports)
- [Sample API Requests](https://developers.google.com/youtube/analytics/sample-requests)
- [Audience Retention Report](https://developers.google.com/youtube/analytics/audience_retention)
- [Official Python Samples — yt_analytics_report.py](https://github.com/youtube/api-samples/blob/master/python/yt_analytics_report.py)
- [Thumbnails.set Reference](https://developers.google.com/youtube/v3/docs/thumbnails/set)
- [TubeBuddy Thumbnail A/B Testing](https://www.tubebuddy.com/tools/youtube-thumbnail-test)
