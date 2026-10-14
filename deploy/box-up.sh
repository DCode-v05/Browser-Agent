#!/usr/bin/env bash
# Brings the engine up on a Linux machine where you have no root, such as a shared box, joined to
# your tailnet and driving your Mac through the helper there (spec 22.6.2). Run it from the checkout:
#
#   bash deploy/box-up.sh https://your-mac.your-tailnet.ts.net:8796
#
# Tailscale is fetched into your own home folder and checked against the checksum Tailscale
# publishes. The three secrets are typed by you when it asks, and are never written to a file: the
# Tailscale auth key, the helper's pairing code, and the model's key.
set -euo pipefail

helper=${1:-}
if [ -z "$helper" ]; then
  echo "Give the address of the helper on your Mac, for example https://your-mac.your-tailnet.ts.net:8796" >&2
  exit 2
fi
version=${TS_VERSION:-1.104.1}
case "$(uname -m)" in
  x86_64) arch=amd64 ;;
  aarch64 | arm64) arch=arm64 ;;
  *) echo "Tailscale publishes no build for $(uname -m)." >&2; exit 2 ;;
esac
home=${BAP_BOX_HOME:-$HOME/.bap-box}
here=$home/tailscale_${version}_${arch}
if [ ! -x "$here/tailscaled" ]; then
  mkdir -p "$home"
  tarball=$home/tailscale_${version}_${arch}.tgz
  curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_${version}_${arch}.tgz" -o "$tarball"
  wanted=$(curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_${version}_${arch}.tgz.sha256")
  if [ "$(sha256sum "$tarball" | cut -d' ' -f1)" != "$wanted" ]; then
    rm -f "$tarball"
    echo "The Tailscale download does not match the checksum Tailscale publishes. Nothing was installed." >&2
    exit 3
  fi
  tar -xzf "$tarball" -C "$home"
  rm -f "$tarball"
fi
export PATH="$here:$PATH"
echo "Tailscale $(tailscale version | head -1) is in $here" >&2

# The secrets: from the environment, or typed now. Never echoed, never written.
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
ask BAP_BROWSER_HELPER_TOKEN "The pairing code the helper on your Mac shows"
ask ANTHROPIC_API_KEY "Claude API key"

cd "$(dirname "$0")/.."
uv sync --frozen
if [ ! -f src/bap_browser/viewer_dist/index.html ]; then
  if command -v npm >/dev/null 2>&1; then
    npm --prefix viewer ci && npm --prefix viewer run build
  else
    echo "There is no npm here to build the viewer. Build it on your Mac and copy src/bap_browser/viewer_dist over." >&2
    exit 2
  fi
fi
export BAP_BROWSER__COMPUTER__RUNS=remote
export BAP_BROWSER__COMPUTER__HELPER_URL=$helper
export BAP_BROWSER__AGENT__PROVIDER=anthropic
export BAP_BROWSER__AGENT__MODEL=${BAP_BROWSER__AGENT__MODEL:-claude-opus-5-5}
export BAP_BROWSER__AGENT__API_KEY_ENV=ANTHROPIC_API_KEY
export BAP_BROWSER__AGENT__BASE_URL=https://api.anthropic.com/v1
exec sh deploy/vm-start.sh uv run bap-browser studio
