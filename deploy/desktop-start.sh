#!/bin/sh
# Starts the virtual screen and the window manager, and stays until the container is stopped.
# SCREEN is the screen's size as WIDTHxHEIGHT; whoever starts the container gives it.
set -eu
Xvfb "$DISPLAY" -screen 0 "${SCREEN:-1280x800}x24" -nolisten tcp &
tries=0
until xdpyinfo >/dev/null 2>&1; do
  tries=$((tries + 1))
  [ "$tries" -gt 100 ] && exit 1
  sleep 0.1
done
openbox &
# The window manager paints the background when it starts: the colour is set after it.
sleep 0.5
xsetroot -solid "#3a5a78"
if [ "${WHILE_INPUT:-}" = 1 ]; then
  # Whoever started the desktop holds its input open. When that closes, they have ended, and so
  # does the desktop.
  cat >/dev/null
  exit 0
fi
wait
