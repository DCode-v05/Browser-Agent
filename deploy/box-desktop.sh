#!/usr/bin/env bash
# Starts a Linux desktop on a box with no root, in rootless Docker, joined to the tailnet as a node
# of its own (spec 22.6). The engine there drives that desktop, and its page is served to the
# tailnet. A helper beside the desktop lets an engine elsewhere drive it too, for the Tailscale
# logins named. Run it on the box, once rootless Docker answers (`~/.bap-box/docker-env`):
#
#   bash deploy/box-desktop.sh you@example.com
#
# It asks for the Tailscale auth key and the Claude key without showing them, and writes neither to
# a file. The helper's pairing code is made here and kept for the box's user alone.
set -euo pipefail

allow=${1:-}
if [ -z "$allow" ]; then
  echo "Give the Tailscale login that may drive this desktop from elsewhere, for example you@example.com" >&2
  exit 2
fi
# shellcheck source=/dev/null
source "$HOME/.bap-box/docker-env"
image=${BAP_DESK_IMAGE:-bap-desk:latest}
if ! docker image inspect "$image" >/dev/null 2>&1; then
  echo "There is no image $image. Build it on this box first:" >&2
  echo "  docker build --network host --build-arg DESKTOP=true --build-arg TAILSCALE=true -t $image -f deploy/Dockerfile ." >&2
  exit 2
fi

ask() {
  local name=$1 what=$2 given
  if [ -z "${!name:-}" ]; then
    if [ ! -t 0 ]; then
      echo "$name is not set, and there is nobody to type it: $what." >&2
      exit 2
    fi
    read -r -s -p "$what: " given
    echo >&2
    export "$name=$given"
  fi
}
ask TS_AUTHKEY "Tailscale auth key (reusable, ephemeral, tagged tag:bap-vm)"
ask ANTHROPIC_API_KEY "Claude API key"

umask 077
code_file=$HOME/.bap-box/desk-pairing-code
if [ ! -s "$code_file" ]; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(18))' > "$code_file"
fi
BAP_BROWSER_HELPER_TOKEN=$(cat "$code_file")
export BAP_BROWSER_HELPER_TOKEN

docker rm -f bap-desk >/dev/null 2>&1 || true
# In the container: the engine's studio starts the desktop's own screen, and once that screen is
# there, the helper drives it for an engine elsewhere. Tailscale's userspace socket is named, so
# that the helper can ask who a caller is. What it writes in /data (its task records, settings and
# sign-ins) is kept in a volume of its own, which the next container finds again.
docker run -d --name bap-desk --network host \
  -v bap-desk-data:/data \
  -e TS_AUTHKEY -e ANTHROPIC_API_KEY -e BAP_BROWSER_HELPER_TOKEN \
  -e TS_HOSTNAME="${BAP_DESK_NAME:-bap-desk}" \
  -e BAP_BROWSER__COMPUTER__RUNS=here \
  -e BAP_BROWSER__COMPUTER__BASE__HELPER_ALLOW="[\"$allow\"]" \
  -e BAP_BROWSER__COMPUTER__BASE__TAILSCALE_SOCKET=/tmp/tailscaled.sock \
  -e BAP_BROWSER__AGENT__PROVIDER=anthropic \
  -e BAP_BROWSER__AGENT__MODEL="${BAP_BROWSER__AGENT__MODEL:-claude-opus-5-5}" \
  -e BAP_BROWSER__AGENT__API_KEY_ENV=ANTHROPIC_API_KEY \
  -e BAP_BROWSER__AGENT__BASE_URL=https://api.anthropic.com/v1 \
  -e BAP_BROWSER__AGENT__INPUT_PRICE_PER_MILLION="${BAP_BROWSER__AGENT__INPUT_PRICE_PER_MILLION:-4}" \
  -e BAP_BROWSER__AGENT__OUTPUT_PRICE_PER_MILLION="${BAP_BROWSER__AGENT__OUTPUT_PRICE_PER_MILLION:-20}" \
  "$image" sh -c '
    tailscale --socket=/tmp/tailscaled.sock serve --bg --https=8796 http://127.0.0.1:8796 >&2
    uv run --project /app --no-sync bap-browser studio --dev &
    until DISPLAY=:1 xdpyinfo >/dev/null 2>&1; do sleep 1; done
    DISPLAY=:1 exec uv run --project /app --no-sync bap-browser computer helper
  ' >/dev/null
unset TS_AUTHKEY ANTHROPIC_API_KEY
echo "The desktop is starting as ${BAP_DESK_NAME:-bap-desk} on the tailnet. Its pairing code is in $code_file." >&2
