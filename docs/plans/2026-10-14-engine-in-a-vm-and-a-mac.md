# The engine in a Linux VM, driving a Mac over Tailscale: the steps

Written on 2026-10-14. Nothing here has been run over a real tailnet yet. Each step ends in a check;
the last section says what is proven today without a tailnet and what is not.

## What runs where

| Part | Machine | What it does |
|---|---|---|
| The engine and its service | The Linux box (the team box, or any micro VM) | Runs the agent, serves the viewer to the tailnet |
| Tailscale in userspace mode | The Linux box | Joins the tailnet without root; gives the engine a local proxy at `localhost:1055` |
| The helper | The Mac | Starts the driver, relays the engine's calls, returns screenshots and elements |
| The chat above every app | The Mac | The chat of the service's Computer page, in a window that stays on top |

The engine calls the Mac. The Mac never takes a call from the internet or the LAN: the helper
listens on `127.0.0.1` and `tailscale serve` shows it to the tailnet alone (spec 22.6.2).

The four arrangements of spec 22.6 map to settings like this:

| Arrangement | `computer.runs` | Tailscale |
|---|---|---|
| A. Engine on the Mac, driving the Mac | `machine` | None |
| B. Engine on the Mac or in a VM, driving a contained desktop | `container`, or `here` in a VM | None |
| C. Engine in a remote VM, reaching your private data | `here` | The VM joins your tailnet |
| D. Engine in a remote VM, driving the Mac | `remote` | The VM reaches the helper on the Mac |

This document is arrangement D. The Windows side of D is a teammate's work and is not covered.

## Decide first: the keys on a shared box

The team box has one login, `team`, shared by everybody. A process started there shows its
environment to anybody with that login. Three secrets would be on it: the Tailscale key, the
helper's pairing code and the model key. With the pairing code and the tailnet tag, a teammate on
the box could drive your Mac through the helper for as long as the helper runs.

Choose one before starting:

- Use a micro VM that only you can log in to. Nothing below changes.
- Use the team box, and accept that teammates on it can reach the helper while it runs. End the
  helper (Ctrl+C) the moment you are done, and use a Tailscale key that expires the same day.

## Once, in the Tailscale admin console

| Step | Value |
|---|---|
| Turn on MagicDNS and HTTPS certificates | `tailscale serve` needs both |
| Make a tag | `tag:bap-vm` |
| Make an auth key | Reusable, ephemeral, tagged `tag:bap-vm`, with a short expiry |
| Grant | `tag:bap-vm` to your Mac on port 8796 (the helper) |
| Grant | Your own login to `tag:bap-vm` on port 443 (the viewer) |

The key is typed by you, on the box, into the shell that starts the engine. It goes into no file
of this repository.

## On the Mac

1. Install Tailscale and sign in. Check: `tailscale status` lists this Mac.
2. Install the driver and allow it:

   ```sh
   uv run bap-browser computer install
   uv run bap-browser computer doctor
   ```

   The doctor names what macOS still has to allow (Accessibility, Screen Recording). Allow both.
3. Start the helper and leave it running:

   ```sh
   uv run bap-browser computer helper
   ```

   It prints a pairing code, who it lets in (`tag:bap-vm`), and this line:

   ```sh
   tailscale serve --bg --https=8796 http://127.0.0.1:8796
   ```

   Run that line in a second terminal. Check: `tailscale serve status` shows port 8796.
4. Note the Mac's tailnet name: `tailscale status --json | grep DNSName | head -1`.

The helper holds the engine to the apps your Mac's own settings allow. To let it work in any app,
turn on "Let the agent work in any app on the machine" on the Mac before starting the helper.

## On the Linux box

1. Tailscale without root. Download the static build for the box's processor from
   `pkgs.tailscale.com/stable`, unpack it in your home folder, and put that folder on `PATH`.
   Check: `tailscaled --version`.
2. The code:

   ```sh
   git clone https://github.com/DCode-v05/Browser-Agent.git && cd Browser-Agent
   uv sync && uv run playwright install chromium
   npm --prefix viewer ci && npm --prefix viewer run build
   ```

   If the box has no `node`, build the viewer on the Mac and copy `src/bap_browser/viewer_dist/` over.
3. A `config.json` beside the code:

   ```json
   {
     "computer": {"runs": "remote", "helper_url": "https://YOUR-MAC.YOUR-TAILNET.ts.net:8796"},
     "agent": {"provider": "anthropic", "model": "claude-opus-5-5", "api_key_env": "ANTHROPIC_API_KEY"}
   }
   ```

4. The three secrets, typed by you into the shell and nowhere else:

   ```sh
   read -s "?Tailscale key: " TS_AUTHKEY && export TS_AUTHKEY
   read -s "?Pairing code: " BAP_BROWSER_HELPER_TOKEN && export BAP_BROWSER_HELPER_TOKEN
   read -s "?Model key: " ANTHROPIC_API_KEY && export ANTHROPIC_API_KEY
   ```

   In `bash`, the form is `read -s -p "Tailscale key: " TS_AUTHKEY`.
5. Start it. The script joins the tailnet, serves the viewer to the tailnet over HTTPS, points the
   engine at Tailscale's proxy, and forgets the key:

   ```sh
   sh deploy/vm-start.sh uv run bap-browser studio
   ```

   It prints "Joined the tailnet as NAME. The viewer is at https://NAME".

## Check it, in this order

| # | Where | Do | Expect |
|---|---|---|---|
| 1 | Linux box | Open the viewer's address from the Mac's browser | The sign-in page, over HTTPS |
| 2 | Viewer | Open the Computer page | The Mac's screen, live. This is the streaming of the Mac to the remote engine |
| 3 | Mac, helper's terminal | Watch it | A line for each thing the engine does, never what is typed |
| 4 | Mac | `uv run bap-browser computer chat https://NAME` | The chat in a narrow window at the right edge, above every app |
| 5 | That window | Give a task that opens Safari | Safari opens; the chat stays above it; the next task is given there |
| 6 | That window | Give a task that presses Send or Delete in an app | It waits for your yes before the press |
| 7 | Mac, helper's terminal | Ctrl+C | The engine's next call says the helper could not be reached |

If check 2 fails with "The helper on the other machine could not be reached", the grant for port
8796 is missing or `tailscale serve` is not running on the Mac. A 403 means the box did not join
with `tag:bap-vm`. A 401 means the pairing code was mistyped.

## What is proven today, and what is not

Proven without a tailnet:

- The engine's link reaches a helper it can only find through a proxy, for single calls and for
  the live conversation (`tests/unit/test_machine_helper.py`,
  `test_where_tailscale_gives_a_proxy_the_link_reaches_the_helper_through_it`). In userspace mode
  that proxy is the only way to a tailnet name, so this is the route step 5 sets up.
- The helper refuses a caller with no tailnet identity, a wrong tag or a wrong code (same file).
- The engine drives a Mac through the helper on the same machine (`scripts/ladder.py --through-helper`).
- The chat's window opens above every app on this Mac and says where it stands.

Not proven:

- Anything over a real tailnet: the join, the grants, `tailscale serve` on the Mac, the HTTPS
  certificate of the helper's name as the link sees it through the proxy.
- The speed of the live picture across the tailnet.
- The Anthropic provider against the real service.
- Take over from the viewer on a real Mac: the page says to use the Mac's own mouse and keyboard.
