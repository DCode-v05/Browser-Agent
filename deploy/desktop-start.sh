#!/bin/sh
set -eu
Xvfb "$DISPLAY" -screen 0 "${SCREEN:-1280x800}x24" -nolisten tcp &
tries=0
until xdpyinfo >/dev/null 2>&1; do
  tries=$((tries + 1))
  [ "$tries" -gt 100 ] && exit 1
  sleep 0.1
done
dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --fork --nopidfile
openbox &
sleep 0.5
xsetroot -solid "#3a5a78"
if [ "${WHILE_INPUT:-}" = 1 ]; then
  cat >/dev/null
  exit 0
fi
wait
