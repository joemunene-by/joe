# joe

A local-first, self-personalising agent shell for your machine. Think
Claude Code, but every model runs on your own GPU, every byte of state
sits in `~/.joe-agent/`, and the agent gets better at understanding you
the longer you use it.

```
joe (your terminal)
  ├── orchestrator    joe-gemma             (gemma3:4b, Modelfile-personalised)
  ├── coder delegate  qwen2.5-coder:7b/14b
  ├── planner         deepseek-r1:14b       (optional; used by /plan)
  ├── fast model      qwen2.5:3b            (joe-pair save-watcher, trivials)
  └── tools           read/write/edit/bash/grep/glob/web_search/web_fetch
                      test/lint/build/plan/image/delegate

state under ~/.joe-agent/
  ├── sessions        full chat history per named session
  ├── lessons         /undo corrections, distilled into prompt rules
  ├── provenance      every write/edit stamped with prompt + model + agent
  ├── knowledge       (subject, relation, object) triples from each turn
  ├── agents          named subagent personas, summoned with @@name
  ├── macros          recorded slash-command sequences
  └── (training data, profiles, journals, tasks, snapshots, ...)
```

## why this exists

Cloud agents see your code through a straw. Local agents are starting to
catch up, but most are just chat REPLs with one or two tools bolted on.
joe sits between the two: a real tool-using agent on hardware you own,
with the receipts (provenance, lessons, knowledge graph) to actually
improve over time without retraining.

The seven features that make joe interesting:

1. **AI-blame / provenance** — `joe blame src/foo.py:42` tells you which
   prompt, under which agent, in which session, on which date produced
   that line. Git blame for *intent*.
2. **Lessons-learned loop** — every `/undo` is a signal. `/lessons distill`
   turns recent corrections into 1-line preference rules that get injected
   into the system prompt of every future turn. Auto-evolving personality.
3. **Knowledge graph** — every conversation is parsed into
   `(subject, relation, object)` triples in the background. `/ask` queries
   the graph for grounded answers with session citations.
4. **Smart inbox** — `joe inbox` aggregates PRs awaiting your review,
   issues mentioning you, failing CI runs across active repos, running
   background tasks. One panel.
5. **Self-eval / drift detection** — snapshot your past accepted answers
   as a private benchmark. Rerun weekly against the current model and
   measure how much it has drifted.
6. **Live pair-programming** — `joe-pair` watches your files via fswatch.
   On each save it runs your tests; if they pass, it briefly asks the
   model whether anything in the change is worth flagging. Silent 90% of
   the time.
7. **Self-training** — `joe train collect` builds a JSONL training set
   from your accepted answers + lessons. `joe train modelfile` bakes
   them into a fresh ollama Modelfile (`joe-gemma:vYYYYMMDD`).
   `joe train lora` hands the same data to mlx-lm for a real LoRA on
   Apple Silicon.

Plus the everyday surface: macros, scheduled jobs, cross-session memory,
voice input/output, vision, iOS bridge over ntfy, cross-machine sync
through a private git repo, per-repo profiles with auto-detected style
fingerprints, a web dashboard at `joe-http` for the visual view (with
streaming-SSE chat right in the browser), model auto-promotion when a
freshly-trained candidate beats the current default by a threshold,
time-aware semantic recall ("what was I working on yesterday morning?"),
`joe replay` to step through any past session and rerun prompts against
alternate models, `joe-wake` for always-on "hey joe" voice activation,
and a Tauri menu-bar app for click-to-open access.

## quickstart

Requires Python 3.10+, `ollama` running locally, and macOS for the voice /
notification / launchd bits. Most things work on Linux too if you ignore
those.

```sh
git clone https://github.com/joemunene-by/joe ~/code/joe
cd ~/code/joe
./install.sh                          # symlinks bin/* into ~/.local/bin
ollama pull gemma3:4b
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:14b
ollama pull nomic-embed-text          # for cross-session RAG + eval

python3 -m pip install --user rich prompt_toolkit fastapi uvicorn mcp
joe doctor                            # confirm everything is wired
joe                                   # start the REPL
```

First time you run `joe`, it auto-seeds seven default subagents at
`~/.joe-agent/agents/{reviewer,doc-writer,security,explainer,oncall,release-manager,refactor-specialist}.toml`.
Try one:

```
@@reviewer review the current diff
```

If you'd rather have `joe doctor` install missing pieces for you instead
of installing manually, run `joe doctor --fix` after `./install.sh`. It
pulls missing ollama models and pip-installs missing Python deps.

For a guided tour of the killer features on a sample repo, run
`joe demo`: it creates a fresh project, makes a deliberately-buggy file,
runs `@@reviewer` and `@@security` on it, then walks you through
`/blame`, `/ask`, and `/tasks`. The thing to record a launch GIF of.

## the input prefixes

joe parses your input by its first character before treating it as chat:

| Prefix | Meaning                                                    |
| ------ | ---------------------------------------------------------- |
| `/`    | slash command (no model call)                              |
| `&`    | background task; gets an id, runs detached, pings on exit  |
| `@`    | switch cwd to that active repo for this turn               |
| `@@`   | run the turn under a named subagent persona                |
| `///`  | enter multi-line input (terminate with another `///`)      |

## the slash commands

`/help` inside the REPL shows the live menu. Highlights:

```
/plan <task>         multi-step plan with per-step approval
/review              joe-gemma audits the current git diff
/commit | /push      AI-drafted commit message, then push
/test | /lint | /build  auto-detected for python/rust/node/go
/blame <p>:<line>    AI-blame: prompt/model/agent that produced this code
/lessons distill     turn recent /undo events into prompt rules
/macro record <n>    capture a sequence of inputs; replay with /macro run
/recall <q>          search past sessions by semantic similarity
/ask <q>             query the knowledge graph for a grounded answer
/inbox               PRs / mentions / failing CI / pending tasks
/reflect             write today's developer-journal entry
/snap save|restore   tar repo state to ~/.joe-agent/snaps/
/listen / /speak     voice in/out
/paste / /attach     image attachment for vision
/sync push|pull      cross-machine state sync over git
```

## the tool protocol (what the model can do)

The model emits XML tags; joe parses, executes, and feeds the result
back as `<tool_result>`:

```xml
<read path="..." />
<write path="...">content</write>
<edit path="..."><old>X</old><new>Y</new></edit>
<bash>command</bash>
<grep pattern="..." path="..." />
<glob pattern="..." />
<delegate model="qwen2.5-coder:14b">spec</delegate>
<test path="..." />
<lint path="..." />
<build path="..." />
<web_search query="..." />
<web_fetch url="..." />
<plan title="...">numbered steps</plan>
<image path="..." />
```

By default, bash runs against an allow-list. Pass `--unsafe-bash` or
set `JOE_AUTO_YES=1` to broaden / auto-approve. Reading the threat model
below before flipping either is recommended.

## customising

Three places to leave your fingerprints:

### per-repo profiles (`.joe-profile.toml` at a repo root)

```toml
default_coder = "qwen2.5-coder:14b"
default_base = "main"
lint_cmd = "ruff check ."
test_cmd = "pytest"
build_cmd = "python3 -m build"
context_extra = """
This is the GhostLM training repo. Always run pytest after edits in ghostlm/.
Never touch RESULTS.md by hand; it's auto-generated.
"""
```

Generate a starter with `joe init` — it also scans the repo and bakes a
style fingerprint (indent / quote / naming / line-length) into the
`context_extra` so coder delegates match existing convention.

### subagent personas (`~/.joe-agent/agents/<name>.toml`)

```toml
description = "release manager"
model = "joe-gemma"
coder = "qwen2.5-coder:14b"
auto_yes = false
system_prompt = """
You are my release manager. Run /test and /lint first. If both pass,
draft a CHANGELOG entry, then a release commit, then a tag.
"""
```

Summon with `@@release-manager cut a v0.9.34 from main`.

### lessons supplement (`~/.joe-agent/prompt-supplement.md`)

Free-form markdown that joins every system prompt. Use it for facts
about you and your stack that don't change: "I use ruff format with line
length 88", "in ghostloop, the embedded runtime is the ESP32 build",
etc. `/lessons distill` writes here automatically; `/lessons review`
opens it in `$EDITOR` for cleanup.

## privacy + security

joe is local-first, but the surface area is broad. A few flags to
understand before turning them on:

- **`--unsafe-bash` / `JOE_AUTO_YES=1`** — disables the bash allow-list
  and auto-approves every write/edit/bash. Suitable for a sandboxed VM
  you can throw away; risky on your daily-driver Mac. Off by default.
- **`joe-proactive`** — watches your zsh history file and pops a banner
  when it detects retry patterns. It reads your shell history. Opt-in
  (`JOE_PROACTIVE=1` for the `--autostart` form).
- **`joe sync push`** — syncs `~/.joe-agent/` to a git remote you
  configure. The default `.gitignore` excludes credentials and large
  blobs, but conversation logs (`joe-sessions.sqlite`) DO sync. Use a
  private repo.
- **`joe-http`** — exposes a FastAPI server on a port of your choice.
  Bearer-token auth, no TLS. Bind to `127.0.0.1` for local-only or front
  it with Tailscale for off-LAN access. Never open port 8765 to the
  public internet.
- **iOS bridge** — `joe ios-setup` prints a Shortcut recipe. Pushes go
  through ntfy.sh which is third-party. Use a guessable-but-not-obvious
  topic name (no public listing exists, but topics aren't private by
  design).
- **`/web` and `<web_fetch>`** — scrape DuckDuckGo HTML and arbitrary
  URLs. Your IP is visible to those endpoints.

No network calls happen unless you explicitly invoke a web tool, sync,
ntfy, or the iOS bridge. Conversations stay between you and ollama on
localhost.

## architecture in one paragraph

The orchestrator (joe-gemma) emits XML tool tags; joe's REPL parses each
tag, executes it (write/edit/bash/test/etc.), captures stdout, feeds the
result back as `<tool_result>`, and loops until the model stops emitting
tags or hits an 8-turn cap. Code-writing is delegated to qwen-coder
because the smaller orchestrator handles meta-work better than raw
generation. Cross-session memory uses nomic-embed-text against a
SQLite-backed vector store. The lessons supplement and knowledge-graph
triples are stored separately and merged into every prompt's preamble.

## the web dashboard

`joe-http` exposes a single-page dashboard at `GET /` (or `/dashboard`)
that renders, all in one screen:

- eval-trend sparklines per model (with delta vs previous run)
- the last 10 provenance entries (which prompt / agent produced each write)
- knowledge-graph stats and the 12 newest triples
- active distilled lessons
- recent sessions and background tasks

Auth is the same bearer token as the JSON endpoints, passed via
`?token=<TOKEN>` so browsers can hit it without setting headers:

```
http://localhost:8765/dashboard?token=<from ~/.joe-agent/http-token>
```

Front it with Tailscale to view from your phone on the couch.

## tests

```sh
python3 -m pip install --user pytest
python3 -m pytest tests/ -v
```

34 tests, all offline, no ollama dependency. Covers the tool-call
parser, time-phrase extractor, blob store, subagent loader, lessons +
provenance round-trip, active-repo discovery, and the small math
helpers underpinning embeddings + eval scoring.

## menu-bar app (Tauri)

```sh
cd joe-tauri
cargo tauri dev          # dev build, hot-reload
cargo tauri build        # signed .app in src-tauri/target/release/bundle/macos/
```

Click the menu-bar icon to toggle the dashboard window. Left-click
toggles; right-click opens the menu (Open / Refresh / Quit). The app
reuses your existing `joe-http` server and auth token.

## bidirectional MCP

joe is now both an MCP server **and** a client. As of v0.7.0:

- **server side** (`joe-mcp`): exposes joe's tools (ask, search_repos,
  pr_draft, standup) to any MCP client (Claude Code, Cursor, Continue).
- **client side**: connects to external MCP servers configured at
  `~/.joe-agent/mcp-clients.json` and lets the orchestrator call their
  tools via a `<mcp>` tag.

Setup:

```sh
joe mcp init                  # scaffolds ~/.joe-agent/mcp-clients.json
                              # with filesystem + github sample servers
                              # (both disabled-by-default)
# edit the file, flip `enabled: true` on the servers you want
python3 -m pip install --user mcp   # if you don't already have it
joe                           # at startup, joe connects each enabled server
```

Inside the REPL:

```
/mcp list      # show connected servers + their tools
/mcp reload    # tear down + reconnect after editing the config
```

The orchestrator sees available tools in an `<mcp_tools>` block in its
system prompt and can call them with:

```xml
<mcp server="github" tool="list_repos">{"owner": "joemunene-by"}</mcp>
```

Results come back through the standard `<tool_result>` loop.

### example: joe talking to ghostloop

ghostloop (the robotics-agent sister project) already ships an MCP
server at `examples/mcp_robot.py`. With one config entry in
`~/.joe-agent/mcp-clients.json` joe becomes a client of that server:

```json
{
  "servers": [{
    "name": "ghostloop",
    "transport": "stdio",
    "enabled": true,
    "command": "python3",
    "args": ["/absolute/path/to/ghostloop/examples/mcp_robot.py"],
    "env": {"GHOSTLOOP_PROFILE": "franka_arm", "GHOSTLOOP_BACKEND": "mock"}
  }]
}
```

joe-gemma now sees `move_to`, `pick`, `place`, `scan` etc. in
`<mcp_tools>` and can drive a robot from any prompt. ghostloop's
policy pipeline (geofence, force-cap, human-in-the-loop) still gates
every intent so joe can use the robot but can't bypass safety. Full
sample at `examples/mcp-clients.ghostloop.json`.

## what's not in here yet

The headline open items are shipped. Future polish:

- HTTP transport for MCP clients (currently stdio-only).
- A `joe stats --export csv` flag.
- More piper-tts voices via a per-language `--setup-piper <locale>` flow.

PRs welcome.

## license

MIT.

## acknowledgements

Built by Joe Munene with deliberate use of Claude as a pair-programmer.
The agent's name is incidental; the design takes inspiration from
Claude Code, Aider, and the years of work on local LLMs that made
gemma3:4b + qwen-coder good enough to do this seriously.
