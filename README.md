# joe

A local-first, self-personalising agent shell for your machine. Think
Claude Code, but every model runs on your own GPU, every byte of state
sits in `~/.joe-agent/`, and the agent gets better at understanding you
the longer you use it.

```
joe (your terminal)
  ├── orchestrator    joe-gemma   (gemma3:4b, personalised via Modelfile)
  ├── coder delegate  qwen2.5-coder:7b / 14b
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
fingerprints.

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

First time you run `joe`, it auto-seeds four default subagents at
`~/.joe-agent/agents/{reviewer,doc-writer,security,explainer}.toml`.
Try one:

```
@@reviewer review the current diff
```

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

## what's not in here yet

- Linux feature-parity for the macOS-specific paths (osascript, say,
  pbpaste, fswatch -> inotify, launchd -> systemd-user). Most of the
  agent works on Linux; the assistive bits don't.
- Auto-installer for ollama models.
- A web dashboard (FastAPI on `joe-http` could render inbox / blame /
  graph in one pane).
- Bidirectional MCP (joe driving Claude Code and vice-versa via the
  same tool set).
- Multi-agent debate mode.

PRs welcome on any of these.

## license

MIT.

## acknowledgements

Built by Joe Munene with deliberate use of Claude as a pair-programmer.
The agent's name is incidental; the design takes inspiration from
Claude Code, Aider, and the years of work on local LLMs that made
gemma3:4b + qwen-coder good enough to do this seriously.
