"""Voiceover for one scene. Returns (audio path or None, [(start, end, word), ...])."""
import asyncio
from pathlib import Path


def estimate_words(text: str, rate: float = 2.6):
    """Timings when there is no voice: an even reading pace."""
    words, t, out = text.split(), 0.0, []
    for w in words:
        d = max(0.22, len(w) * 0.07) / (rate / 2.6)
        out.append((t, t + d, w))
        t += d
    return out


async def _edge(text, voice, rate, path):
    import edge_tts

    words = []
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    with open(path, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
    return words


def speak(text: str, cfg: dict, path: Path):
    if cfg.get("provider", "edge") == "none":
        return None, estimate_words(text)
    words = asyncio.run(_edge(text, cfg["name"], cfg.get("rate", "+0%"), path))
    return path, words or estimate_words(text)
