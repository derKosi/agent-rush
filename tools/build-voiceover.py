#!/usr/bin/env python3
"""Turn docs/transcript.md into per-beat audio files and a timing plan.

    .venv/bin/python tools/build-voiceover.py [--voice en-US-AndrewNeural]

Writes recordings/voice/beat-<n>.mp3 and recordings/voice/holds.txt (one duration per line,
already including the gap). The recording script reads holds.txt, so the visuals follow the
voice instead of the other way round.
"""

import argparse
import asyncio
import re
import time
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRANSCRIPT = REPO / "docs" / "transcript.md"
OUT = REPO / "recordings" / "voice"
GAP = 0.8


def beats():
    """One block per **0:00 — ...** marker; the spoken lines are the '> ' lines inside it."""
    text = TRANSCRIPT.read_text(encoding="utf-8")
    english = text.split("## Timing check")[0]
    blocks = re.split(r"^\*\*(\d+):\d\d[^\n]*\*\*$", english, flags=re.MULTILINE)[1:]
    out = []
    for block in blocks:
        spoken = [line[2:].strip() for line in block.splitlines() if line.startswith("> ")]
        if spoken:
            out.append(" ".join(spoken).strip())
    return out


async def render(text, voice, path):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(path))


def duration(path):
    ff = subprocess.run([str(Path(sys.executable).with_name("python")), "-c",
                         "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                        capture_output=True, text=True)
    exe = ff.stdout.strip()
    probe = subprocess.run([exe, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if not match:
        return None
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="en-US-AndrewNeural")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    parts = beats()
    if not parts:
        print("no beats found — check the transcript markers", file=sys.stderr)
        return 2

    holds = []
    for index, text in enumerate(parts, start=1):
        path = OUT / f"beat-{index}.mp3"
        # The unauthenticated endpoint throttles bursts; a pause and two retries beat a
        # hard failure halfway through a voice-over.
        for attempt in range(3):
            try:
                asyncio.run(render(text, args.voice, path))
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    print(f"beat {index} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                    return 4
                time.sleep(3)
        time.sleep(1.5)
        length = duration(path)
        if length is None:
            print(f"could not read duration of {path}", file=sys.stderr)
            return 3
        holds.append(length + GAP)
        print(f"beat {index}: {len(text.split()):3} words  {length:5.1f}s  (+{GAP}s)  {text[:60]}…")

    (OUT / "holds.txt").write_text("\n".join(f"{h:.2f}" for h in holds) + "\n", encoding="utf-8")
    total = sum(holds)
    print(f"\ntotal video: {total:.1f}s ({int(total // 60)}:{total % 60:04.1f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
