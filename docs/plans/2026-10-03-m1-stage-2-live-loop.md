# Milestone 1, Stage 2: Live Loop — Implementation Plan

**Goal:** One command runs a basic agent loop against a real browser while the viewer shows every step live and a person can pause, take over and stop it. This is the first check of the whole path: agent, tools, browser, events, pictures, viewer, controls.

**Architecture:** The agent loop and the core share one process, the way an agent core does inside the micro VM. The tool layer reports each step to an observer. A session object holds the event history, the control state and the subscribers. A Starlette app serves the built viewer, a WebSocket with events and picture frames, and a small demo site. The viewer gets a WebSocket connection beside its recorded one.

**Tech Stack:** As stage 1, plus Starlette and uvicorn (already in the stack; they become direct dependencies). The hosted model's SDK is not added in this plan: the loop is built against a small model interface with a scripted model, and the hosted model plugs in once its provider and dependency are agreed.

**Spec:** `docs/bap-browser-spec.md` sections 4.5 (who is driving), 4.6, 4.7, 4.8 (protocol and event fields), 4.10, 9.7 (timeline sentences), 10.3 (`agent`, `viewer`), 14.1 slice 4, 16.5 (the reference agent loop).

## Global Constraints

- Everything in the Global Constraints of the stage 1 plan still holds.
- Event names and fields are exactly those of spec 4.8 and `viewer/src/protocol.ts`. The viewer is not changed to fit the service; the service fits the protocol.
- Typed text never appears in an event: a typing step carries a character count.
- A sentence shown in the timeline is under 60 characters; an element's name inside it is cut to fit.
- The service listens on `127.0.0.1`. Every API route and the WebSocket need the token; the WebSocket also checks `Origin`. The token never appears in a log, an event or a tool result.
- While a person drives or the session is paused, an agent's tool call waits (`control.hold_timeout_s`), then returns the plain message of spec 4.5, not an error. After Stop every call returns "The session was ended by a person."
- Nothing reaches the agent while a person drives: no snapshot and no result of what the person did.
- No new dependency beyond `starlette` and `uvicorn` without asking.

## Interfaces fixed by this plan

```
tools/observer.py     StepObserver (Protocol)
                        step_started(step: int, tool: str, label: str, target: Box | None) -> None
                        step_finished(step: int, ok: bool, ms: float, chars: int, summary: str, url: str) -> None
tools/sentences.py    label_for(tool, args, target_name) -> str        'Clicking "Create account"'
                      summary_for(tool, args, target_name, ok, result) -> str   'Clicked "Create account" (button)'
driver/base.py        Box(x, y, w, h); Located(name: str, box: Box | None)
                      Driver.locate(ref) -> Located
                      Driver.start_frames(on_frame: Callable[[bytes], None], level: QualityLevel) -> None
                      Driver.stop_frames() -> None
                      Driver.pointer(action, x, y, button) / key(action, key) / wheel(x, y, dx, dy)
service/events.py     EventHub(history: int): publish(event: dict) -> None; subscribe() -> (history, queue); unsubscribe(queue)
service/session.py    ServiceSession(config, driver=None): toolkit, hub, control
                        handle(command: dict) -> None      pause, resume, take_over, hand_back, stop, pointer, key, wheel
                        start() / close()
service/app.py        create_app(config, sessions, token) -> Starlette
agent/models.py       Model (Protocol): async complete(system, messages, tools) -> Reply
                      Reply(text: str, tool_calls: list[ToolCall]); ToolCall(id, name, arguments)
                      ScriptedModel(steps); demo_script() -> ScriptedModel
agent/loop.py         async run_agent(task, toolkit, model, settings, on_text) -> str
viewer connection     SocketConnection(url, token) implements Connection
```

## Tasks

Each task is test first, with the real browser and the real transport wherever the stage 1 rules ask for it.

- [x] **Task 1: Configuration and packaging.** `agent` section and `viewer.picture_heartbeat_s` in `config.py`; `starlette` and `uvicorn` declared in `pyproject.toml`; the built viewer and the demo site included in the package (`viewer_dist/`, `demo_site/`, copied from `viewer/scripts/demo_site/`). Tests: the new defaults match the spec; `agent.provider` accepts only what this build contains (`scripted`).
- [x] **Task 2: Step sentences and the observer.** `Driver.locate`; `sentences.py` for the four tools (labels, summaries, failures as "Could not …: reason", names cut to keep rows under 60 characters); `Toolkit` reports each call to a `StepObserver`. Tests with the fake driver: started then finished, in order, numbered from 1; a typing step never carries its text; a failed step says why; a blocked navigation still produces a step.
- [ ] **Task 3: Session, events, control.** `EventHub` with a bounded history; `ServiceSession` publishes `session_started`, `control_changed`, `step_*`, `tab_changed`, `navigation_blocked`, `session_ended`; control states `agent`, `paused`, `person`, `ended` gate tool calls as spec 4.5 says; on hand-back the agent's next result starts with the change note. A subscriber always gets `session_started` first; when the bounded history has dropped events, the current `control_changed` and `tab_changed` follow it (spec 4.8). Tests with the fake driver: each command, the hold time-out message, Stop, history replay for a late subscriber, and a replay after the history has overflowed.
- [ ] **Task 4: Live pictures and a person's input.** CDP screencast with frame acknowledgement, capped at the quality level's `max_fps`, JPEG; `picture_current` every `viewer.picture_heartbeat_s` while nothing changes; `pointer`, `key`, `wheel` sent to the page. Tests on the test site: frames are JPEG and arrive after a page change; a still page produces heartbeats; a remote click ticks the checkbox; remote typing fills the field; none of it reaches the event log as text.
- [ ] **Task 5: The service.** Starlette app: the viewer's files, `/healthz`, `/api/sessions`, the WebSocket (auth as first message, a refused token closes it with code 4401, `Origin` check, history, the newest picture, `caught_up` with `ts`, events as text, frames as one type byte plus JPEG, commands in), `/demo-site/`. Tests: no token or a wrong one is closed with 4401 and receives nothing; a wrong `Origin` is refused; a late viewer gets the history, the newest picture, then `caught_up`; a frame arrives as binary; `stop` ends the session.
- [ ] **Task 6: The agent loop.** `Model` interface, `ScriptedModel`, `run_agent`, the demo script (sign up on the demo site by reading refs from the snapshot). Tests: the loop stops at a reply with no tool call, at `agent.max_steps`, and when the session is stopped; a tool error goes back to the model as a result; end to end on the demo site with the scripted model.
- [ ] **Task 7: `bap-browser agent`.** Starts the service on a free port, prints the viewer address (token in the fragment) to the error stream, runs the loop, prints the answer; `--demo` uses the scripted model and the demo site; `--exit-when-done` ends the process after the run. Test: the real command with `--demo --exit-when-done` exits 0 and leaves the steps in the event log and no browser behind.
- [x] **Task 8: The viewer's live connection.** `SocketConnection`: auth, events, frames as object URLs (a finished step comes with its own kept picture, a replaced live picture is released), commands, reconnect with growing delays, a refused token (close code 4401) is not retried, the session clock. Nothing replayed is shown as new. `main.tsx` plays a recorded session for `?state=` or `?demo=`, connects when the address carries a token, and otherwise shows the link-refused screen. Tests with a scripted WebSocket, and the refused screen in a real browser.
- [ ] **Task 9: The whole path.** A test starts `bap-browser agent --demo`, opens the served viewer in a real browser, and sees: "Agent is working", steps arriving, the picture drawn, Pause and Resume acting on the real session, Take over and Hand back, then the summary. Screenshots saved as proof.

## Verification for the whole plan

```bash
npm --prefix viewer run typecheck && npm --prefix viewer run lint && npm --prefix viewer run test && npm --prefix viewer run build
uv run ruff format --check . && uv run ruff check . && uv run pyright
uv run pytest -q
uv run bap-browser agent --demo        # then open the printed address and watch
```
