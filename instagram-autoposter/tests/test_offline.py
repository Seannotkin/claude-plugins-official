"""Offline end-to-end test: real ffmpeg render, fake Claude / Telegram / Instagram."""
import subprocess
from datetime import datetime, timezone

import pytest

from autoposter import config, footage, instagram, pipeline, render, script
from autoposter import telegram as tg

CFG = {"language": "English", "slots_utc": [15], "video": {"max_seconds": 25, "scenes": 2},
       "voice": {"provider": "none"}}
PLAN = {"title": "Morning light", "caption": "Why light matters. Do you get outside early?",
        "hashtags": ["#sleep", "#habits"],
        "scenes": [{"text": "Your phone is not why you are tired", "footage": "sunrise window"},
                   {"text": "Ten minutes of {morning} light resets your body clock", "footage": "walk"}]}


class FakeTelegram:
    def __init__(self):
        self.calls, self.queue, self.sent_video = [], [], None

    def call(self, method, files=None, timeout=60, **params):
        self.calls.append((method, params))
        if method == "getUpdates":
            out, self.queue = self.queue, []
            return out
        if method == "sendVideo":
            self.sent_video = files["video"][1].read()
        return {"message_id": 7}

    def texts(self):
        return [p["text"] for m, p in self.calls if m == "sendMessage"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=s=640x360:r=25:d=1", "-pix_fmt", "yuv420p", str(clip)], check=True)
    fake, posted = FakeTelegram(), []
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.setattr(config, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(pipeline, "OUT", tmp_path / "out")
    monkeypatch.setattr(tg, "call", fake.call)
    monkeypatch.setattr(tg, "download", lambda fid, dest: dest.write_bytes(b"video") and dest)
    monkeypatch.setattr(script, "make_plan", lambda *a, **k: PLAN)
    monkeypatch.setattr(footage, "get_clip", lambda q, d, u: clip)
    monkeypatch.setattr(instagram, "publish_reel",
                        lambda path, caption: posted.append(caption) or "https://instagram.com/reel/x")
    return fake, posted, config.load_state()


def msg(text, chat=42, **extra):
    return {"update_id": 1, "message": {"chat": {"id": chat}, "text": text, **extra}}


def tap(data, chat=42):
    return {"update_id": 2, "callback_query": {"id": "c", "data": data, "message": {
        "message_id": 7, "chat": {"id": chat}, "caption": "cap #tag", "video": {"file_id": "f"}}}}


def test_render_makes_vertical_video_with_sound(env, tmp_path):
    fake, _, state = env
    state["niche"] = "sleep"
    pipeline.generate(state, CFG)
    out = tmp_path / "v.mp4"
    out.write_bytes(fake.sent_video)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type,width,height", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True).stdout
    assert "video,1080,1920" in probe and "audio" in probe
    assert 4 < render.duration(out) < 25
    assert out.stat().st_size < 20 * 1024 * 1024
    send = next(p for m, p in fake.calls if m == "sendVideo")
    assert send["caption"].endswith("#sleep #habits") and send["reply_markup"] == tg.BUTTONS
    assert state["history"] == ["Morning light"]


def test_nothing_is_made_without_a_niche(env):
    fake, _, state = env
    pipeline.handle(msg("/new"), state, CFG)
    assert fake.sent_video is None and "/niche" in fake.texts()[0]


def test_approve_posts_once_and_only_for_the_owner(env):
    fake, posted, state = env
    pipeline.handle(tap("approve", chat=999), state, CFG)
    assert posted == []
    pipeline.handle(tap("approve"), state, CFG)
    assert posted == ["cap #tag"]
    methods = [m for m, _ in fake.calls]
    assert methods.index("editMessageReplyMarkup") < methods.index("sendMessage")
    assert "Posted" in fake.texts()[-1]


def test_reject_and_dry_run_do_not_post(env, monkeypatch):
    fake, posted, state = env
    pipeline.handle(tap("reject"), state, CFG)
    monkeypatch.setenv("DRY_RUN", "1")
    pipeline.handle(tap("approve"), state, CFG)
    assert posted == []


def test_failed_post_puts_the_buttons_back(env, monkeypatch):
    fake, _, state = env
    monkeypatch.setattr(instagram, "publish_reel", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        pipeline.handle(tap("approve"), state, CFG)
    marks = [p["reply_markup"] for m, p in fake.calls if m == "editMessageReplyMarkup"]
    assert marks[-1] == tg.BUTTONS


def test_caption_edit_and_niche(env):
    fake, _, state = env
    pipeline.handle(msg("/niche sleep tips"), state, CFG)
    assert config.load_state()["niche"] == "sleep tips"
    reply = {"reply_to_message": {"message_id": 7, "chat": {"id": 42}, "video": {}}}
    pipeline.handle(msg("caption: New words", **reply), state, CFG)
    edit = next(p for m, p in fake.calls if m == "editMessageCaption")
    assert edit["caption"] == "New words" and edit["reply_markup"] == tg.BUTTONS


def test_schedule_makes_one_video_per_slot(env):
    fake, _, state = env
    state["niche"] = "sleep"
    made = lambda: sum(1 for m, _ in fake.calls if m == "sendVideo")
    pipeline.tick(state, CFG, now=datetime(2026, 1, 1, 14, tzinfo=timezone.utc))
    assert made() == 0
    pipeline.tick(state, CFG, now=datetime(2026, 1, 1, 15, tzinfo=timezone.utc))
    pipeline.tick(state, CFG, now=datetime(2026, 1, 1, 18, tzinfo=timezone.utc))
    assert made() == 1


def test_updates_are_acknowledged_before_they_run(env):
    fake, posted, state = env
    fake.queue = [tap("approve")]
    pipeline.tick(state, CFG, now=datetime(2026, 1, 1, 1, tzinfo=timezone.utc))
    assert posted and config.load_state()["offset"] == 3
