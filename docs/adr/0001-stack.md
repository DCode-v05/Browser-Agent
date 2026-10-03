# 1. Stack

Date: 2026-10-03 · Status: accepted

## Context

bap-browser gives AI agents a browser through one contract (browser-MCP) and lets a person watch and
control it. Chromium runs in three places: in the micro VM beside the agent, in the person's own
Chrome through an extension, and inside the desktop app.

## Decision

- The core is Python 3.12+, managed with uv. Browser driving is Playwright for Python plus direct
  Chrome DevTools Protocol sessions, behind a driver interface made of plain data.
- Agents reach the core in-process, or over MCP (stdio and streamable HTTP) with the official SDK.
- Configuration is typed with Pydantic; one file holds every default.
- The viewer is TypeScript, React and Vite; its built files ship inside the Python package.
- The extension for take-over Chrome carries a small TypeScript driver that implements the same
  driver interface and enforces permissions on the person's machine. The core stays in Python.
- Checks: ruff, pyright and pytest for Python; tsc, ESLint and Vitest for TypeScript.

## Consequences

- One codebase holds the tools, the policy and the results for every backend.
- The driver operations exist twice (Python with Playwright, TypeScript in the extension). One
  conformance suite runs against both to keep them the same.
- The page-reading script is JavaScript shared by every backend.
