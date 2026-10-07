# MCP-specific security research for bap-browser (as of 2026-10-06)

Researched on the web on 2026-10-06 by a research agent. One read-only look at the repo: `uv.lock` pins
`mcp` 2.3.0, the newest release.

## How to read the provenance marks
- **raw**: the page source was fetched (curl) and read. Quotes are verbatim.
- **summarizer**: read through a fetch tool that returns a small model's extraction. Quotes are probably right but were not checked against the page.
- **snippet**: search result only.
- Web search ran out of budget and the fetch tool hit its limit partway through, so later pages were read raw.

## 0. Things that differ from what we assumed

1. **The current spec is 2026-07-28**, not 2025-06-18 or 2025-11-25. The versioning page says: "The **current** protocol version is **2026-07-28**."
2. **Protocol sessions are gone.** 2026-07-28 removes `Mcp-Session-Id`, the `initialize` handshake, the GET stream, and SSE resumability. "Session Hijacking" is now "State Handle Hijacking". The old session rules still matter because the SDK docs say "Your 2025-era clients (today, that is most clients) still open sessions".
3. **Dynamic Client Registration is deprecated** in favour of Client ID Metadata Documents. **Sampling, Roots and Logging are deprecated.**
4. **New mandatory request headers** on Streamable HTTP: `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`, with header/body mismatch rejection.
5. **The Python SDK has 12 published advisories.** All are fixed at or below 2.2.0, so 2.3.0 is patched, but two fixes only take effect if you configure them (section 8).
6. A new official page, **Local Server Security**, is close to a description of our deployment.

## 1. Security Best Practices page (2026-07-28, raw, fully read)
URL: https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices

| Attack | What it is | Mitigation (verbatim where quoted) |
|---|---|---|
| Confused deputy | Proxy server with a static client ID to a third-party authorization server, plus dynamic registration, plus a consent cookie: attacker gets a code without consent | "MCP proxy servers **MUST** implement per-client consent and proper security controls". Per-user registry of approved `client_id`; consent page names client, scopes, `redirect_uri`, has CSRF protection and blocks framing; cookies use `__Host-` prefix with `Secure`, `HttpOnly`, `SameSite=Lax`; exact-match redirect URIs; single-use `state` set only after consent |
| Token passthrough | Server accepts tokens not issued to it and forwards them | "MCP servers **MUST NOT** accept any tokens that were not explicitly issued for the MCP server." Called "explicitly forbidden" |
| SSRF in OAuth discovery | Malicious server points `resource_metadata`, `authorization_servers`, `token_endpoint` at internal addresses | "MCP clients deployed to a server **MUST** consider SSRF risks". SHOULD: require HTTPS, block private ranges, validate redirect hops, use an egress proxy, pin DNS. Also applies to authorization servers fetching client metadata |
| State handle hijacking (new) | Attacker obtains or guesses a server-minted handle | "MCP servers that implement authorization **MUST** verify all inbound requests. MCP servers **MUST NOT** treat possession of a state handle as authentication." "MCP servers **SHOULD** use secure, non-deterministic handles generated with secure random number generators." "MCP servers **SHOULD** bind handles server-side to the authenticated user" |
| Session hijacking (2025-11-25 page, raw) | Two forms: prompt injection through a shared queue keyed by session ID; impersonation with a stolen ID | "MCP Servers **MUST NOT** use sessions for authentication." "MCP servers **MUST** use secure, non-deterministic session IDs." "MCP servers **SHOULD** bind session IDs to user-specific information" (key format `<user_id>:<session_id>`) |
| Local MCP server compromise | Malicious startup command, malicious payload, or "An attacker accesses an insecure local server that's left running on localhost via DNS rebinding" | Clients MUST show the exact command and get approval. Servers: "MCP servers intending for their servers to be run locally **SHOULD** implement measures to prevent unauthorized usage from malicious processes: Use the `stdio` transport to limit access to just the MCP client; Restrict access if using an HTTP transport, such as: Require an authorization token; Use unix domain sockets or other Interprocess Communication (IPC) mechanisms with restricted access" |
| OAuth authorization URL validation | Malicious server supplies `javascript:` or shell-injecting URLs | Clients MUST allow only `http`/`https`, "**MUST NOT** use shell commands (e.g., `cmd.exe`, `sh`, PowerShell) to open URLs" |
| stdio in proxy scenarios | XSS in a client steals the proxy token, proxy spawns commands | Sandbox spawned processes, CSP, log stdio use |
| Mix-up attacks | Attacker authorization server receives an honest server's code | RFC 9207 `iss` validation; "PKCE alone does not prevent this attack" |
| Localhost redirect URI impersonation / CIMD trust policies | Any local process can claim a client's metadata URL | Authorization servers show the redirect host and warn on localhost-only URIs |
| Scope minimization | Broad up-front scopes widen token theft impact | Minimal initial scopes, step-up via `WWW-Authenticate`; avoid wildcard scopes; "Log elevation events" |

Local Server Security page (raw, fully read): https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/local-server-security
- "Binding to 127.0.0.1 is not an authentication boundary: such components need real authentication and origin validation, and they need prompt updates when advisories land."
- It names tool poisoning, shadowing and rug pull as threat 4, and "local developer tools listening on a port have been exploited directly from a web page" as threat 5.
- "Prefer clients that pin tool definitions... The protocol does not require this".

## 2. Transports (raw)
Streamable HTTP 2026-07-28: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http

Security section, verbatim:
> 1. Servers **MUST** validate the `Origin` header on all incoming connections to prevent DNS rebinding attacks.
>    * If the `Origin` header is present and invalid, servers **MUST** respond with HTTP 403 Forbidden. The HTTP response body **MAY** comprise a JSON-RPC *error response* that has no `id`.
> 2. When running locally, servers **SHOULD** bind only to localhost (127.0.0.1) rather than all network interfaces (0.0.0.0).
> 3. Servers **SHOULD** implement proper authentication for all connections.
>
> Without these protections, attackers could use DNS rebinding to interact with local MCP servers from remote websites.

The 403 sub-clause was added in 2025-11-25; the 2025-06-18 text has only the three numbered items.

Other rules:
- "Every POST request to the MCP endpoint **MUST** include an `MCP-Protocol-Version` header." It must match `_meta`; otherwise "the server **MUST** reject the request with `400 Bad Request` and a `HeaderMismatch` JSON-RPC error" (code `-32020`).
- `Mcp-Method` and `Mcp-Name` are required. "Servers that process the request body **MUST** reject requests where the values specified in the headers do not match the corresponding values in the request body."
- A 2026-only server receiving old traffic SHOULD answer GET/DELETE with 405 and: "An `Mcp-Session-Id` header on a request: ignore it, and do not mint or echo session IDs."
- Tools spec: "Server developers **SHOULD NOT** mark sensitive parameters (passwords, API keys, tokens, PII) with `x-mcp-header`".

Session rules, 2025-11-25 (raw): https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- "The session ID **SHOULD** be globally unique and cryptographically secure (e.g., a securely generated UUID, a JWT, or a cryptographic hash)."
- "The session ID **MUST** only contain visible ASCII characters (ranging from 0x21 to 0x7E)."
- Servers requiring a session "**SHOULD** respond to requests without an `MCP-Session-Id` header (other than initialization) with HTTP 400 Bad Request."
- After termination the server "**MUST** respond to requests containing that session ID with HTTP 404 Not Found."
- Invalid `MCP-Protocol-Version`: "**MUST** respond with `400 Bad Request`"; a missing header is treated as `2025-03-26`.

stdio 2026-07-28 (raw): "The server **MUST NOT** write anything to its `stdout` that is not a valid MCP message." Logging goes to `stderr`.

## 3. Authorization (raw; index and security-considerations fully read, discovery read, client-registration first half read)
URL: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization

- "Authorization is **OPTIONAL** for MCP implementations." HTTP transports "**SHOULD** conform to this specification." "Implementations using an STDIO transport **SHOULD NOT** follow this specification, and instead retrieve credentials from the environment."
- Based on OAuth 2.1 draft-13, RFC 8414, 7591, 8707, 9728, 9207 and the CIMD draft.
- "MCP servers **MUST** implement OAuth 2.0 Protected Resource Metadata (RFC9728)", with `authorization_servers`, discoverable through `WWW-Authenticate ... resource_metadata` on 401 or the well-known URI.
- Clients "**MUST** implement Resource Indicators" and send `resource` in authorization and token requests.
- "MCP servers **MUST** validate that access tokens were issued specifically for them as the intended audience". "Invalid or expired tokens **MUST** receive a HTTP 401 response." "MCP servers **MUST NOT** accept or transit any other tokens." Upstream: "The MCP server **MUST NOT** pass through the token it received from the MCP client."
- "authorization **MUST** be included in every HTTP request from client to server"; "Access tokens **MUST NOT** be included in the URI query string".
- PKCE: clients "**MUST** implement PKCE", "**MUST** use the `S256` code challenge method when technically capable", and refuse if `code_challenge_methods_supported` is absent.
- "Clients and servers **MUST** implement secure token storage". "Authorization servers **SHOULD** issue short-lived access tokens".
- Registration priority: pre-registered, then CIMD, then DCR ("Dynamic Client Registration is deprecated"), then ask the user.
- Tutorial (raw): authorization is "strongly recommended when" the server "accesses user-specific data", or "You need to audit who performed which actions".

**What a single static bearer token lacks, compared with the spec** (the researcher's inference from the quotes above):
1. No RFC 9728 metadata and no `resource_metadata` challenge, so clients cannot discover how to authenticate; the token must be configured by hand.
2. No audience binding. Nothing ties the token to one instance, port or resource.
3. No expiry or rotation; the spec expects short-lived tokens.
4. No per-user identity. Every holder is the same principal, so handles or sessions cannot be bound to a user, and audit cannot say who acted.
5. No scopes, so no least privilege and no step-up. The spec allows tool lists to "vary by the authorization presented"; a single token cannot.
6. No revocation short of changing the token.
7. Still binding: header only, never the query string, on every request, 401 when wrong, stored securely, never logged. Browsers cannot set an `Authorization` header on a WebSocket handshake, so the extension bridge needs another carrier that is not the URL (design implication; inference).

For a server on 127.0.0.1 a required token matches the spec's own local-server advice ("Require an authorization token"). For any non-loopback deployment it falls short of the SHOULD.

## 4. Annotations, elicitation, sampling, consent, tool output (raw)

Tool annotations (schema.ts 2026-07-28):
- `readOnlyHint` default false; `destructiveHint` default true; `idempotentHint` default false; `openWorldHint` default true. The last: "the world of a web search tool is open".
- "NOTE: all properties in `ToolAnnotations` are **hints**. They are not guaranteed to provide a faithful description of tool behavior... Clients should never make tool use decisions based on `ToolAnnotations` received from untrusted servers."
- Tools page: "clients **MUST** consider tool annotations to be untrusted unless they come from trusted servers."
- MCP blog, "Tool Annotations as Risk Vocabulary" (2026-03-16, raw): "They aren't enforcement. If you need a guarantee that a tool can't exfiltrate data, that's a job for network controls or sandboxing, not a boolean hint." On open-world tools: "The safest posture is to treat anything a tool considers external as a potential source of untrusted content." Five annotation SEPs are open, including #1913 trust and sensitivity.

User interaction and consent:
- Tools: "there **SHOULD** always be a human in the loop with the ability to deny tool invocations." Applications SHOULD "Provide UI that makes clear which tools are being exposed", "Insert clear visual indicators when tools are invoked", "Present confirmation prompts".
- Spec index: "Users must explicitly consent to and understand all data access and operations"; "Hosts must obtain explicit user consent before invoking any tool"; "Hosts must not transmit resource data elsewhere without user consent". These are lowercase, and the page adds "MCP itself cannot enforce these security principles at the protocol level".
- Tools security considerations: "Servers **MUST**: Validate all tool inputs; Implement proper access controls; Rate limit tool invocations; Sanitize tool outputs". Clients SHOULD: "Prompt for user confirmation on sensitive operations", "Show tool inputs to the user before calling the server, to avoid malicious or accidental data exfiltration", "Validate tool results before passing to LLM", "Implement timeouts for tool calls", "Log tool usage for audit purposes".

Elicitation:
- "Servers **MUST NOT** use form mode elicitation to request sensitive information such as passwords, API keys, access tokens, or payment credentials". "Servers **MUST** use URL mode for interactions involving such sensitive information". Names and emails are "not categorically prohibited".
- Servers "**MUST** bind elicitation requests to the client and user identity"; "**MUST NOT** rely on client-provided user identification without server verification".
- URL mode: no user secrets in the URL, no pre-authenticated URLs. Clients "**MUST NOT** automatically pre-fetch the URL", "**MUST NOT** open the URL without explicit consent", "**MUST** show the full URL".

Sampling: deprecated. "there **SHOULD** always be a human in the loop with the ability to deny sampling requests". "Clients **SHOULD** implement rate limiting"; "Both parties **SHOULD** implement iteration limits for tool loops".

Tool output and definitions:
- With an `outputSchema`: "Servers **MUST** provide structured results that conform to this schema."
- Resource links are allowed. Resources: "Servers **MUST** validate all resource URIs" and "**MUST** sanitize file paths to prevent directory traversal attacks".
- `tools/list` "**MUST NOT** vary per-connection" but "**MAY** vary by the authorization presented". "Servers **SHOULD** return tools in a deterministic order".
- Names: 1–128 characters from `A-Za-z0-9_-.`. Aggregators "**SHOULD** implement a disambiguation strategy such as prefixing tool names with a server identifier".
- "Stateful Tools" (non-normative) uses "an open browser context" as its example: return an explicit handle; "For unauthenticated servers, where the handle is necessarily a bearer token, it should be generated with sufficient entropy (e.g., a UUIDv4) and given a bounded lifetime."
- `clientInfo`/`serverInfo` are self-reported; implementations "**SHOULD NOT** rely on them for security decisions."
- "Implementations **MUST NOT** automatically dereference `$ref` values that resolve to a network URI."
- No MUST or SHOULD capping tool result size was found in the 2026-07-28 tools page.

## 5. Known attack classes

| Class / incident | Source, date, provenance | What happened and root cause | Control |
|---|---|---|---|
| Tool poisoning | Invariant Labs, 2025-04-01, raw | "malicious instructions are embedded within MCP tool descriptions that are invisible to users but visible to AI models"; demo leaked `~/.cursor/mcp.json` and SSH keys through a hidden parameter | Show full descriptions and arguments; pin; scan. Server side: descriptions hold no instructions about other tools or files |
| Rug pull | Same | "a malicious server can change the tool description after the client has already approved it" | Hash and pin definitions; re-prompt on change. Windows requirement: "Servers' definition of tools cannot be changed at runtime" |
| Cross-server shadowing | Same; WhatsApp follow-up 2025-04-07, partial raw | A malicious server's description changes how the agent uses a trusted server's tool; "Code isolation or sandboxing of the MCP server is not a relevant mitigation" | Isolation between servers; detect cross-references; few servers |
| Line jumping | Trail of Bits, 2025-04-21, summarizer; follow-up 2025-04-23, partial raw | Descriptions reach the model at `tools/list` before any call, bypassing invocation controls | "Implement trust-on-first-use (TOFU) validation for MCP servers. Alert users or administrators whenever a new tool is added or if an existing tool's description changes." |
| ANSI escape hiding | Trail of Bits, 2025-04-29, summarizer | Escape codes hide text from the user but not the model | Strip or replace byte `0x1b` in descriptions and outputs |
| Plaintext credential storage | Trail of Bits, 2025-04-30, summarizer | API keys in world-readable config and logs | OS credential store; tight file permissions |
| Full-schema poisoning, ATPA | CyberArk, 2025-05-30, **snippet only** | Payloads in parameter names, types, defaults, required arrays; ATPA hides prompts in runtime output and error strings | Treat the whole schema and every output as untrusted; strict schemas |
| Preference manipulation (MPMA) | arXiv 2505.11154, 2025-05-16, abstract via summarizer | Persuasive words in name/description make the model prefer the attacker's server | Neutral, factual descriptions; curated server lists |
| Name collision, typosquatting, installer spoofing | Hou et al., arXiv 2503.23278v3, taxonomy table raw | 16 threats, including "Namespace Typosquatting", "Tool Name Conflict", "Preference Manipulation", "Cross-Server Shadowing", "Installer Spoofing", "Configuration Drift" | Verified namespace; prefixed tool names; pinned versions |
| Lethal trifecta | Simon Willison, 2025-06-16, raw, fully read | "Access to your private data", "Exposure to untrusted content", "The ability to externally communicate in a way that could be used to steal your data". "Guardrails won't protect you". "The only way to stay safe there is to avoid that lethal trifecta combination entirely." | Remove one leg per session; human approval; egress limits |
| GitHub MCP data leak | Invariant, 2025-05-26, raw | Issue in a public repo makes the agent copy private-repo data into a public PR. "this is not a flaw in the GitHub MCP server code itself, but rather a fundamental architectural issue" | One repo per session; monitoring. GitHub later added "lockdown mode", described as "a best-effort content filter... **not** an authorization boundary" (README, raw) |
| Supabase MCP leak | General Analysis, 2025-07-08, partial raw; Supabase docs, summarizer | Support ticket text made a Cursor agent with `service_role` read `integration_tokens` and write it to a customer-visible reply | Read-only mode, project scoping, manual approval. Supabase wraps SQL results with warnings; "This is not foolproof though." |
| Asana cross-tenant bug | BleepingComputer, 2025-06-18, partial raw; UpGuard, summarizer | Launched 2025-05-01, found 2025-06-04; "a logic flaw in the MCP system" exposed data to other organizations' users. No public statement from Asana; root cause not published | Per-tenant and per-user authorization on every request; tenant-isolation tests; logs |
| MCP Inspector RCE, **CVE-2025-49596** (CVE.org: CVSS 4.0 9.4, fixed 0.14.1) | CVE record raw; Oligo, summarizer | "lack of authentication between the Inspector client and proxy, allowing unauthenticated requests to launch MCP commands over stdio"; reachable from a web page through 0.0.0.0, CSRF or DNS rebinding | Session token by default, plus Origin and Host validation |
| 0.0.0.0-day | Oligo, Aug 2024, partial raw | Browsers let public pages reach local services through 0.0.0.0 | "Verify the HOST header"; "Don't trust the localhost network because it is "local"—add a minimal layer of authorization"; CSRF tokens |
| mcp-remote, **CVE-2025-6514** (CVSS 9.6, 0.0.5–0.1.15, fixed 0.1.16) | GitHub advisory raw; JFrog, 2025-07-09, summarizer | Malicious server returns a crafted `authorization_endpoint`; opening it on Windows ran PowerShell | Client: scheme allowlist, no shell |
| Postmark MCP malicious package | Postmark statement, 2025-09-25, summarizer; Koi article not readable | Fake npm `postmark-mcp`; "added a backdoor in version 1.0.16 that secretly BCC'd emails to an external server"; "This is not an official Postmark tool." No CVE found | Verified publisher; pinned versions; official install path documented |
| Smithery build path traversal | GitGuardian, 2025-10-22, summarizer | `dockerBuildPath` not validated; leaked a fly.io token giving access to "more than 3000 apps". No CVE found | Path validation; least-privilege build credentials |
| Figma (Framelink), **CVE-2025-53967** (CVSS 7.5, fixed 0.6.3) | GitHub advisory raw; Imperva, summarizer | Unsanitized input in `child_process.exec` | No shell strings; argument arrays |
| Filesystem server, **CVE-2025-53109 / -53110** | GitHub advisories raw | Prefix matching and symlinks bypass allowed directories | Resolve real paths before checks |
| mcp-server-git, **CVE-2025-68143 / -68144 / -68145** | GitHub advisories raw | Unrestricted `git_init`; argument injection; missing path validation | Reject flag-like arguments; path containment |
| Cursor MCPoison, **CVE-2025-54136** (CVSS 7.2, fixed 1.3) | CVE.org raw; Check Point, summarizer | Approval bound to the server's key name, not its command | Re-approve on any change |
| Cursor, **CVE-2025-54135** (CVSS 8.6, fixed 1.3.9) | CVE.org raw | Prompt injection writes a new `.cursor/mcp.json`, leading to code execution | Approval for config writes |
| Prompt hijacking, **CVE-2025-6515** (oatpp-mcp, 6.8, advisory unreviewed) | GitHub advisory raw; JFrog, summarizer | Session ID was a memory pointer; attacker reuses it | Random IDs with at least 128 bits |
| NeighborJack | Backslash, 2025-06-25, summarizer | "Hundreds" of servers bound to 0.0.0.0; no exact counts given | Bind to loopback |
| **Playwright MCP, CVE-2025-9611** (CVSS 4.0 7.2, fixed 0.0.40) | CVE.org and GitHub advisory raw | "fails to validate the Origin header on incoming connections. This allows an attacker to perform a DNS rebinding attack via a victim's web browser" | Origin and Host validation. Closest precedent to our server |
| **Claude Code IDE extensions, CVE-2025-52882** (CVSS 4.0 8.8) | CVE.org raw | Local WebSocket accepted "connections from arbitrary origins"; a web page could read files | Check Origin on the WebSocket handshake and require a token. Applies directly to our extension bridge |
| browser-use, **CVE-2025-47241** (CVSS 9.3, fixed 0.1.45) | GitHub advisory raw | `allowed_domains` bypassed by a decoy domain in the URL's username part | Compare the parsed hostname, not a substring |

Inference for bap-browser: a browser tool server supplies all three trifecta legs by itself (logged-in pages, untrusted page text, navigation and form submission), the same shape Willison describes for the GitHub server. Comparable products say so openly. Playwright MCP: "Playwright MCP is **not** a security boundary"; its origin lists "*does not* serve as a security boundary and *does not* affect redirects"; its secrets masking "is a convenience and not a security feature" (README, raw). Chrome DevTools MCP: "exposes content of the browser instance to the MCP clients" (raw).

## 6. Defensive tooling and guidance
- **MCP-scan**, Invariant, 2025-04-11 (raw); now Snyk Agent Scan (summarizer). Detects poisoning, rug pulls, cross-origin escalation; "Tool Pinning... tracking changes via tool hashing". It sends tool names and descriptions to an external API.
- **mcp-context-protector**, Trail of Bits, 2025-07-28 (summarizer): proxy with trust-on-first-use pinning, guardrail scanning, ANSI sanitization. Stated limit: alert fatigue.
- **Microsoft, Windows**, David Weston, 2025-05-19 (summarizer): proxy-mediated communication, per client-tool approval, central registry. Registry requirements: "Mandatory code signing", "Servers' definition of tools cannot be changed at runtime", "Security testing of exposed interfaces", "Mandatory package identity", "Servers must declare privileges they require". Developer blog (partial raw): Prompt Shields, spotlighting, datamarking.
- **Docker MCP Toolkit** (summarizer): signed images with SBOM; containers "restricted to 1 CPU" and "limited to 2 GB"; no host filesystem by default. **MCP Gateway** (partial raw): "isolated Docker containers with restricted privileges, network access, and resource usage", with logging and call tracing.
- **Cloudflare** (summarizer): the server "generates and issues its own token to the MCP client"; "Do not log or return the raw access token"; hide tools a user may not call.
- **Official MCP Registry** (raw), in preview: namespace verification through GitHub or DNS. "The MCP Registry **does not** make guarantees about moderation, and consumers should assume minimal-to-no moderation." It will not remove "Servers with security vulnerabilities".
- **Spec SECURITY.md** (raw): "MCP clients trust MCP servers they connect to." Server developers are responsible for access controls, documenting capabilities, validating inputs, least privilege.
- **OWASP** (cross-reference only): MCP Top 10, beta, MCP01:2025–MCP10:2025 (raw). MCP Security Cheat Sheet (raw): "Pin reviewed tool definitions using cryptographic hashes"; "Do not reject non-browser clients solely because they send no Origin header"; "Validate the Host header"; "Treat every tool response as untrusted data"; "extract the required structured data instead of passing raw HTML".
- **OpenAI MCP docs** (partial raw): "Trusting a MCP's developer does not make this safe. For this to be safe you need to trust all content that can be accessed within the MCP."
- **ETDI**, arXiv 2506.01333 (abstract raw): proposal for signed, versioned tool definitions; not part of the spec.
- **Chrome Local Network Access** (partial raw): permission prompt for public sites reaching local addresses, "launching in Chrome 142". The SDK advisory says such prompts are "not a substitute for server-side validation".

## 7. Output size, context flooding, denial of wallet
- Spec: no normative cap on tool results (the researcher's reading). Related rules: servers must "Rate limit tool invocations"; page size "is determined by the server"; schema validators "**SHOULD** apply reasonable bounds".
- **Claude Code** (docs markdown, raw): "Claude Code displays a warning when MCP tool output exceeds 10,000 tokens and limits output to 25,000 tokens by default." Raised with `MAX_MCP_OUTPUT_TOKENS`; "The warning threshold is fixed."
  - Text results over 50,000 characters are saved to a file; a tool may raise this with `_meta["anthropic/maxResultSizeChars"]` "up to a hard ceiling of 500,000 characters".
  - Error text over about 11,000 characters keeps the first and last 5,000.
  - "Claude Code truncates each tool description and each server's instructions at 2,048 characters by default."
- **Anthropic, "Writing effective tools for agents"**, 2025-09-11 (raw): use "pagination, range selection, filtering, and/or truncation with sensible default parameter values"; "For Claude Code, we restrict tool responses to 25,000 tokens by default."
- **Python SDK** (section 8): 4 MiB request body cap; 10,000 sessions; 1,800 s idle timeout.
- Playwright MCP README (raw) says command-line use is "more token-efficient" because it avoids "verbose accessibility trees"; it offers snapshot `depth`, save-to-file, and a find-in-snapshot tool.
- Denial of wallet: OWASP LLM10:2025 could not be read (HTTP 429). Willison, 2026-10-03 (raw), argues for "default hard budget caps"; general, not MCP-specific.

## 8. Python SDK (`mcp`) specifics, all raw from the repo at v2.3.0 and the GitHub advisory API

**DNS rebinding protection: yes, built in.**
- `TransportSecuritySettings` has `enable_dns_rebinding_protection: bool = True`, `allowed_hosts` and `allowed_origins` (both empty lists by default).
- When `transport_security` is `None` and `host in ("127.0.0.1", "localhost", "::1")`, the app builders arm it with `allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"]` and `allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]`.
- Default `host` is `"127.0.0.1"`. Bad Host gives `421`; bad Origin gives `403`. A missing `Origin` is accepted. POST requires `Content-Type: application/json`.
- Traps:
  1. Docs: "Passing a non-localhost `host=`... does **not** allowlist that hostname. It only stops the localhost default from arming the protection, which leaves every Host and Origin accepted."
  2. If the middleware is built directly with no settings, protection is off (code comment: "disable DNS rebinding protection by default for backwards compatibility").
  3. The default origin list trusts a page on any localhost port (the researcher's reading of the pattern). We can narrow it to our own port.
  4. "Custom routes are **never authenticated**, even when the rest of the server is... Don't put anything private behind one." This matters for viewer routes on the same app.
- Authorization: the SDK is resource-server only (`TokenVerifier` plus `AuthSettings`). "None of this protects `stdio`." Audience checking (`validate_token_resource`) is off unless set.
- Request-state tokens are sealed with a per-process `os.urandom(32)` key and a 600 s lifetime.
- Legacy session IDs are `uuid4().hex`.
- "The **WebSocket transport**... It was never part of the MCP specification" and is removed in v2. Our extension bridge is therefore our own code with no SDK protection.

**Advisories** (2.3.0 includes every fix):

| ID | Issue | Fixed in |
|---|---|---|
| CVE-2025-53366 | FastMCP validation error, denial of service | 1.9.4 |
| CVE-2025-53365 | Unhandled exception in Streamable HTTP, denial of service | 1.10.0 |
| **CVE-2025-66416** (CVSS 4.0 7.6) | "DNS Rebinding Protection Disabled by Default... for Servers Running on Localhost" | 1.23.0 |
| **CVE-2026-52869** (7.1) | "HTTP transports serve session requests without verifying the authenticated principal" | 1.27.2 |
| CVE-2026-52870 | Experimental task handlers let any client access others' tasks | 1.27.2 |
| **CVE-2026-59950** | "WebSocket server transport does not support Host/Origin validation"; "a web page served from any origin could open a WebSocket to a reachable MCP server" | 1.28.1 |
| GHSA-fmmv-w9g8-j3gc (7.5, no CVE listed) | Request bodies read with no size limit | 1.29.1 / 2.1.0 |
| **CVE-2026-59951** (7.5) | Sessions "never reclaimed by default"; "Authentication limits who can open sessions, not how many a token holder can open." | 1.30.0 / 2.2.0 |
| GHSA-w4fh-qvv9-3v23 (6.8, no CVE listed) | Bearer auth accepts tokens for another resource; "**Upgrading alone changes nothing.**" | 1.30.0 / 2.2.0 |
| GHSA-qx49-fqc8-xw99, GHSA-5h93-6whr-6q8j, GHSA-rwrf-2pqf-9j8j | Client-side: credentials sent to a server-chosen authorization server; cross-origin redirects; `$ref` fetching | 1.30.0 / 2.2.0 |

## (a) Server-side checklist for a server like ours
1. Validate `Origin` on every HTTP request; 403 when present and not allowed; accept a missing Origin. Source: transport spec; CVE-2025-66416; CVE-2025-9611; OWASP cheat sheet.
2. Validate `Host`; 421 otherwise. Source: SDK `TransportSecuritySettings`; Oligo.
3. Pass an explicit `transport_security` narrowed to our port and origins, and never rely on the default once `host` is not loopback. Source: SDK deploy docs.
4. Bind to 127.0.0.1, never 0.0.0.0, by default. Source: transport spec; NeighborJack.
5. Require the token on every MCP request even on loopback. Source: "Binding to 127.0.0.1 is not an authentication boundary"; CVE-2025-49596.
6. Token only in the `Authorization` header, never in a URL; 401 when wrong; never logged or returned; stored securely. Source: authorization spec; Cloudflare.
7. Authenticate the viewer routes separately, because SDK custom routes are never authenticated. Source: SDK asgi docs.
8. On the extension WebSocket: check `Origin` against our extension ID, require a secret, and consider per-connection approval. Source: CVE-2025-52882; CVE-2026-59950; Playwright extension README ("you'll need to approve each connection"; token "unique to your browser profile").
9. Browser-context handles: random, opaque, expiring, checked on every call, never treated as authentication. Source: State Handle Hijacking; Stateful Tools.
10. For legacy clients: random session IDs, idle timeout, session cap, 404 for a different principal. Source: 2025-11-25 rules; CVE-2026-52869; CVE-2026-59951.
11. Send and check `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`; reject mismatches with 400. Source: Streamable HTTP spec. The SDK handles this.
12. Cap request body size (SDK default 4 MiB, 413). Source: GHSA-fmmv-w9g8-j3gc.
13. Rate limit tool calls and bound concurrency. Source: tools spec.
14. Validate every tool input against a strict schema; return validation errors as tool errors. Source: tools spec; 2025-11-25 changelog.
15. Never build shell strings or unresolved paths from arguments; compare parsed hostnames for any domain allowlist. Source: CVE-2025-53967; CVE-2025-68144; CVE-2025-53109/-53110; CVE-2025-47241.
16. Sanitize tool output: no raw HTML, strip control characters including `0x1b`, label page text as untrusted data, extract structured fields. Source: tools spec; Trail of Bits; OWASP cheat sheet.
17. Cap every observation and offer paging or filtering, staying well under 25,000 tokens and 50,000 characters per result. Source: Claude Code docs; Anthropic guidance.
18. Keep descriptions and server instructions under 2,048 characters, factual, with no instructions about other tools. Source: Claude Code docs; Invariant; MPMA.
19. Keep tool definitions stable at runtime, in a deterministic order, the same for every connection. Source: tools spec; Windows requirement; rug-pull research.
20. Set annotations honestly: page-reading and navigation tools are open-world and not read-only when they change page state. Never rely on annotations for safety. Source: schema; MCP blog 2026-03-16.
21. Never ask for passwords or tokens through form elicitation; typed secrets stay out of results, logs and model context. Source: elicitation spec.
22. stdio: nothing but protocol messages on stdout; credentials from the environment. Source: stdio and authorization specs.
23. Do not forward a client's token to any upstream service. Source: token passthrough rule.
24. Keep an audit log of tool, time and outcome, with secrets redacted. Source: OWASP cheat sheet; MCP08:2025.
25. Publish under a verified namespace with pinned, signed releases, and document the one official install command. Source: Postmark incident; registry docs.
26. Track SDK advisories and upgrade promptly. Source: SDK SECURITY.md.
27. If we ever leave loopback: OAuth resource-server mode with RFC 9728 metadata, audience validation (`validate_token_resource=True`), short-lived tokens, per-user identity. Source: authorization spec; GHSA-w4fh-qvv9-3v23.
28. State in the docs that the server is not a security boundary against a hostile page, and what it does and does not protect. Source: Playwright and Chrome DevTools MCP disclaimers.

## (b) Client and host controls to document for agents that connect to us
1. Keep a human able to deny tool calls; show the full inputs before calling. Source: tools spec.
2. Treat our annotations as hints unless the host trusts our server. Source: tools spec.
3. Pin our tool definitions by hash and re-prompt on change. Source: Trail of Bits; Invariant; OWASP cheat sheet.
4. Treat every result from us as untrusted data, because it carries web page text. Source: OWASP cheat sheet; OpenAI docs.
5. Do not combine us, in one session, with tools holding private data and a way to send it out, unless approval is on. Source: Willison; MCP blog.
6. Prefix our tool names with a server identifier. Source: tools spec.
7. Send the token only in the header; store it in the OS credential store; keep it out of committed config. Source: authorization spec; Trail of Bits.
8. Use HTTPS for any non-loopback URL; do not follow redirects that downgrade. Source: authorization spec; SDK deploy docs.
9. Set tool-call timeouts and output limits. Source: tools spec; Claude Code docs.
10. Strip terminal escape codes before showing our output. Source: Trail of Bits.
11. Show the exact launch command before first run; run third-party servers isolated, with a pinned version. Source: SEP-1024; Local Server Security.
12. Log tool use. Source: tools spec.
13. Validate our structured results against the output schema; never fetch network `$ref`s. Source: tools spec; basic spec.

## (c) Pages that could not be read
- CyberArk, "Poison everywhere: No output from your MCP server is safe": every URL redirects to a Palo Alto Networks marketing page; archive.org returned 403 and 429. Only a search snippet was used.
- Koi Security's Postmark article: redirects to a Palo Alto Networks page. Replaced by Postmark's own statement.
- OWASP LLM10:2025 Unbounded Consumption: HTTP 429 twice.
- Asana's own notice: not public.
- Not attempted for lack of budget: the Aim Labs, Cymulate and Cyata write-ups (only CVE records read), Cloudflare's MCP portal docs, the second half of the client-registration page, and the full text of several long pages marked partial above.
- Every page marked "summarizer" was read through an extracting model, so its quotes are unverified against the source.

## Sources (kind; date; how read)
Spec and project, all raw:
- https://modelcontextprotocol.io/specification/versioning (spec)
- https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices (spec guidance; fully read)
- https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices (Session Hijacking section only)
- https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/local-server-security (fully read)
- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http, `/stdio`, `/index` (fully read)
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports and `/2025-06-18/` (security and session sections)
- https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization (index and security-considerations fully; discovery read; client-registration first half)
- https://modelcontextprotocol.io/specification/2026-07-28/server/tools (key sections); schema.ts in the spec repo (ToolAnnotations)
- `/client/elicitation`, `/client/sampling`, `/basic/index`, `/server/utilities/pagination`, `/server/resources` (normative lines only)
- `/specification/2026-07-28/index`, `/changelog` (fully read); 2025-11-25 changelog (selected lines)
- https://modelcontextprotocol.io/seps/1024-mcp-client-security-requirements-for-local-server- (Final, created 2025-07-22; fully read)
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/SECURITY.md; https://modelcontextprotocol.io/community/security
- https://modelcontextprotocol.io/registry/about and `/registry/moderation-policy`
- https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization (one section)
- https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/ (2026-03-16; about three quarters read)

Python SDK, raw:
- https://github.com/modelcontextprotocol/python-sdk at v2.3.0: `src/mcp/server/transport_security.py`, `mcpserver/server.py`, `streamable_http_manager.py`, `docs/run/deploy.md`, `authorization.md`, `asgi.md`, `legacy-clients.md`, `whats-new.md`, `SECURITY.md`
- https://github.com/modelcontextprotocol/python-sdk/security/advisories (through the API; six read in full)
- CVE.org record API and GitHub advisory API for every CVE above

Research and vendor:
- https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks (research; 2025-04-01; raw, about two thirds)
- https://invariantlabs.ai/blog/whatsapp-mcp-exploited (2025-04-07; raw, partial)
- https://invariantlabs.ai/blog/introducing-mcp-scan (2025-04-11; raw)
- https://invariantlabs.ai/blog/mcp-github-vulnerability (2025-05-26; raw)
- https://invariantlabs.ai/blog/toxic-flow-analysis (2025-07-29; raw, partial)
- https://github.com/invariantlabs-ai/mcp-scan (summarizer)
- https://blog.trailofbits.com/2025/04/21/jumping-the-line-how-mcp-servers-can-attack-you-before-you-ever-use-them/ (summarizer)
- https://blog.trailofbits.com/2025/04/23/how-mcp-servers-can-steal-your-conversation-history/ (raw, partial)
- https://blog.trailofbits.com/2025/04/29/deceiving-users-with-ansi-terminal-codes-in-mcp/, `/2025/04/30/insecure-credential-storage-plagues-mcp/`, `/2025/07/28/we-built-the-security-layer-mcp-always-needed/` (summarizer)
- https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ (raw, full); `/2025/Apr/9/mcp-prompt-injection/` (raw, partial); `/2026/Oct/3/default-hard-budget-caps/` (raw, full)
- https://www.generalanalysis.com/blog/supabase-mcp-blog (2025-07-08, reviewed 2026-09-06; raw, partial); https://supabase.com/docs/guides/getting-started/mcp (summarizer)
- https://www.bleepingcomputer.com/news/security/asana-warns-mcp-ai-feature-exposed-customer-data-to-other-orgs/ (third-party; 2025-06-18; raw, partial); https://www.upguard.com/blog/asana-discloses-data-exposure-bug-in-mcp-server (summarizer)
- https://www.oligo.security/blog/critical-rce-vulnerability-in-anthropic-mcp-inspector-cve-2025-49596 (summarizer; its date of 2025-06-27 is unverified); https://www.oligo.security/blog/0-0-0-0-day-exploiting-localhost-apis-from-the-browser (raw, partial)
- https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/ (2025-07-09); https://jfrog.com/blog/mcp-prompt-hijacking-vulnerability/ (2025-10-21) (summarizer)
- https://postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package (2025-09-25; summarizer)
- https://blog.gitguardian.com/breaking-mcp-server-hosting/ (2025-10-22); https://www.imperva.com/blog/another-critical-rce-discovered-in-a-popular-mcp-server/ (2025-10-07); https://research.checkpoint.com/2025/cursor-vulnerability-mcpoison/ (2025-08-05); https://www.backslash.security/blog/hundreds-of-mcp-servers-vulnerable-to-abuse (2025-06-25) (all summarizer)
- https://arxiv.org/abs/2505.11154 (summarizer); https://arxiv.org/html/2503.23278v3 (raw, table); https://arxiv.org/abs/2506.01333 (raw, abstract)
- https://blogs.windows.com/windowsexperience/2025/05/19/securing-the-model-context-protocol-building-a-safer-agentic-future-on-windows/ (summarizer); https://developer.microsoft.com/blog/protecting-against-indirect-injection-attacks-mcp (raw, partial; date not captured)
- https://docs.docker.com/ai/mcp-catalog-and-toolkit/toolkit/ (summarizer); `/mcp-gateway/` (raw, partial)
- https://developers.cloudflare.com/agents/model-context-protocol/authorization/ (summarizer)
- https://owasp.org/www-project-mcp-top-10/ (raw); https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html (raw)
- https://code.claude.com/docs/en/mcp (raw, selected lines); https://www.anthropic.com/engineering/writing-tools-for-agents (2025-09-11; raw, partial)
- https://developers.openai.com/api/docs/mcp (raw, partial)
- https://github.com/microsoft/playwright-mcp and the Playwright extension README; https://github.com/ChromeDevTools/chrome-devtools-mcp; https://github.com/github/github-mcp-server (raw, selected lines)
- https://developer.chrome.com/blog/local-network-access (2025-06-09, updated 2025-09-29; raw, partial)
