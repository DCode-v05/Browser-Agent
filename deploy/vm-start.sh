#!/bin/sh
set -eu
if [ -n "${TS_AUTHKEY:-}" ]; then
  if ! command -v tailscaled >/dev/null 2>&1; then
    echo "TS_AUTHKEY is set, but this image has no Tailscale. Build it with --build-arg TAILSCALE=true." >&2
    exit 2
  fi
  sock=/tmp/tailscaled.sock
  proxy=localhost:1055
  certs=$(mktemp -d)
  tailscaled --tun=userspace-networking --state=mem: --statedir="$certs" --socket="$sock" \
    --outbound-http-proxy-listen="$proxy" --socks5-server="$proxy" >/tmp/tailscaled.log 2>&1 &
  if ! tailscale --socket="$sock" up --authkey="$TS_AUTHKEY" --hostname="${TS_HOSTNAME:-bap-browser}" --timeout=60s >&2; then
    echo "The VM could not join the tailnet with the key it was given. The key must be reusable, ephemeral, tagged and not expired." >&2
    exit 3
  fi
  unset TS_AUTHKEY
  name=$(tailscale --socket="$sock" status --json | python3 -c 'import json, sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
  tailscale --socket="$sock" serve --bg --https=443 http://127.0.0.1:8765 >&2
  export BAP_BROWSER__SERVER__HOST=127.0.0.1
  export BAP_BROWSER__SERVER__PUBLIC_URL="https://$name"
  export BAP_BROWSER__BROWSER__PROXY__SERVER="http://$proxy"
  export HTTP_PROXY="http://$proxy" HTTPS_PROXY="http://$proxy"
  echo "Joined the tailnet as $name. The viewer is at https://$name" >&2
fi
if command -v dbus-run-session >/dev/null 2>&1; then
  exec dbus-run-session -- "$@"
fi
exec "$@"
