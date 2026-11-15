"""Cut the scenes together with ffmpeg: 1080x1920, voiceover, burned-in captions."""
import os
import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 30
FONT = "Arial" if os.name == "nt" else "DejaVu Sans"

ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Cap,{FONT},92,&H00FFFFFF,&H00000000,&H80000000,-1,1,7,2,5,90,90,0

[Events]
Format: Layer, Start, End, Style, Text
"""


def _run(args, cwd=None):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       cwd=cwd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-1500:]}")


def duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def _ts(t: float) -> str:
    cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def captions(words, per_line: int = 3) -> str:
    """words: [(start, end, word)] on the final timeline. Short chunks read best on a phone."""
    lines = []
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        end = words[i + per_line][0] if i + per_line < len(words) else chunk[-1][1] + 0.25
        text = " ".join(w for _, _, w in chunk).upper()
        text = text.replace("\\", "").replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_ts(chunk[0][0])},{_ts(max(end, chunk[0][0] + 0.2))},Cap,{text}")
    return ASS_HEAD + "\n".join(lines) + "\n"


def _segment(clip, audio, seconds: float, dest: Path):
    if clip:
        video_in = ["-stream_loop", "-1", "-i", str(clip)]
    else:
        video_in = ["-f", "lavfi", "-i", f"color=c=0x16213e:s={W}x{H}:r={FPS}"]
    audio_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={FPS},setsar=1,format=yuv420p")
    _run([*video_in, *audio_in, "-t", f"{seconds:.3f}", "-map", "0:v:0", "-map", "1:a:0",
          "-vf", vf, "-af", "aresample=44100,apad", "-ac", "2",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          "-c:a", "aac", "-b:a", "160k", str(dest)])


def render(scenes, workdir: Path, dest: Path) -> Path:
    """scenes: [{"clip": path|None, "audio": path|None, "words": [(start, end, word)]}]"""
    workdir.mkdir(parents=True, exist_ok=True)
    timeline, offset, names = [], 0.0, []
    for i, scene in enumerate(scenes):
        spoken = duration(scene["audio"]) if scene["audio"] else scene["words"][-1][1]
        seconds = spoken + 0.3
        seg = workdir / f"seg{i}.mp4"
        _segment(scene["clip"], scene["audio"], seconds, seg)
        timeline += [(s + offset, e + offset, w) for s, e, w in scene["words"]]
        offset += duration(seg)  # measured, so captions cannot drift from the picture
        names.append(seg.name)
    (workdir / "list.txt").write_text("".join(f"file '{n}'\n" for n in names))
    (workdir / "subs.ass").write_text(captions(timeline))
    # 3.5 Mbit/s keeps a 30 s video near 14 MB: inside what a Telegram bot may download again
    _run(["-f", "concat", "-safe", "0", "-i", "list.txt", "-vf", "ass=subs.ass",
          "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-maxrate", "3500k",
          "-bufsize", "7000k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
          "-movflags", "+faststart", str(dest.resolve())], cwd=workdir)
    return dest
