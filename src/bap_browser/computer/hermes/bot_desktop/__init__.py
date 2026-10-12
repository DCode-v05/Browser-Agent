# Taken from NousResearch/hermes-agent at 3569e846: tools/bot_desktop/__init__.py
# MIT License, Copyright (c) 2025 Nous Research. Changed only by scripts/take_hermes.py.
"""Bot Desktop: per-profile headless Xfce desktop over RFB, viewed from Hermes Desktop.

``runtime`` owns the Xvnc/Xfce process and the published env; ``lease`` owns who may drive the
screen (agent vs. human); ``rfb_filter`` is the byte-level input gate the WebSocket bridge applies.
"""
