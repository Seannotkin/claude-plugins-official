"""Minimal Telegram Bot API client. Only the configured chat can talk to the bot."""
import json

import requests

from .config import secret

BUTTONS = {"inline_keyboard": [[
    {"text": "✅ Post it", "callback_data": "approve"},
    {"text": "🔁 Redo", "callback_data": "redo"},
    {"text": "❌ Drop", "callback_data": "reject"},
]]}


def call(method: str, files=None, timeout=60, **params):
    url = f"https://api.telegram.org/bot{secret('TELEGRAM_BOT_TOKEN')}/{method}"
    if "long_poll" in params:
        params["timeout"] = params.pop("long_poll")
    data = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in params.items()}
    r = requests.post(url, data=data, files=files, timeout=timeout)
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method}: {body.get('description')}")
    return body["result"]


def chat_id() -> str:
    return secret("TELEGRAM_CHAT_ID")


def say(text: str):
    return call("sendMessage", chat_id=chat_id(), text=text[:4000])


def send_for_approval(video_path, caption: str):
    with open(video_path, "rb") as f:
        return call("sendVideo", files={"video": ("reel.mp4", f, "video/mp4")}, timeout=300,
                    chat_id=chat_id(), caption=caption, supports_streaming="true",
                    reply_markup=BUTTONS)


def updates(offset: int, wait: int = 0):
    # `timeout` here is Telegram's long-poll time; the HTTP timeout sits above it
    return call("getUpdates", timeout=wait + 30, offset=offset, limit=50,
                allowed_updates=["message", "callback_query"], long_poll=wait)


def download(file_id: str, dest):
    info = call("getFile", file_id=file_id)
    url = f"https://api.telegram.org/file/bot{secret('TELEGRAM_BOT_TOKEN')}/{info['file_path']}"
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as out:
            for chunk in r.iter_content(1 << 20):
                out.write(chunk)
    return dest
