"""Make a video, send it to Telegram for approval, and act on what the owner answers."""
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import footage, instagram, render, script, voice
from . import telegram as tg
from .config import OUT, dry_run, save_state

HELP = """I make short videos for your Instagram and post them only after you approve.

• Send me any message — I turn it into a video.
• /new — make a video on a topic I choose
• /niche <text> — set what the account is about
• /pause — stop making videos (when you need your PC); /resume — start again
• /status — see whether I am paused
• Under each video: ✅ Post it · 🔁 Redo · ❌ Drop
• Reply to a video with what to change and I remake it.
• Reply to a video with "caption: <new text>" to change only the caption."""


def make_video(plan: dict, cfg: dict) -> Path:
    work = OUT / f"job-{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)
    scenes, used = [], set()
    for i, sc in enumerate(plan["scenes"]):
        audio, words = voice.speak(sc["text"], cfg["voice"], work / f"voice{i}.mp3")
        clip = footage.get_clip(sc["footage"], work / f"clip{i}.mp4", used)
        scenes.append({"clip": clip, "audio": audio, "words": words})
    final = render.render(scenes, work, OUT / f"{work.name}.mp4")
    shutil.rmtree(work, ignore_errors=True)
    return final


def generate(state: dict, cfg: dict, brief=None, feedback=None):
    if state.get("paused"):
        tg.say("⏸ I'm paused, so I didn't make that video. Send /resume when your PC is free.")
        return
    niche = state.get("niche") or cfg.get("niche")
    if not niche:
        tg.say("Tell me what the account is about first:\n/niche <your topic and audience>")
        return
    tg.say("🎬 Making a video, this takes a couple of minutes…")
    plan = script.make_plan(niche, cfg["language"], cfg["video"], state["history"], brief, feedback)
    video = make_video(plan, cfg)
    tg.send_for_approval(video, script.full_caption(plan))
    video.unlink(missing_ok=True)  # Telegram keeps the copy we publish from
    state["history"].append(plan["title"])
    save_state(state)


def _approve(message: dict):
    OUT.mkdir(exist_ok=True)
    path = tg.download(message["video"]["file_id"], OUT / f"approved-{message['message_id']}.mp4")
    try:
        if dry_run():
            tg.say("✅ Approved. (DRY_RUN is on, so nothing was posted.)")
        else:
            tg.say("⏫ Posting to Instagram…")
            tg.say(f"✅ Posted: {instagram.publish_reel(path, message.get('caption', ''))}")
    finally:
        path.unlink(missing_ok=True)


def _buttons(message: dict, on: bool):
    tg.call("editMessageReplyMarkup", chat_id=message["chat"]["id"],
            message_id=message["message_id"],
            reply_markup=tg.BUTTONS if on else {"inline_keyboard": []})


def handle(update: dict, state: dict, cfg: dict):
    if "callback_query" in update:
        cq = update["callback_query"]
        message = cq.get("message") or {}
        if str(message.get("chat", {}).get("id")) != tg.chat_id() or "video" not in message:
            return
        tg.call("answerCallbackQuery", callback_query_id=cq["id"])
        _buttons(message, False)  # first, so a second tap cannot post twice
        if cq["data"] == "approve":
            try:
                _approve(message)
            except Exception:
                _buttons(message, True)
                raise
        elif cq["data"] == "redo":
            generate(state, cfg, feedback="Make a different, stronger video than the last one.")
        else:
            tg.say("❌ Dropped.")
        return

    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    if str(message.get("chat", {}).get("id")) != tg.chat_id() or not text:
        return
    command, _, rest = text.partition(" ")
    rest = rest.strip()
    replied = message.get("reply_to_message") or {}
    if command in ("/start", "/help"):
        tg.say(HELP)
    elif command == "/niche":
        if rest:
            state["niche"] = rest
            save_state(state)
            tg.say(f"Niche set: {rest}\nSend /new for the first video.")
        else:
            tg.say(f"Current niche: {state.get('niche') or cfg.get('niche') or '(not set)'}")
    elif command in ("/pause", "/resume"):
        state["paused"] = command == "/pause"
        save_state(state)
        tg.say("⏸ Paused. I won't make any videos until you send /resume. "
               "You can still approve videos I already sent." if state["paused"]
               else "▶️ Resumed. Scheduled videos are back on; send /new for one now.")
    elif command == "/status":
        tg.say(("⏸ Paused." if state.get("paused") else "▶️ Running.")
               + f"\nNiche: {state.get('niche') or cfg.get('niche') or '(not set)'}"
               + f"\nDaily videos at (UTC hours): {cfg.get('slots_utc', [])}")
    elif command == "/new":
        generate(state, cfg, brief=rest or None)
    elif "video" in replied and text.lower().startswith("caption:"):
        tg.call("editMessageCaption", chat_id=replied["chat"]["id"],
                message_id=replied["message_id"], caption=text[8:].strip()[:1000],
                reply_markup=tg.BUTTONS)
        tg.say("Caption updated.")
    elif "video" in replied:
        _buttons(replied, False)
        generate(state, cfg, feedback=f"{text}\n(Caption of the rejected video: "
                                      f"{replied.get('caption', '')[:300]})")
    elif not command.startswith("/"):
        generate(state, cfg, brief=text)
    else:
        tg.say(HELP)


def tick(state: dict, cfg: dict, wait: int = 0, now=None):
    """One round: answer Telegram, then make the scheduled video if one is due."""
    for update in tg.updates(state["offset"], wait):
        state["offset"] = update["update_id"] + 1
        save_state(state)  # before acting: a crash must never replay an approval
        try:
            handle(update, state, cfg)
        except Exception as e:
            traceback.print_exc()
            tg.say(f"⚠️ That failed: {e}")

    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    due = sum(1 for hour in cfg.get("slots_utc", []) if now.hour >= hour)
    if state["auto"].get(day, 0) < due:
        state["auto"][day] = due  # missed slots are skipped, not sent in a burst
        save_state(state)
        if state.get("paused"):
            return  # the slot is used up, so resuming does not start a render by surprise
        try:
            generate(state, cfg)
        except Exception as e:
            traceback.print_exc()
            tg.say(f"⚠️ The scheduled video failed: {e}")
