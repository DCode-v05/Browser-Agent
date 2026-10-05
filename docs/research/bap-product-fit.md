# How the BAP product is built, where a browser agent has to fit

Read on 2026-10-05 from the product's code beside this repository (`Code/architecture`, `bap-backend`,
`bap-engine`, `bap-web`, `citadel`, `docs`, `product-docs`). Nothing was run. The agent core itself
("september-engine") is in a separate private repository; what is said about it comes from the
architecture documents, not from its code.

## What the meeting's words mean in the product today

| Word | What exists |
|---|---|
| Plugin | No plugin system. The nearest thing is an **asset** (also called a connector): one MCP server, listed in a catalogue (`bap-backend/src/assets/catalog-seed.ts`: name, icon, auth method, tools, `server_url`). A person connects one through `POST /assets/connect/:server`, an API key, or a custom server address. Each tool of an asset can be set to allow, ask or deny |
| MCP | The engine speaks MCP over HTTP only (streamable HTTP, JSON-RPC by POST). No stdio. An asset's tools appear to the agent as `ad:{server}.{action}`. The product ships 71 MCP servers of its own (`bap-backend/mcp-servers/*-mcp`, Express, `POST /mcp`, a bearer token, each with a Dockerfile). None is a browser |
| Micro VM | Not there. Each user gets one Docker container (`bap-engine/orchestrator/backends/docker_backend.py`, image `september-engine:latest`, host port 9001 to 9999, sleeps after an hour idle). The architecture notes only say a Firecracker, Fly or E2B provider could be swapped in later |
| Tool call output | Socket.IO event `tool_activity` `{toolName, phase: call or result, params, result, durationMs}`; shown by `components/super-chat/turn-blocks/ToolTurnBlock.tsx` as a row that expands to "Input" and "Result". Results are cut to 500 characters, text only, so a screenshot does not pass |
| Human in the loop | Event `hitl_prompt` (question, choices, the tool and its parameters), answered with `ie:hitl_respond` (approved, modified, denied); card `HitlInlineCard.tsx`. In practice approvals are switched off: the container is seeded with "allow everything" |
| App shell | Next.js 16, React 19, Tailwind 4, shadcn (`components.json`, style new-york). Left rail 88 or 248 px, then the main area. Chat is on the **left**; the right column holds an app or an artifact, resizable (at least 320 px). There is no right-side chat today |
| Desktop app, extension | Neither exists anywhere in the product |

## What this means for bap-browser

1. **The way in is an asset.** To the product, bap-browser is one more MCP server over HTTP, connected as an asset. `bap-browser mcp` speaks stdio only, so MCP over HTTP (`serve`) is what makes it usable there.
2. **A tool with a UI already has a seam.** A tool result that carries `_meta.ui.resourceUri` becomes `mcp_app_render` and is shown in the right column in a sandboxed frame. That is where the viewer could appear inside the product.
3. **Nothing reaches a service inside a user's container from the browser.** The frontend talks only to the backend. A live picture, or a bridge channel from an extension, needs a route that does not exist yet.
4. **Chromium inside the engine's container is unlikely as it is:** read-only root, no network in the inner sandbox, all capabilities dropped. The browser would run as its own service.
5. **Screenshots cannot travel as tool results** while results are cut to 500 characters.
