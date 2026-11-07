#!/usr/bin/env bash
# Video v2 script: hero page → live run → dependencies → settings → release line → evidence →
# GitHub → close. Nine beats, timed to the audio.
#
#   bash tools/make-video-v2.sh [base-url] [voice] [name] [captions: off|small|full]
set -uo pipefail
BASE="${1:-http://45.77.143.94}"
VOICE="${2:-fr-FR-VivienneMultilingualNeural}"
NAME="${3:-demo-v7}"
SUBS="${4:-off}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
V="$HERE/recordings/voice"; OUT="$HERE/recordings"
FF="$("$HERE/.venv/bin/python" -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')"

echo "== 1/4 voice"
"$HERE/.venv/bin/python" "$HERE/tools/build-voiceover.py" --voice "$VOICE" || exit 2
H=(); while IFS= read -r l; do H+=("$l"); done < "$V/holds.txt"
"$HERE/.venv/bin/python" - "$V/holds.txt" > "$V/holds_adj.txt" <<'PY'
import sys
h = [float(x) for x in open(sys.argv[1]).read().split()]
print("\n".join(f"{v:.2f}" for v in [h[0]] + [max(1.5, x - 0.34) for x in h[1:]]))
PY
A=(); while IFS= read -r l; do A+=("$l"); done < "$V/holds_adj.txt"
TOTAL=$("$HERE/.venv/bin/python" -c "print(sum(float(x) for x in open('$V/holds.txt')))")

rid() { curl -s "$BASE/runs?limit=20" | "$HERE/.venv/bin/python" -c "
import json,sys
w=sys.argv[1]; r=json.load(sys.stdin)['runs']
print(next((x['id'] for x in r if w in ((x.get('task') or {}).get('package') or '')), ''))" "$1"; }
R291="$(rid harborline-2.9.1)"; R290="$(rid harborline-2.9.0)"; R280="$(rid harborline-2.8.0)"
[ -n "$R291" ] || { echo "no harborline runs on $BASE" >&2; exit 3; }

echo "== 2/4 browser prep"
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
nav "$BASE/hero.html" 4

echo "== 3/4 screen pass (${TOTAL}s)"
rm -f "$OUT/demo-raw-v2.mov"
screencapture -v -V "$("$HERE/.venv/bin/python" -c "print(int($TOTAL)+3)")" "$OUT/demo-raw-v2.mov" &
REC=$!
sleep 1
nav "$BASE/hero.html" "${A[0]}"
nav "$BASE/?theme=dark" "${A[1]}"
nav "$BASE/?run=$R291&theme=dark" "${A[2]}"
nav "$BASE/?run=$R291&tab=deps&theme=dark" "${A[3]}"
nav "$BASE/?settings=1" "${A[4]}"
nav "$BASE/?run=$R290&theme=dark" "8"
nav "$BASE/?run=$R280&theme=dark" "7.7"
nav "$BASE/?run=$R291&tab=evidence&theme=dark" "${A[6]}"
nav "https://github.com/derKosi/agent-rush" "${A[7]}"
nav "$BASE/hero.html" "${A[8]}"
wait $REC 2>/dev/null

echo "== 4/4 encode + mux"
"$FF" -y -loglevel error -i "$OUT/demo-raw-v2.mov" -vf "crop=2880:1524:0:136,scale=1440:-2" \
  -c:v libx264 -crf 20 -preset veryfast -an "$OUT/demo-video-v2.mp4"
"$FF" -y -loglevel error -f lavfi -i anullsrc=r=24000:cl=mono -t 0.8 "$V/sil.mp3"
: > "$V/list.txt"
for i in 1 2 3 4 5 6 7 8 9; do
  echo "file '$V/beat-$i.mp3'" >> "$V/list.txt"; echo "file '$V/sil.mp3'" >> "$V/list.txt"
done
"$FF" -y -loglevel error -f concat -safe 0 -i "$V/list.txt" -c:a libmp3lame -q:a 4 "$V/voiceover-v2.mp3"
"$HERE/.venv/bin/python" "$HERE/tools/make-subtitles.py" >/dev/null || true
case "$SUBS" in
  full)  STYLE="FontName=Arial,FontSize=19,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=36" ;;
  small) STYLE="FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0,MarginV=16" ;;
  *)     STYLE="" ;;
esac
if [ -n "$STYLE" ]; then
  "$FF" -y -loglevel error -i "$OUT/demo-video-v2.mp4" -i "$V/voiceover-v2.mp3" \
    -vf "subtitles=$V/subs.srt:force_style='$STYLE'" -c:v libx264 -crf 20 -preset veryfast \
    -c:a aac -b:a 128k -shortest "$OUT/$NAME.mp4"
else
  "$FF" -y -loglevel error -i "$OUT/demo-video-v2.mp4" -i "$V/voiceover-v2.mp3" \
    -c:v copy -c:a aac -b:a 128k -shortest "$OUT/$NAME.mp4"
fi
"$FF" -hide_banner -i "$OUT/$NAME.mp4" 2>&1 | grep -E "Duration|Stream" | head -3
echo "wrote $OUT/$NAME.mp4"
