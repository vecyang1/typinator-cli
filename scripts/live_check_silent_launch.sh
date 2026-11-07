#!/bin/bash
# Live check (T-008 / D-005): CLI launches of Typinator must show no main window
# and must not move focus. Unit tests pin the launch argv; only this script
# proves the override still works against the installed Typinator (a future
# version could rename the "Open Window at Start" key and the unit tests would
# stay green).
#
# Disruptive: restarts Typinator twice (about 2 s each without expansions).
# Run by hand on the Mac: scripts/live_check_silent_launch.sh
# Exit 0 = silent, 1 = window appeared or focus moved, 2 = could not run.
set -u

TYPINATOR="${TYPINATOR_BIN:-typinator}"
command -v "$TYPINATOR" >/dev/null || { echo "cannot run: '$TYPINATOR' not on PATH" >&2; exit 2; }
python3 -c "import Quartz" 2>/dev/null || { echo "cannot run: python3 has no Quartz (pyobjc)" >&2; exit 2; }

main_window_width() {
  python3 -c "
import Quartz
w = [int(x['kCGWindowBounds']['Width']) for x in Quartz.CGWindowListCopyWindowInfo(
    Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
    if x.get('kCGWindowOwnerName') == 'Typinator' and x.get('kCGWindowLayer') == 0]
print(w[0] if w else 'none')"
}
front() { osascript -e 'tell application "System Events" to name of first application process whose frontmost is true'; }
close_main_window() {
  osascript -e 'tell application "System Events" to tell application process "Typinator" to if exists window "Typinator" then perform action "AXPress" of (first button of window "Typinator" whose subrole is "AXCloseButton")' >/dev/null 2>&1
}

failures=0
check() {  # label, frontmost-before
  sleep 2.5
  local after win
  after="$(front)"; win="$(main_window_width)"
  if [[ "$win" != "none" || "$after" != "$2" ]]; then
    echo "FAIL  $1: main window=$win, frontmost $2 -> $after"; failures=$((failures + 1))
  else
    echo "ok    $1: no main window, frontmost unchanged ($after)"
  fi
}

close_main_window; sleep 0.5
[[ "$(main_window_width)" == "none" ]] || { echo "cannot run: Typinator main window is open and could not be closed" >&2; exit 2; }

b="$(front)"; "$TYPINATOR" restart --json >/dev/null || { echo "cannot run: typinator restart failed" >&2; exit 2; }
check "typinator restart" "$b"
close_main_window

osascript -e 'tell application "Typinator" to quit' >/dev/null 2>&1
for _ in $(seq 1 20); do pgrep -x Typinator >/dev/null || break; sleep 0.25; done
pgrep -x Typinator >/dev/null && { echo "cannot run: Typinator did not quit" >&2; exit 2; }
b="$(front)"; "$TYPINATOR" list-sets >/dev/null || { echo "cannot run: list-sets failed while Typinator was quit" >&2; exit 2; }
pgrep -x Typinator >/dev/null || { echo "FAIL  rule command while quit: Typinator not running afterwards"; exit 1; }
check "rule command while Typinator was quit" "$b"
close_main_window

echo "saved 'Open Window at Start' preference (left untouched): $(defaults read com.macility.typinator2 'Open Window at Start' 2>/dev/null || echo unset)"
[[ $failures -eq 0 ]] && exit 0 || exit 1
