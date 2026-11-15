"""Publish a Reel with the official Instagram Graph API (resumable upload, no public URL needed)."""
import os
import time
from pathlib import Path

import requests

from .config import secret


def _base() -> str:
    return f"https://graph.facebook.com/{os.environ.get('GRAPH_API_VERSION', 'v23.0')}"


def _check(r):
    body = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in body:
        msg = body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else r.text
        raise RuntimeError(f"Instagram API: {msg}")
    return body


def publish_reel(video: Path, caption: str) -> str:
    """Uploads and publishes. Returns the permalink of the new Reel."""
    token, user = secret("IG_ACCESS_TOKEN"), secret("IG_USER_ID")
    auth = {"Authorization": f"Bearer {token}"}

    container = _check(requests.post(f"{_base()}/{user}/media", headers=auth, timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true"}))
    upload_url = container.get("uri") or (
        f"https://rupload.facebook.com/ig-api-upload/{os.environ.get('GRAPH_API_VERSION', 'v23.0')}"
        f"/{container['id']}")
    size = video.stat().st_size
    with open(video, "rb") as f:
        _check(requests.post(upload_url, data=f, timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}))

    for _ in range(60):  # Instagram processes the video before it can be published
        status = _check(requests.get(f"{_base()}/{container['id']}", headers=auth, timeout=60,
                                     params={"fields": "status_code,status"}))
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram rejected the video: {status.get('status')}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram is still processing the video after 5 minutes")

    media = _check(requests.post(f"{_base()}/{user}/media_publish", headers=auth, timeout=60,
                                 data={"creation_id": container["id"]}))
    link = _check(requests.get(f"{_base()}/{media['id']}", headers=auth, timeout=60,
                               params={"fields": "permalink"}))
    return link.get("permalink", media["id"])
