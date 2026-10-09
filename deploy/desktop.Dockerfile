# The contained desktop of computer use (spec 21): a small Linux desktop with a virtual screen and a
# few apps, driven from outside with the mouse and the keyboard. It holds no account data and no
# credential, and it runs as a user without root rights.
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      xvfb openbox xdotool imagemagick x11-xserver-utils x11-utils xauth dbus-x11 \
      fonts-dejavu-core xterm mousepad pcmanfm galculator \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash agent \
 && mkdir -p /home/agent/Files \
 && chown -R agent:agent /home/agent
COPY --chown=agent:agent desktop-start.sh /usr/local/bin/desktop-start
# The desktop's own right-click menu is empty: an app is opened by the tools, inside what a person allows.
COPY --chown=agent:agent desktop-menu.xml /home/agent/.config/openbox/menu.xml
RUN chmod 755 /usr/local/bin/desktop-start

USER agent
WORKDIR /home/agent
ENV DISPLAY=:1 HOME=/home/agent
CMD ["/usr/local/bin/desktop-start"]
