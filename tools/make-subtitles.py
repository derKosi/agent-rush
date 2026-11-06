#!/usr/bin/env python3
"""Build an SRT from the transcript beats and the measured hold times.

    .venv/bin/python tools/make-subtitles.py

The audio timeline is the truth: beat n starts at the sum of the previous (beat + gap) and
lasts its own duration. Cues therefore line up with the voice, not with the screen pass.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VOICE = REPO / "recordings" / "voice"
GAP = 0.8
MAX_CHARS = 46


def beats():
    text = (REPO / "docs" / "transcript.md").read_text(encoding="utf-8")
    english = text.split("## Timing check")[0]
    blocks = re.split(r"^\*\*\d+:\d\d[^\n]*\*\*$", english, flags=re.MULTILINE)[1:]
    out = []
    for block in blocks:
        spoken = [line[2:].strip() for line in block.splitlines() if line.startswith("> ")]
        if spoken:
            out.append(" ".join(spoken))
    return out


def wrap(text):
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > MAX_CHARS and line:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return "\n".join(lines).replace("`", "")


def stamp(seconds):
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def main() -> int:
    holds = [float(x) for x in (VOICE / "holds.txt").read_text().split()]
    parts = beats()
    if len(parts) != len(holds):
        print(f"{len(parts)} beats but {len(holds)} holds", file=sys.stderr)
        return 2

    cues, t = [], 0.0
    for index, (text, hold) in enumerate(zip(parts, holds), start=1):
        duration = max(1.5, hold - GAP)
        cues.append(f"{index}\n{stamp(t)} --> {stamp(t + duration)}\n{wrap(text)}\n")
        t += hold

    (VOICE / "subs.srt").write_text("\n".join(cues), encoding="utf-8")
    print(f"wrote {VOICE / 'subs.srt'} — {len(cues)} cues, {t:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
