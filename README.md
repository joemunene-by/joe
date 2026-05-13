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

### example: joe ↔ ghostloop (bidirectional)

joe pairs naturally with [ghostloop](https://github.com/joemunene-by/ghostloop),
the embodied-agent runtime. Both directions of the loop are now wired:

**direction 1 — joe drives ghostloop** (joe as MCP client, ghostloop as MCP server).
ghostloop ships `examples/mcp_robot.py` as an MCP server. Drop one entry into
`~/.joe-agent/mcp-clients.json`:

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

joe-gemma now sees `move_to`, `pick`, `place`, `scan` etc. in `<mcp_tools>` and
can drive the robot from any prompt. ghostloop's policy pipeline (geofence,
force-cap, human-in-the-loop) still gates every intent so joe can use the
robot but can't bypass safety. Full sample at
`examples/mcp-clients.ghostloop.json`.

**direction 2 — ghostloop uses joe-gemma as its policy brain** via the
OpenAI-shaped shim on `joe-http`:

```sh
# on the box running joe:
joe-http --host 0.0.0.0          # exposes /v1/chat/completions + /v1/models

# on the box running ghostloop:
OPENAI_BASE_URL=http://<joe-host>:8765/v1 \
OPENAI_API_KEY=$(ssh <joe-host> cat ~/.joe-agent/http-token) \
OPENAI_MODEL=joe-gemma \
    python3 examples/direct_llm_arm.py
```

joe-http proxies ollama's already-OpenAI-compatible endpoint, with two
additions worth the indirection:
  1. **personalisation injection** — the active lessons supplement gets
     prepended as a system message when the caller doesn't supply one,
     so ghostloop's `LLMPolicy` inherits your distilled preferences.
  2. **bearer auth + cross-machine access** — ollama only listens on
     localhost; joe-http can be exposed over LAN or Tailscale, so
     ghostloop on another machine can reach joe-gemma without exposing
     ollama directly.

Sample ghostloop runner at `examples/ghostloop-uses-joe.py`.

## the v0.9.x engineer-grade pack

Six rounds shipped that push joe past "chat REPL with tools" into "real
terminal coding agent that an Anthropic engineer would scroll up over."

### v0.9.5 — per-tool session trust

Claude-Code-style permission prompts. Every confirm now accepts a third
answer:

```
Apply this write to ./README.md? [y/N/a]:
  y -- yes, this call only
  N -- no (default)
  a -- always (this tool, this session)
```

Trust is scoped per-tool, so `a` to a write doesn't trust bash. `/trust`
shows + resets state; `/trust all` grants session-wide consent (close to
`/yolo` but revocable). Synonyms for `a`: `always`, `trust`, `all`.

### v0.9.6 — reproducibility passport + /council + /blame

**Passport** — every model call stamps a sha256 of `(model + prompt +
cwd + sorted active lessons + LoRA endpoint)` into
`~/.joe-agent/passports.sqlite`.

```
/passport list                   # newest 20 (hash, ts, model, preview)
/passport show <hash-prefix>     # full input space + response
/passport replay <hash>          # re-run the exact prompt bit-for-bit
```

The hash is the natural identity for "this exact input space." Anthropic
engineers know determinism is hard; having a passport for every turn is
the difference between toy and tool.

**`/council`** — concurrent multi-model arbitration. Fires the same
prompt at `joe-gemma + deepseek-r1:14b + qwen2.5:14b` in parallel threads
(override via `$JOE_COUNCIL='m1,m2,m3'`), shows them side-by-side in
Rich Columns with per-model latency, then asks a fourth judge model
(`$JOE_COUNCIL_JUDGE`) which one is best. Winner logged to evals.sqlite.

**`/blame <file>:<line>`** — git-blame for AI provenance. Surfaces the
prompt, agent, model, session, line range, and ±deltas that wrote that
line. The capture has always happened; v0.9.6 surfaced it one slash away.

Plus tool-emission repair hints (parser failures get specific feedback
fed back — "your `<write>` opened at char 42 but never closed"), AST
validation on Python writes (broken syntax blocked before disk hit), and
a "Scope discipline" system-prompt section that stops joe from polishing
files it just `<cd>`'d into.

### v0.9.7 — agentic PC control + custom commands + hooks

joe sees and acts on the host machine. Seven new XML tools:

```xml
<screen />                          <!-- captures display, attaches as
                                         image to next turn; joe-gemma
                                         is gemma3 vision-capable -->
<click x="500" y="300" button="left" clicks="1" />
<type>literal text at focus</type>
<key>cmd+s</key>                    <!-- hotkey or single key -->
<open>app-or-url</open>             <!-- launches via open/xdg-open/start -->
<clipboard op="get" />              <!-- read system clipboard -->
<clipboard op="set">text</clipboard>
```

Each gated by `/trust click`, `/trust type`, etc. Screenshots via
`screencapture` (macOS) / `gnome-screenshot` / `scrot`. Mouse + keyboard
via pyautogui (optional dep). Clipboard via pbpaste/pbcopy / xclip /
wl-paste.

**Custom slash commands** — drop a TOML file at
`~/.joe-agent/commands/<name>.toml`:

```toml
description = "Senior security review"
template = """
Review {{args}} in {{cwd}} as of {{date}}.
Focus on: thread safety, SQL injection, auth bypass, secrets in git.
Be specific.
"""
model = "joe-gemma"               # optional override
allowed_tools = ["read", "grep"]  # optional restriction
```

Type `/review src/auth.py` and joe renders the template + runs a turn.
Substitutions: `{{args}}`, `{{cwd}}`, `{{date}}`. `/commands` lists them;
`/commands reload` re-reads from disk.

**Lifecycle hooks** — shell scripts in `~/.joe-agent/hooks/<event>.sh`
fire on:

```
user_prompt   non-zero EXIT cancels the turn
pre_tool      non-zero EXIT BLOCKS the tool + feeds stderr back to model
post_tool     non-blocking; receives result via env
stop          after turn completes
```

Hooks receive `JOE_HOOK_EVENT`, `JOE_HOOK_TOOL`, `JOE_HOOK_TOOL_ARGS`,
`JOE_HOOK_TOOL_BODY`, `JOE_HOOK_TOOL_RESULT`, `JOE_HOOK_USER_MSG`,
`JOE_HOOK_RESPONSE`, `JOE_HOOK_CWD`, `JOE_HOOK_SESSION`, `JOE_HOOK_MODEL`
via env. Mirrors Claude Code's hook surface so admin policies port
straight over.

### v0.9.8 — eval diff + auto-eval on swap

```
joe eval diff <model-a> <model-b>   # per-case head-to-head: wins /
                                    # losses / ties + score deltas
joe eval cases                      # list the current eval set
```

Auto-eval kicks in a daemon thread when the REPL's model changes (via
`/model <name>`). Runs the eval set against the new model, compares to
the previous model's most recent run, fires a desktop notification if
avg-similarity drops by >0.02.

### v0.9.9 — `<parallel>` + deterministic-tool cache

```xml
<parallel>
  <read path="src/a.py" />
  <read path="src/b.py" />
  <grep pattern="def login" path="." />
</parallel>
```

Fans the children out concurrently via ThreadPoolExecutor (max 8
workers). Children restricted to side-effect-free tags: `<read>`,
`<grep>`, `<glob>`, `<web_fetch>`. Single-child short-circuits to direct
dispatch (no thread overhead).

Plus a per-session result cache for those same four tools keyed by
`(tool, attrs, body prefix, cwd)`. Repeated reads of the same file or
greps for the same pattern return instantly with a `[cache hit]` marker.

### v0.9.10 — Playwright `<browser>`

Real headless Chromium driven by a persistent Playwright session per
REPL:

```xml
<browser action="open" url="https://github.com/joemunene-by" />
<browser action="click" selector="a[href='/joemunene-by/joe']" />
<browser action="extract" selector=".repository-content" />
<browser action="screenshot" path="/tmp/joe-repo.png" />
<browser action="close" />
```

Other actions: `type`, `wait`, `title`, `url`, `back`. Cookies + login
persist across actions in one REPL. Headed via `JOE_BROWSER_HEADED=1`.
Optional dep — refuses with an install hint if Playwright isn't present:

```sh
pip install --user playwright && playwright install chromium
```

Combined with `<screen>` + `<click>` from v0.9.7, joe drives both a
headless browser (websites + scraping + automation) AND the user's actual
desktop (window automation). That's the full Anthropic-Computer-Use
surface, on local hardware, with /trust-gated consent.

## v0.10.x — everything-agent pack

Eight more rounds after v0.10.0 brought joe to feature parity with
Claude Code, Codex, Cursor, Aider, and Cline / Roo Code, while keeping
the local-first, byte-of-state-in-`~/.joe-agent/` model.

### v0.10.1 — plugin tools + AGENTS.md / CLAUDE.md auto-load

Drop a `.py` file in `~/.joe-agent/tools/` exporting a `register()` that
returns `{name: handler}`. The parser regenerates after load so the
new tag is recognised. Plugins cannot override built-in tools.

```python
# ~/.joe-agent/tools/jira.py
def jira_handler(attrs, body):
    return f"JIRA-{attrs['key']}: ..."
def register():
    return {"jira": jira_handler}
```

Plus: when joe enters a cwd with `AGENTS.md` (OpenAI Codex convention),
`CLAUDE.md` (Claude Code convention), or `.joe/instructions.md`, the
content gets injected as `<project_context>` into every system prompt.

### v0.10.2 — /diff-model + reasoning trace + turn meter

`/diff-model <a> <b> <prompt>` is the cheap two-model A/B without the
judge spend of `/council`. `capture_reasoning_trace()` strips
`<think>...</think>` blocks from streaming output, persists each to
`think.sqlite`, returns the clean response. `/think show <hash>`
surfaces past reasoning. Every model turn ends with an inline meter:

```
└ 1247 tok in ·   412 tok out ·  3.2s ·  129 tok/s
```

### v0.10.3 — output styles + statusline + multi_edit + notebook_edit

Seven built-in output-style presets (`/output-style concise`, `learning`,
`security`, `review`, `ship-it`, …) overlay the system prompt. Custom
`.md` files at `~/.joe-agent/output-styles/<name>.md` extend the set.
`/statusline <fmt>` lets you write a Rich-markup format string that
replaces the default bottom-of-REPL bar.

New tools: `<multi_edit>` (Claude Code MultiEdit equivalent — atomic
N-edit-in-one-tag with single diff preview); `<notebook_edit>` for
.ipynb cells with replace / append / insert / delete ops.

### v0.10.4 — @-mentions + sandbox modes

```
> @src/auth.py what's wrong here?
```

joe auto-prepends `<file path="src/auth.py">...</file>` to the prompt
before the model sees it. Cursor / Continue.dev pattern. Multiple
`@path` tokens, dedup, trailing-punctuation strip, 30 KB cap per file.

Sandbox modes (Codex-inspired): `read-only`, `workspace-write`, `full`.
`/sandbox <mode>` at the prompt; `--sandbox <mode>` at CLI; or
`$JOE_SANDBOX`. The dispatcher blocks tools not allowed at the current
level, and `workspace-write` additionally refuses writes outside cwd.

### v0.10.5 — repo map + mode switching

Aider-style repo map: every system prompt now contains a
`<repo_map>` block with a per-file symbol table (def / class / fn /
struct / trait / type) for Python, TypeScript, Rust, Go. Capped at
~5 KB so it doesn't blow the context budget on monorepos. Refreshed
every 60s per cwd.

Mode switching (Cline / Roo Code): `/mode act | plan | architect |
debug | ask | review | security` atomically swaps both
`/output-style` and `/sandbox`. So "plan the change" → `/mode plan`
(explanatory + read-only); "now make it real" → `/mode act` (ship-it
+ full).

### v0.10.6 — skills + /loop

**Skills** (Claude Code SKILL.md packages). Drop a directory at
`~/.joe-agent/skills/<name>/` with `SKILL.md`:

```markdown
---
name: pr-review
description: Senior code review with security focus
when_to_use: review, audit, check for bugs, vulnerabilities
allowed_tools: read, grep, glob, parallel
---
<body of skill instructions...>
```

joe loads all skills at REPL start. Every turn, it matches the user
message against each skill's `when_to_use` triggers and injects matched
skills as `<skill_available>` blocks. Joe-autonomous: the model picks
them up when relevant, no explicit invocation. Different from `/<name>`
custom commands (user-typed) and `@@<persona>` subagents (explicit
dispatch).

`/loop 5 fix the next lint warning` repeats a turn 5 times.
`/loop until DONE finish the refactor` iterates up to 12 times until
the response contains "DONE" (case-insensitive). Useful for "keep
going until tests pass" or "apply this to every model file."

### v0.10.7 — AI! markers + /skills install

Aider's signature feature: leave a comment marker in your code:

```python
def parse_csv(text):
    # AI! refactor this to use the csv module
    return [line.split(",") for line in text.split("\n")]
```

```
/ai-markers       scan cwd, list every marker with file:line
/ai-markers fix   run a turn per marker; addresses + removes the
                  marker line
```

Marker styles recognised: `# AI!`, `// AI!`, `<!-- AI! ... -->`,
`; AI!`, `-- AI!`. Skips node_modules, target, .venv, .git etc.

Plus `/skills install <git-url>` clones a SKILL.md package directly
from a public repo into `~/.joe-agent/skills/`. Validates the dir
name as `[a-zA-Z0-9_-]+`; refuses if target exists; reloads the
skill registry after install so it's active in the same REPL.

## v0.11.x — user-research polish + safety hardening

Eight more rounds after the v0.10.x parity pack. v0.11.0 was a docs
release; v0.11.1 onward each shipped a piece of either competitive
parity or hardening surfaced by the "what do developers want from
terminal AI agents in 2026" survey + competitor mining.

### v0.11.1 — doctor --fix + /swarm + cumulative cost

`joe doctor --fix` iterates over runtime deps (rich, prompt_toolkit,
fastapi, uvicorn, mcp, pyautogui, playwright) and pip-installs any
missing one through the *same* interpreter that's running joe, so
the "ModuleNotFoundError: rich" UX disappears for good.

`/swarm prompts.txt` reads N lines (one prompt per line) and fires
each as an independent agent in a fresh session, concurrently, up to
8 threads. A result table renders per-agent success / failure +
preview. Latency drops from `sum(individual)` to `max(individual)`.

`/cost` now shows cumulative $-spend per session based on the new
`MODEL_PRICES_PER_MTOK` table (Claude 4.x family, GPT-5, o3,
DeepSeek-V4-Pro:cloud). Local models render as `$0 (local)` so the
"free" signal is loud.

### v0.11.2 — auto-compact at 85%

Every REPL iteration estimates current session tokens. When the
ratio crosses 85% of `CONTEXT_BUDGET_TOKENS`, `_auto_compact()`
summarises the oldest half via the current model with a
preserve-decisions-files-open-questions prompt, replaces it with one
system turn, keeps the recent half verbatim. Context drops from
~87% to ~30-40% with the conversation's useful state intact. Fires
once per ceiling-cross (a `_warned_compact` flag prevents thrash).

### v0.11.3 — native MCP server: every joe tool exposed

`bin/joe-mcp` was a four-tool MCP server (ask, search_repos,
pr_draft, standup). It now exposes thirteen so any FastMCP-aware
client (Claude Desktop, Cursor, Zed, Cline) can drive joe fully:

```
ask         search_repos    pr_draft     standup
read_file   write_file      blame_line   council
recall      list_passports  replay_passport
list_skills ai_markers_in
```

`write_file` goes through joe-agent so the write is stamped to the
provenance log and AST-validated. A Claude Desktop user can now say
"use joe's `council` to compare joe-gemma vs deepseek-r1 on this
question" and joe IS the server doing it.

### v0.11.4 — joe-watch-ai daemon (Aider parity)

A long-running daemon that polls the cwd for file saves and, on
detection of a `# AI!` / `// AI!` / `<!-- AI! -->` marker, shells
out to `joe -p` to fix and remove the marker, then optionally
`git commit`s the result.

```
joe-watch-ai                 # daemon mode, polls every 2s
joe-watch-ai --once          # one pass + exit
joe-watch-ai --path src      # subtree
joe-watch-ai --dry-run       # show what would fire
joe-watch-ai --no-commit
```

Leave it running in a side terminal while you work; flag spots with
marker comments; joe attends to them in the background. This is the
always-on companion to the manual `/ai-markers fix`.

### v0.11.5 — Windows compat shims

joe was Linux + macOS only. v0.11.5 boots on Windows with native
fallbacks for the platform-dependent tools:

```
<screen>     macOS screencapture -> Linux gnome-screenshot/scrot
             -> Windows PowerShell + .NET (System.Windows.Forms +
             Drawing) -> pyautogui last resort
<open>       macOS open -> xdg-open -> Windows `cmd /c start ""`
<clipboard>  pbpaste/pbcopy -> xclip/wl-* -> Windows PowerShell
             Get-Clipboard (read) and `clip` (write, ships with
             every Windows since XP)
```

No service-mode install yet, but the core tool surface works without
modification on Windows 10+.

### v0.11.6 — knowledge-graph viz in /dashboard

The web dashboard's KG block used to render the newest triples as
plain text. v0.11.6 also renders them as a Mermaid `flowchart LR`
graph, loaded lazily from the CDN with a dark theme that matches
the rest of the dashboard. The original triple table is preserved
behind a `<details>` toggle.

### v0.11.7 — tree-sitter-aware edit guard

v0.9.6's Python `ast.parse` validation refuses `.py` writes that
don't parse. v0.11.7 extends the same contract to every non-Python
language joe can recognise:

```
.js .cjs .mjs .jsx   -> javascript
.ts                  -> typescript           .tsx -> tsx
.rs                  -> rust
.go                  -> go                   .rb  -> ruby
.java                -> java                 .kt  -> kotlin
.swift               -> swift
.c .h                -> c                    .cpp -> cpp
.cs .php .lua .scala .sh .bash
.html .css .json .yaml .toml .sql
```

When `tree-sitter-languages` is installed, broken non-Python writes
get refused with a line:col error string the model can use to retry.
The dep stays optional: absent => silent skip, same as before.

### v0.11.8 — OS-level <bash> sandbox

The Python-layer sandbox modes in v0.10.4 gated which tools the
dispatcher would invoke. But `<bash>` was a hole: a clever model
could shell out via `echo foo > /etc/whatever` and Python never
saw the redirect. v0.11.8 closes that hole with an OS-native jail
around every `<bash>` when the mode is restricted:

```
macOS   -> sandbox-exec -p <SBPL profile> sh -c <cmd>
Linux   -> bwrap --ro-bind / --tmpfs /tmp --chdir <cwd> ...
            (firejail --read-only=/ ... fallback)
other   -> silent passthrough; Python-layer checks still apply
```

In `read-only` mode the jail denies file-write* everywhere except
`/tmp` and `/dev/null`. In `workspace-write` it additionally
re-allows writes under the cwd subpath. In `full` mode the
wrapper is a no-op — the user picked unrestricted on purpose.

```
JOE_OS_SANDBOX=0      # disable globally
/sandbox os on|off    # REPL toggle
/sandbox              # status panel shows which jail is active
```

The Bash panel title prepends the wrapper label so the user can
see at a glance: `Bash (macOS Seatbelt)`, `Bash (linux bwrap)`,
`Bash (linux firejail)`, or just `Bash` (no wrapping).

## tool registry (26 tags)

| tag | what it does | side effects |
|---|---|---|
| `<read>` | read file or dir listing | none (cached) |
| `<write>` | write file (Python AST-validated) | disk write |
| `<edit>` | regex find-and-replace in file | disk write |
| `<bash>` | shell command (allow-list unless `--unsafe-bash`) | varies |
| `<cd>` | persistent cwd change (accepts project aliases) | session state |
| `<grep>` | recursive text search | none (cached) |
| `<glob>` | filename pattern search | none (cached) |
| `<delegate>` | spawn coder model (qwen2.5-coder:7b/14b) | model call |
| `<test>` | auto-detect + run pytest/cargo/npm test | execution |
| `<lint>` | auto-detect + run ruff/clippy/eslint/tsc | execution |
| `<build>` | auto-detect + run build command | execution |
| `<web_search>` | DuckDuckGo HTML search | network (cached) |
| `<web_fetch>` | fetch + HTML→text | network (cached) |
| `<plan>` | multi-step plan with approval | model orchestration |
| `<image>` | attach image to next turn | session state |
| `<mcp>` | call a connected MCP server | external |
| `<screen>` | capture screen, attach to next turn | display flash |
| `<click>` | mouse click at (x, y) | input device |
| `<type>` | typewrite at focus | input device |
| `<key>` | hotkey / single key | input device |
| `<open>` | launch app or URL | desktop launch |
| `<clipboard>` | get/set system clipboard | clipboard |
| `<parallel>` | fan-out N side-effect-free tools | concurrency |
| `<browser>` | Playwright Chromium driver | browser session |
| `<multi_edit>` | atomic N-edits-in-one-tag (CC MultiEdit equiv) | disk write |
| `<notebook_edit>` | Jupyter .ipynb cell mutations | disk write |

## what's not in here yet

The headline open items shipped through v0.11.8. Future polish:

- HTTP / SSE transport for `joe-mcp` (currently stdio-only; FastMCP
  supports SSE so this is a small wiring job).
- A `joe stats --export csv` flag.
- More piper-tts voices via a per-language `--setup-piper <locale>` flow.
- `/undo last-N` — atomic rollback of joe's recent writes via the
  provenance log + git reflog cross-walk.
- Speculative parallel inference: for high-latency cloud models, fire
  2-3 variants in parallel and pick the first valid one.
- Voice on Windows (joe-voice currently macOS-first; pyttsx3 + Sapi5
  is the obvious port).

PRs welcome.

## license

MIT.

## acknowledgements

Built by Joe Munene with deliberate use of Claude as a pair-programmer.
The agent's name is incidental; the design takes inspiration from
Claude Code, Aider, and the years of work on local LLMs that made
gemma3:4b + qwen-coder good enough to do this seriously.
