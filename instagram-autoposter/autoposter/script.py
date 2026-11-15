"""Ask Claude for the video plan: scenes to narrate, footage to search for, caption."""
import json
import os

import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "scenes", "caption", "hashtags"],
    "properties": {
        "title": {"type": "string", "description": "Short internal title of the idea"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "footage"],
                "properties": {
                    "text": {"type": "string", "description": "Words spoken and shown in this scene"},
                    "footage": {"type": "string", "description": "2-4 word stock video search, concrete and visual"},
                },
            },
        },
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = """You write short vertical videos (Instagram Reels) that are built automatically from \
stock footage, a voiceover and on-screen captions.

What makes these videos travel:
- The first scene is the hook: one sentence under 10 words that creates curiosity or names a \
problem the viewer has. No greetings, no "did you know".
- Every scene earns the next one. One idea per video. Plain spoken words, short sentences.
- The last scene pays off the hook and ends on a line worth sharing or saving, or loops back \
into the hook so the video rewatches well.
- Only say things that are true. No invented statistics, quotes, or medical/financial promises.

The footage search for each scene must be something a stock library actually has (a concrete \
subject or action), never an abstract concept.

The caption adds context the video doesn't say, in at most 500 characters, and ends with a \
question that invites comments. Give 5 to 8 specific hashtags, each starting with #."""


def make_plan(niche, language, cfg_video, history, brief=None, feedback=None) -> dict:
    words = int(cfg_video["max_seconds"] * 2.5)
    ask = [
        f"Account niche: {niche}",
        f"Language: {language}",
        f"Length: {cfg_video['scenes']} scenes, at most {words} spoken words in total.",
    ]
    if history:
        ask.append("Already made, pick a clearly different idea:\n- " + "\n- ".join(history[-30:]))
    if brief:
        ask.append(f"The account owner asked for this video specifically: {brief}")
    if feedback:
        ask.append(f"The owner rejected the previous attempt with this feedback, apply it: {feedback}")

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": "\n\n".join(ask)}],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"Claude did not finish the script (stop_reason={response.stop_reason})")
    plan = json.loads(next(b.text for b in response.content if b.type == "text"))
    plan["scenes"] = [s for s in plan["scenes"] if s["text"].strip()]
    if not plan["scenes"]:
        raise RuntimeError("Claude returned a script with no scenes")
    return plan


def full_caption(plan: dict) -> str:
    return (plan["caption"].strip() + "\n\n" + " ".join(plan["hashtags"])).strip()[:1000]
