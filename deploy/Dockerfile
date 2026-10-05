# The browser service in a container (spec 17.2): one session, its tools over MCP on HTTP, the viewer.
# Build from the repository's root:   docker build -f deploy/Dockerfile -t bap-browser .
# Run:   docker run --rm -p 8765:8765 -e BAP_BROWSER_TOKEN=<a long random string> bap-browser

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
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
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

# Not root: the service and the browser run as the image's unprivileged user.
USER pwuser
WORKDIR /data
ENV HOME=/home/pwuser BAP_BROWSER_CONFIG=/etc/bap-browser/config.json
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=2)"
# The token comes from the environment (BAP_BROWSER_TOKEN), never from the image.
CMD ["uv", "run", "--project", "/app", "--no-sync", "bap-browser", "serve"]
