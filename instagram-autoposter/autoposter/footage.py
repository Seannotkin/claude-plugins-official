"""Background clip for a scene: your own clips in footage/ first, then Pexels stock video."""
import os
import random
from pathlib import Path

import requests

from .config import ROOT

LOCAL = ROOT / "footage"


def _pexels(query: str, dest: Path, used: set):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": key},
        params={"query": query, "orientation": "portrait", "per_page": 15},
        timeout=30,
    )
    r.raise_for_status()
    videos = [v for v in r.json().get("videos", []) if v["id"] not in used and v["duration"] >= 4]
    if not videos:
        return None
    video = random.choice(videos[:6])
    used.add(video["id"])
    files = [f for f in video["video_files"] if f.get("file_type") == "video/mp4" and f.get("height")]
    # smallest file that is still at least 1280 tall, else the tallest there is
    tall = sorted((f for f in files if f["height"] >= 1280), key=lambda f: f["height"])
    best = tall[0] if tall else max(files, key=lambda f: f["height"])
    with requests.get(best["link"], stream=True, timeout=120) as dl:
        dl.raise_for_status()
        with open(dest, "wb") as out:
            for chunk in dl.iter_content(1 << 20):
                out.write(chunk)
    return dest


def get_clip(query: str, dest: Path, used: set):
    """Returns a video path, or None (the renderer then uses a plain background)."""
    local = sorted(LOCAL.glob("*.mp4")) if LOCAL.exists() else []
    if local:
        return random.choice(local)
    try:
        return _pexels(query, dest, used)
    except requests.RequestException as e:
        print(f"footage: '{query}' failed: {e}")
        return None
