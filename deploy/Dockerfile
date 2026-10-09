# The browser service in a container (spec 17.2): one session, its tools over MCP on HTTP, the viewer.
# Build from the repository's root:   docker build -f deploy/Dockerfile -t bap-browser .
# Run:   docker run --rm -p 8765:8765 -e BAP_BROWSER_TOKEN=<a long random string> bap-browser
# With the desktop of computer use (spec 21.1, arrangement 2): build with --build-arg DESKTOP=true,
# then run it with `uv run --project /app --no-sync bap-browser serve --desktop` as its command.

# The viewer is built first: the Python package carries it.
FROM node:22-slim AS viewer
WORKDIR /build
COPY viewer/package.json viewer/package-lock.json viewer/
RUN npm --prefix viewer ci
COPY viewer viewer
# The build writes into src/bap_browser/viewer_dist, beside the package.
RUN npm --prefix viewer run build

# Playwright's own image: Chromium, and the libraries and fonts it needs, at the version in uv.lock.
# A test keeps this tag and the lock file together.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble
# uv from PyPI: no other registry is needed to build this image.
RUN pip install --no-cache-dir uv==0.12.5
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
# The dependencies first, so that a change to the code does not install them again.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src src
COPY --from=viewer /build/src/bap_browser/viewer_dist src/bap_browser/viewer_dist
RUN uv sync --frozen --no-dev

COPY deploy/config.vm.json /etc/bap-browser/config.json
# What the service writes (where it is, its log) goes to a folder of its own, owned by the user it runs as.
RUN mkdir -p /data && chown pwuser:pwuser /data

# The desktop of computer use, on the machine's own virtual screen: no terminal is installed, and the
# window manager's own menu is empty. The machine itself is the boundary.
ARG DESKTOP=false
COPY deploy/desktop-menu.xml /tmp/desktop-menu.xml
RUN if [ "$DESKTOP" = true ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends \
         xvfb openbox xdotool imagemagick x11-xserver-utils x11-utils dbus-x11 mousepad pcmanfm galculator \
      && rm -rf /var/lib/apt/lists/* \
      && install -d -o pwuser -g pwuser /home/pwuser/.config/openbox /home/pwuser/Files \
      && install -o pwuser -g pwuser -m 644 /tmp/desktop-menu.xml /home/pwuser/.config/openbox/menu.xml; \
    fi; rm /tmp/desktop-menu.xml

# Tailscale, for a VM that joins a person's tailnet (spec 21.12, arrangement 3). It joins only when the
# container is given TS_AUTHKEY; the key is never in the image.
ARG TAILSCALE=false
RUN if [ "$TAILSCALE" = true ]; then \
      curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o /usr/share/keyrings/tailscale-archive-keyring.gpg \
      && curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list -o /etc/apt/sources.list.d/tailscale.list \
      && apt-get update && apt-get install -y --no-install-recommends tailscale \
      && rm -rf /var/lib/apt/lists/*; \
    fi
COPY --chmod=755 deploy/vm-start.sh /usr/local/bin/vm-start

# Not root: the service and the browser run as the image's unprivileged user.
USER pwuser
WORKDIR /data
ENV HOME=/home/pwuser BAP_BROWSER_CONFIG=/etc/bap-browser/config.json
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=2)"
# The token comes from the environment (BAP_BROWSER_TOKEN), never from the image.
ENTRYPOINT ["/usr/local/bin/vm-start"]
CMD ["uv", "run", "--project", "/app", "--no-sync", "bap-browser", "serve"]
