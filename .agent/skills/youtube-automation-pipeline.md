---
title: "YouTube Automation Pipeline"
description: End-to-end pipeline: script → AI voiceover → video assembly → thumbnail → upload
location: .agent/skills/youtube-automation-pipeline.md
agent_priority: Standard
last_updated: 2026-05-30
---

**🔗 Related Skills:**
- [yt-dlp Web Download](youtube-dlp-web-download.md) - Download reference footage
- [FFmpeg Recipes](ffmpeg-recipes.md) - Video assembly and encoding
- [Subtitle Generator](subtitle-generator.md) - Auto-captions for uploaded videos
- [YouTube SEO](youtube-seo.md) - Title/description/tag optimization
- [Social Publisher](social-publisher.md) - Cross-platform publishing

[Back to README](../../README.md)

---

# Skill: YouTube Automation Pipeline

Full end-to-end pipeline for automated YouTube channel production. Covers every stage from topic research to published video. Designed for "faceless" channels (no on-camera presenter) but applies equally to narrated content.

---

## 1. Pipeline Architecture

```
Topic / Prompt
     │
     ▼
[Stage 1] Script Generation        ← LLM (Claude / GPT-4o / Gemini)
     │
     ▼
[Stage 2] AI Voiceover (TTS)       ← ElevenLabs / OpenAI TTS / Edge-TTS
     │
     ▼
[Stage 3] Visual Asset Collection  ← Stock footage API / DALL-E / Stable Diffusion
     │
     ▼
[Stage 4] Video Assembly           ← MoviePy / FFmpeg
     │
     ▼
[Stage 5] Captions / Subtitles     ← Whisper / amir subtitle
     │
     ▼
[Stage 6] Thumbnail Generation     ← Pillow / DALL-E / Canva API
     │
     ▼
[Stage 7] Metadata Generation      ← LLM (title / description / tags)
     │
     ▼
[Stage 8] Upload to YouTube        ← YouTube Data API v3
     │
     ▼
[Stage 9] Schedule / Publish       ← privacyStatus=private → scheduled publish time
```

---

## 2. Stage 1 — Script Generation (LLM)

```python
from anthropic import Anthropic

client = Anthropic()

def generate_script(topic: str, duration_minutes: int = 8) -> str:
    """Generate a YouTube video script for a given topic."""
    prompt = f"""Write a {duration_minutes}-minute YouTube video script about: {topic}

Structure:
- Hook (first 15 seconds — grab attention)
- Introduction (30 seconds)
- 3-5 main sections with clear transitions
- Call to action (last 30 seconds)

Style: conversational, engaging, no filler words.
Format: plain narration text only, no stage directions."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

---

## 3. Stage 2 — AI Voiceover (TTS)

### 3.1 ElevenLabs (Best Quality)

```python
from elevenlabs.client import ElevenLabs
from elevenlabs import save

def tts_elevenlabs(text: str, output_path: str, voice_id: str = "Rachel") -> str:
    client = ElevenLabs()  # reads ELEVENLABS_API_KEY from env
    audio = client.generate(
        text=text,
        voice=voice_id,
        model="eleven_multilingual_v2",
    )
    save(audio, output_path)
    return output_path
```

### 3.2 OpenAI TTS (Cost-Effective)

```python
from openai import OpenAI
from pathlib import Path

def tts_openai(text: str, output_path: str, voice: str = "alloy") -> str:
    """Voices: alloy, echo, fable, onyx, nova, shimmer"""
    client = OpenAI()
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=voice,
        input=text,
    )
    response.stream_to_file(output_path)
    return output_path
```

### 3.3 Edge-TTS (Free, 300+ Voices)

```bash
pip install edge-tts

# CLI
edge-tts --voice en-US-JennyNeural --text "Hello world" --write-media output.mp3

# Python
```

```python
import asyncio, edge_tts

async def tts_edge(text: str, output_path: str, voice: str = "en-US-JennyNeural"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

asyncio.run(tts_edge("Hello", "voice.mp3"))
```

---

## 4. Stage 3 — Visual Asset Collection

### 4.1 Stock Footage (Pexels API — Free)

```python
import httpx

def fetch_pexels_videos(query: str, count: int = 5) -> list[str]:
    """Returns list of video URLs."""
    headers = {"Authorization": PEXELS_API_KEY}
    r = httpx.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": query, "per_page": count, "orientation": "landscape"}
    )
    r.raise_for_status()
    videos = r.json()["videos"]
    # Pick highest-quality file for each result
    return [
        max(v["video_files"], key=lambda f: f.get("width", 0))["link"]
        for v in videos
    ]
```

### 4.2 AI Image Generation (DALL-E 3)

```python
from openai import OpenAI

def generate_image(prompt: str, output_path: str) -> str:
    client = OpenAI()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",   # 16:9 landscape
        quality="hd",
        n=1,
    )
    url = response.data[0].url
    img_data = httpx.get(url).content
    Path(output_path).write_bytes(img_data)
    return output_path
```

---

## 5. Stage 4 — Video Assembly (FFmpeg)

Prefer raw FFmpeg over MoviePy for production — faster and no re-encode overhead.

```bash
# Concatenate clips from a text file list
# clips.txt:
#   file '/tmp/clip1.mp4'
#   file '/tmp/clip2.mp4'
ffmpeg -f concat -safe 0 -i clips.txt -c copy assembled.mp4

# Overlay narration audio onto video
ffmpeg -i assembled.mp4 -i narration.mp3 \
  -map 0:v -map 1:a \
  -shortest -c:v copy -c:a aac \
  final.mp4

# Add background music at 20% volume under narration
ffmpeg -i video_with_narration.mp4 -i background_music.mp3 \
  -filter_complex "[1:a]volume=0.2[bg];[0:a][bg]amix=inputs=2:duration=first" \
  -c:v copy output.mp4
```

### 5.1 Python Assembly with MoviePy (Simple Cases)

```python
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

def assemble_video(clip_paths: list[str], audio_path: str, output: str):
    clips = [VideoFileClip(p) for p in clip_paths]
    video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip(audio_path).subclip(0, video.duration)
    final = video.set_audio(audio)
    final.write_videofile(output, codec="libx264", audio_codec="aac", fps=30)
    for c in clips:
        c.close()
```

---

## 6. Stage 5 — Captions

```bash
# Generate SRT from the assembled video using amir subtitle
amir subtitle final.mp4 --lang en

# Burn captions into video (for platforms that don't support external SRT)
ffmpeg -i final.mp4 -vf "subtitles=final.srt:force_style='FontSize=24'" \
  final_captioned.mp4
```

---

## 7. Stage 6 — Thumbnail Generation (Pillow)

```python
from PIL import Image, ImageDraw, ImageFont
import textwrap

def make_thumbnail(
    background_path: str,
    title: str,
    output_path: str,
    font_size: int = 80,
) -> str:
    img = Image.open(background_path).resize((1280, 720))
    draw = ImageDraw.Draw(img)

    # Semi-transparent overlay for readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 120))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)

    # Load font (fallback to default)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except OSError:
        font = ImageFont.load_default()

    # Word-wrap title
    lines = textwrap.wrap(title, width=20)
    y = 720 // 2 - (len(lines) * font_size) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((1280 - w) / 2, y), line, font=font, fill="white",
                  stroke_width=3, stroke_fill="black")
        y += font_size + 10

    img.convert("RGB").save(output_path, "JPEG", quality=95)
    return output_path
```

---

## 8. Stage 7 — Metadata Generation

```python
def generate_metadata(script: str, topic: str) -> dict:
    """Generate SEO-optimized title, description, tags via LLM."""
    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": f"""
Generate YouTube metadata for this video about: {topic}

Script excerpt (first 200 chars): {script[:200]}

Return JSON with:
- title: compelling, ≤70 chars, includes primary keyword
- description: 200-300 words, includes keywords naturally, ends with CTA
- tags: list of 10-15 relevant tags (mix of broad and specific)
"""}]
    )
    import json
    return json.loads(response.content[0].text)
```

---

## 9. Stage 8 — Upload to YouTube (Data API v3)

### 9.1 Setup

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

Required OAuth scope: `https://www.googleapis.com/auth/youtube.upload`

Obtain `client_secrets.json` from Google Cloud Console → APIs & Services → Credentials.

### 9.2 Upload Function

```python
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = Path("~/.config/youtube_token.json").expanduser()

def get_youtube_client():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: str,
    thumbnail_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "22",       # 22 = People & Blogs
    privacy: str = "private",      # "public" | "private" | "unlisted"
    publish_at: str | None = None, # ISO 8601, e.g. "2026-06-01T15:00:00Z"
) -> str:
    """Upload video and return video ID."""
    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "private" if publish_at else privacy,
            **({"publishAt": publish_at} if publish_at else {}),
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]

    # Set thumbnail
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path),
    ).execute()

    return video_id
```

---

## 10. Stage 9 — Scheduling

Use YouTube's built-in scheduled publish instead of cron-based triggers:

```python
from datetime import datetime, timezone, timedelta

def schedule_upload(video_path: str, metadata: dict, days_from_now: int = 1) -> str:
    publish_time = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    publish_at = publish_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    return upload_video(
        video_path=video_path,
        thumbnail_path=metadata["thumbnail_path"],
        title=metadata["title"],
        description=metadata["description"],
        tags=metadata["tags"],
        privacy="private",
        publish_at=publish_at,
    )
```

---

## 11. Full Pipeline Runner

```python
def run_pipeline(topic: str, output_dir: str = "/tmp/yt_pipeline") -> str:
    from pathlib import Path
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Script
    script = generate_script(topic, duration_minutes=8)
    (out / "script.txt").write_text(script)

    # 2. Voiceover
    tts_openai(script, str(out / "narration.mp3"))

    # 3. Visuals — fetch per paragraph keyword
    keywords = topic.split()[:3]
    clip_urls = fetch_pexels_videos(" ".join(keywords), count=8)
    clip_paths = []
    for i, url in enumerate(clip_urls):
        p = str(out / f"clip_{i}.mp4")
        httpx.get(url).content  # simplified — use streaming in production
        clip_paths.append(p)

    # 4. Assemble
    assemble_video(clip_paths, str(out / "narration.mp3"), str(out / "assembled.mp4"))

    # 5. Captions — call amir subtitle externally

    # 6. Thumbnail
    make_thumbnail(clip_paths[0], topic, str(out / "thumbnail.jpg"))

    # 7. Metadata
    meta = generate_metadata(script, topic)
    meta["thumbnail_path"] = str(out / "thumbnail.jpg")

    # 8. Upload (scheduled for tomorrow)
    video_id = schedule_upload(str(out / "assembled.mp4"), meta, days_from_now=1)
    return f"https://youtu.be/{video_id}"
```

---

## 12. Common Pitfalls & Best Practices

| Issue | Solution |
|-------|----------|
| OAuth token expires | Persist `token.json`, use `creds.refresh()` before upload |
| Video too long for TTS chunk limit | Split script into paragraphs, concatenate audio with FFmpeg |
| Stock footage aspect ratio mismatch | Normalize all clips to 1920×1080 with FFmpeg `scale+pad` before concat |
| YouTube quota exceeded (10,000 units/day) | One upload = 1600 units; max ~6 uploads/day on free quota |
| Thumbnail not appearing | Wait 60s after upload before calling `thumbnails().set()` |
| Title/description violates policy | Run content moderation check before upload |
| Resumable upload interrupted | Use `MediaFileUpload(resumable=True)` — it auto-resumes |

---

## 13. Environment Variables

```bash
# ~/.amir/config.yaml or .env
ELEVENLABS_API_KEY=...
OPENAI_API_KEY=...
PEXELS_API_KEY=...       # free tier: 200 req/hour
ANTHROPIC_API_KEY=...    # for script + metadata generation
# YouTube credentials: client_secrets.json (OAuth) — never commit to git
```
