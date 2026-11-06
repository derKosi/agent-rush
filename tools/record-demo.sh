#!/usr/bin/env bash
# Records the demo pass, timed to docs/transcript.md (2:32 of narration, silent video).
#
#   bash tools/record-demo.sh [base-url]
#
# Needs: Safari logged into nothing, one window, screen-recording permission for this process,
# and a built .venv with imageio-ffmpeg (pip install imageio-ffmpeg).
#
# The beats follow the transcript. If you change the words, change the holds.
set -uo pipefail

BASE="${1:-http://45.77.143.94}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/recordings"
FF="$("$HERE/.venv/bin/python" -c 'import imageio_ffmpeg,sys; print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null)"
mkdir -p "$OUT"

rid() {
  curl -s "$BASE/runs?limit=20" | "$HERE/.venv/bin/python" -c "
import json,sys
want=sys.argv[1]
runs=json.load(sys.stdin)['runs']
print(next((r['id'] for r in runs if want in ((r.get('task') or {}).get('package') or '')), ''))" "$1"
}

R291="$(rid harborline-2.9.1)"
R290="$(rid harborline-2.9.0)"
R280="$(rid harborline-2.8.0)"
[ -n "$R291" ] || { echo "no harbourline runs on $BASE — seed first" >&2; exit 2; }

nav() { osascript -e "tell application \"Safari\" to set URL of front document to \"$1\"" >/dev/null; sleep "$2"; }

# One tab, frontmost, fixed geometry. Tab bars and docks have ruined two takes.
osascript <<'EOS' >/dev/null
tell application "Safari"
  repeat with i from (count of windows) to 2 by -1
    close window i
  end repeat
  tell front window
    set current tab to tab 1
    repeat with i from (count of tabs) to 2 by -1
      close tab i
    end repeat
  end tell
  set bounds of front window to {0, 25, 1440, 925}
  activate
end tell
EOS
sleep 2
nav "$BASE/?theme=dark&v=$(date +%s)" 4

rm -f "$OUT/demo-raw.mov"
echo "recording 155 s …"
screencapture -v -V 155 "$OUT/demo-raw.mov" &
REC=$!
sleep 1

nav "$BASE/?theme=dark" 6                                   # 0:00 five runs, one blocked
nav "$BASE/?run=$R291&theme=dark" 42                        # 0:06 the verdict, 42 s of narration
nav "$BASE/?run=$R291&tab=deps&theme=dark" 27               # 0:48 the dependency that blocks
nav "$BASE/?run=$R290&theme=dark" 12                        # 1:15 the release before
nav "$BASE/?run=$R280&theme=dark" 11                        #        and the one before that
nav "$BASE/?run=$R291&tab=evidence&theme=dark" 27           # 1:38 every claim has a file
nav "$BASE/?theme=dark" 20                                  # 2:05 close on the rail
wait $REC 2>/dev/null

# Crop the browser chrome and the dock; odd heights kill libx264.
"$FF" -y -loglevel error -i "$OUT/demo-raw.mov" \
  -vf "crop=2880:1470:0:190,scale=1440:-2" -c:v libx264 -crf 20 -preset veryfast -an "$OUT/demo.mp4"
echo "wrote $OUT/demo.mp4"
"$FF" -hide_banner -i "$OUT/demo.mp4" 2>&1 | grep Duration
