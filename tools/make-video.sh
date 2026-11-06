#!/usr/bin/env bash
# Video v1: voice-over first, then the screen pass timed to it, then mux.
#
#   bash tools/make-video.sh [base-url] [voice]
#
# Why this order: the audio decides the pace. Building the visuals first and stretching the
# voice afterwards is how you get a video that talks about dependencies while showing a
# dashboard.
set -uo pipefail
BASE="${1:-http://45.77.143.94}"
VOICE="${2:-en-US-AndrewNeural}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
V="$HERE/recordings/voice"
OUT="$HERE/recordings"
FF="$("$HERE/.venv/bin/python" -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"

echo "== 1/4 voice"
"$HERE/.venv/bin/python" "$HERE/tools/build-voiceover.py" --voice "$VOICE" || exit 2
H=()
while IFS= read -r line; do H+=("$line"); done < "$V/holds.txt"
TOTAL=$("$HERE/.venv/bin/python" -c "print(sum(float(x) for x in open('$V/holds.txt')))")

rid() { curl -s "$BASE/runs?limit=20" | "$HERE/.venv/bin/python" -c "
import json,sys
w=sys.argv[1]; r=json.load(sys.stdin)['runs']
print(next((x['id'] for x in r if w in ((x.get('task') or {}).get('package') or '')), ''))" "$1"; }
R291="$(rid harborline-2.9.1)"; R290="$(rid harborline-2.9.0)"; R280="$(rid harborline-2.8.0)"
[ -n "$R291" ] || { echo "no harborline runs on $BASE" >&2; exit 3; }

echo "== 2/4 clean slate in the browser"
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
nav() { osascript -e "tell application \"Safari\" to set URL of front document to \"$1\"" >/dev/null; sleep "$2"; }
nav "$BASE/?theme=dark&v=$(date +%s)" 3

echo "== 3/4 screen pass (${TOTAL}s of narration)"
rm -f "$OUT/demo-raw.mov"
screencapture -v -V "$("$HERE/.venv/bin/python" -c "print(int($TOTAL)+3)")" "$OUT/demo-raw.mov" &
REC=$!
sleep 1
nav "$BASE/?theme=dark" "${H[0]}"
nav "$BASE/?run=$R291&theme=dark" "${H[1]}"
nav "$BASE/?run=$R291&theme=dark&t=2" "${H[2]}"
nav "$BASE/?run=$R291&tab=deps&theme=dark" "${H[3]}"
nav "$BASE/?run=$R290&theme=dark" "9"
nav "$BASE/?run=$R280&theme=dark" "6.5"
nav "$BASE/?run=$R291&tab=evidence&theme=dark" "${H[5]}"
nav "$BASE/?run=$R291&theme=dark" "${H[6]}"
nav "$BASE/?theme=dark" "${H[7]}"
wait $REC 2>/dev/null

echo "== 4/4 mux"
"$FF" -y -loglevel error -i "$OUT/demo-raw.mov" -vf "crop=2880:1462:0:198,scale=1440:-2" \
  -c:v libx264 -crf 20 -preset veryfast -an "$OUT/demo-video.mp4"
"$FF" -y -loglevel error -f lavfi -i anullsrc=r=24000:cl=mono -t 0.8 "$V/sil.mp3"
: > "$V/list.txt"
for i in 1 2 3 4 5 6 7 8; do
  echo "file '$V/beat-$i.mp3'" >> "$V/list.txt"
  echo "file '$V/sil.mp3'" >> "$V/list.txt"
done
"$FF" -y -loglevel error -f concat -safe 0 -i "$V/list.txt" -c:a libmp3lame -q:a 4 "$V/voiceover.mp3"
"$FF" -y -loglevel error -i "$OUT/demo-video.mp4" -i "$V/voiceover.mp3" \
  -c:v copy -c:a aac -b:a 128k -shortest "$OUT/demo-v1.mp4"
"$FF" -hide_banner -i "$OUT/demo-v1.mp4" 2>&1 | grep -E "Duration|Stream"
echo "wrote $OUT/demo-v1.mp4"
