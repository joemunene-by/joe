# joe

A local-first agent shell for your Mac. joe-gemma orchestrates, qwen-coder
delegates the actual code-writing, and a tool protocol gives both filesystem
+ shell access. Everything lives under `~/.joe-agent/`; nothing leaves the
machine unless you ask it to (ntfy push, web search, HTTP bridge).

This document is the complete reference. Read once, keep it open in a
second window the first week, then use `/help` from inside joe for quick
lookups.

---

## install summary

Binaries live in `~/.local/bin/`:

```
joe              the interactive shell (this is the main one)
joe-agent        legacy one-shot wrapper (chat/pr/standup subcommands)
joe-listen       record + transcribe via whisper.cpp
joe-speak        macOS say wrapper, strips markdown/tool tags first
joe-schedule     launchd wrapper for arbitrary scheduled shell commands
joe-http         FastAPI server exposing joe over the LAN + /ios endpoint
joe-mcp          MCP server exposing joe to Claude Code
joe-index        builds the per-repo RAG vector index
joe-watch-logs   tails log files, alerts on errors/milestones via LLM
joe-proactive    watches zsh history for retry patterns and idle stretches
```

Update with `joe self-update` (default source: `ghostlm-linux:/tmp/joe`).

Quick health check:

```
joe doctor
```

Green checks across ollama models (joe-gemma, qwen2.5-coder, nomic-embed-text),
helper binaries, ntfy topic, history-index. Sets the baseline you can trust.

---

## starting a session

```
joe                              start the REPL
joe -p "summarise today"         one-shot, exit when done
joe -s morning                   resume session 'morning'
joe --coder qwen2.5-coder:7b     pick a different delegate
joe --image bug.png "what's wrong here?"
```

Inside the REPL you'll see a status line above every prompt:

```
─ joe-20260512-153012  joe-gemma  ~/GhostLM  ctx ~2840  tasks:1 ─
```

Session id, model, cwd, rough token count, plus flags (`yolo`, `speak:Alex`,
running background tasks).

---

## the four input prefixes

joe parses your input by its first character before treating it as a chat
message.

| Prefix | Meaning                                                                |
| ------ | ---------------------------------------------------------------------- |
| `/`    | slash command (no model call)                                          |
| `&`    | background task (`&python train.py` runs detached, gets a task id)     |
| `@`    | switch cwd to that active repo for this turn (`@GhostLM run pytest`)   |
| `@@`   | run this turn under a named subagent persona (`@@reviewer review .`)   |
| `///`  | open multi-line input mode; another `///` on its own line closes it    |
| (none) | normal chat message; goes to joe-gemma with full tool access           |

Tab completion (via `prompt_toolkit`) covers all four: slashes, repo names,
agent names, and file paths after `/read`, `/diff`, `/explain`, `/attach`,
`/test`, `/lint`, `/build`, `/run`.

Up/down arrows give you input history across every session, persisted to
`~/.joe-agent/input-history`.

---

## slash commands

### session control

```
/help                  the menu
/exit, /quit           leave
/cwd [path]            show or change working dir
/model [name]          switch orchestrator model
/coder [name]          switch the code-delegate model
/clear                 wipe screen + start a fresh session
/save <name>           rename the current session
/load <name>           resume a saved session
/sessions              list the 20 most recent sessions
/fork <new-name>       copy current session under a new name
/share [session]       export to markdown in ~/.joe-agent/exports/
/compact               summarise the oldest half of the session
/yolo                  toggle JOE_AUTO_YES for this REPL
/whoami                model / profile / repo / RAG / ntfy summary
/cost                  context-budget meter with color bar
/doctor                run the dependency health check
```

### files + shell

```
/read <path>           syntax-highlighted file preview
/run <cmd>             allow-listed bash one-liner
/diff [path]           git diff for path (or whole repo)
/copy [N]              pbcopy the Nth code block of the latest answer
/history [N]           last N write/edit operations
/undo [N]              revert the last N writes/edits (also captures a lesson)
/redo [N]              re-apply the last undone change
```

### code workflow

```
/plan <task>           multi-step plan with approval per step
/test [path]           pytest/cargo test/npm test/go test (auto-detect)
/lint [path]           ruff/clippy/eslint/tsc/govet (auto-detect)
/build [path]          auto-detect build command
/explain <path>        route the file to the coder for a structured summary
/profile               print the active per-repo profile
/review                joe-gemma reviews the current git diff, ends with
                       SHIP | FIX-FIRST verdict
/blame <path>:<line>   show which prompt/model/agent produced that code
```

### git + github

```
/commit [subject]      draft commit message from staged + unstaged diff,
                       confirm, then `git add -A && git commit -m`
/push [remote]         push current branch (default: origin)
/pr <sub>              list | view N | comment N "text" | review N | create
/issue <sub>           list | view N | comment N "text" | new | close N
/snap <sub>            save | restore | list | drop  (tar repo state)
```

### subagents

```
/agents                list named personas
@@reviewer review .    run a turn under the reviewer persona
@@security audit ...   etc.
```

Seeded personas live in `~/.joe-agent/agents/`:

```
reviewer.toml      Critical / Style / Tests / Followups markdown report
doc-writer.toml    READMEs / CHANGELOGs in your voice
security.toml      OWASP-style audit, per-finding shape
explainer.toml     onboard a new reader to unfamiliar code
```

Drop new TOMLs into the same folder to add your own:

```toml
description = "release manager"
model = "joe-gemma"
coder = "qwen2.5-coder:14b"
auto_yes = false
system_prompt = """
You are my release manager. ...
"""
```

### background + scheduling

```
&<cmd>                 spawn <cmd> as a tracked background task
/tasks                 list all background tasks
/task <id>             show one task (cmd, pid, status, tail of log)
/task kill <id>        SIGTERM a running task
```

Tasks live in `~/.joe-agent/tasks/<id>.{json,log}`. When `NTFY_TOPIC` is
set, a phone push fires the moment a task exits, plus a local osascript
banner. Tasks survive the parent joe process exiting, but only the
notification depends on joe still running.

For fully-detached recurring jobs use `joe-schedule`:

```
joe-schedule add nightly-distill --at 23:00 --command "joe lessons distill"
joe-schedule add proactive --interval 86400 --command "JOE_PROACTIVE=1 joe-proactive --autostart"
joe-schedule list
joe-schedule show nightly-distill
joe-schedule run nightly-distill           # fire now
joe-schedule remove nightly-distill
```

### voice + vision + journal

```
/listen [--duration N]   record (silence-detect auto-stop) + transcribe +
                          send as the next user message
/speak [voice|off|text]  toggle auto-TTS, set voice, or speak text once
/paste                   attach the clipboard image to the next turn
/attach <path>           attach an image file to the next turn
/journal [text]          today's journal (auto-seeded with the last 24h of
                          commits across active repos); with text, append
                          a time-stamped note
```

### memory + lessons

```
/recall <query>          top-K semantically similar past turns from all
                          sessions (cross-session RAG)
/lessons <sub>           list | add "<rule>" | drop <n> | distill | review
/timer <minutes> [label] pomodoro; macOS notification + spoken alert when done
```

### misc

```
/web <query>             DuckDuckGo HTML search
/fetch <url>             fetch + strip HTML to text
/tools                   show the XML tag protocol the model uses
/repos                   list active repos joe knows about
/recall, /review,        (see above)
```

---

## the tool protocol (what the model can do)

The model emits XML tags; joe parses, executes, and feeds the result back
as `<tool_result>`. The loop caps at 8 turns.

```xml
<read path="..." />
<write path="...">content</write>
<edit path="..."><old>X</old><new>Y</new></edit>
<bash>cmd</bash>
<grep pattern="..." path="..." />
<glob pattern="..." />
<delegate model="qwen2.5-coder:7b">spec</delegate>   simple tasks
<delegate model="qwen2.5-coder:14b">spec</delegate>  complex tasks
<test path="..." />
<lint path="..." />
<build path="..." />
<web_search query="..." />
<web_fetch url="..." />
<plan title="...">numbered steps</plan>
<image path="..." />
```

Bash runs against an allow-list by default (`find/grep/ls/cat/git/gh/
python3/npm/pnpm/bun/cargo/ruff/pytest/uv/...`). `joe --unsafe-bash` lifts
it for the session.

For writes, joe shows a unified diff (with `+adds / -dels` summary) and
asks to confirm. `JOE_AUTO_YES=1` or `/yolo` auto-approves.

---

## subsystems worth knowing

### cross-session memory (RAG over your own chat history)

Every (user, assistant) pair gets embedded via `nomic-embed-text` and
stored in `~/.joe-agent/history-index.sqlite`. At the start of each new
turn, the top-3 semantically similar past turns are injected as
`<past_turns>` context (only if similarity >= 0.35; silent otherwise).

Use `/recall <query>` to search this directly.

### lessons-learned loop

When you `/undo`, joe records the (user_msg, what-joe-did, before-state)
into `~/.joe-agent/lessons.sqlite` as a candidate "user rejected" event.
Add manual lessons with `/lessons add "<rule>"`.

```
/lessons distill
```

Reads the last 14 days of events, asks joe-gemma to produce up to 10
short imperative rules ("Always run pytest after editing src/", "Prefer
double quotes in TS files"), deduplicates against existing rules, and
appends new ones to the active set.

Active rules are injected into every turn as `<learned_preferences>` at
the top of the prompt. Over time joe drifts toward your taste without
any retraining. Long-term path: when the supplement file gets meaty,
fold it into a LoRA on joe-gemma (you've already got the training
pipeline).

Schedule a nightly distill:

```
joe-schedule add lessons-distill --at 23:00 --command "joe lessons distill"
```

### provenance / AI-blame

Every successful `<write>` and `<edit>` stamps `(ts, path, op, session,
model, agent, user_msg, line_start, line_end, +adds/-dels)` into
`~/.joe-agent/provenance.sqlite`.

```
joe blame ~/GhostLM/src/foo.py
joe blame ~/GhostLM/src/foo.py:42
/blame src/foo.py:42         # same, inside the REPL
```

Tells you which prompt under which agent on which session produced that
code. Way better than `git blame` for AI-generated changes because it
shows *intent*, not just the most recent commit author.

### macros

Record sequences of slash commands and chat lines, replay with one
command.

```
/macro record morning
/standup
/journal
/diff
/review
/macro stop
/macro list
/macro run morning
```

Stored in `~/.joe-agent/macros/<name>.toml`. The recorder skips inputs
that start with `/macro` so you can stop recording without polluting the
script.

### per-repo profiles

`.joe-profile.toml` at a repo root (walked up from cwd), or
`~/.joe-agent/profiles/<repo-name>.toml` as fallback:

```toml
default_coder = "qwen2.5-coder:14b"
default_base = "main"
lint_cmd = "ruff check ."
test_cmd = "pytest"
build_cmd = "python3 -m build"

context_extra = """
GhostLM: small LM training and chat-tuning.
Always run pytest after edits in ghostlm/.
"""
```

`joe init` (run in a fresh repo) scans the repo, detects language /
lint / test / build commands, runs a style fingerprint (line length,
indent, quote style, naming convention), and writes the profile for you.
It also builds the initial RAG index for that repo. Skip the slow
parts with `--no-index` or `--no-style`.

### codebase style fingerprint

`joe init` scans up to 120 source files and measures:

- average + p90 line length
- indent style (tabs vs spaces, modal width)
- quote style (single vs double)
- naming convention (snake_case vs camelCase)
- comment density (sparse / moderate)
- average function length

It folds the result into `context_extra` so the coder delegate matches
existing convention instead of imposing a generic one.

### auto-test-on-edit

Set `JOE_AUTO_TEST=1` in the env. After every successful `<write>` or
`<edit>`, joe runs the profile's `test_cmd` and shows the tail in a
panel. Fast feedback without you typing `/test` each time.

### watch mode

```
joe watch                       watch cwd, debounce 2s
joe watch ~/GhostLM --debounce 3
```

`fswatch` loop: on file change, runs lint + test, fires a macOS
notification when both finish.

### auto-summarise (avoid context overflow)

`/cost` shows a meter against your `num_ctx` budget (default 131072 from
joe-gemma's Modelfile). When you cross ~80%, `/compact` asks joe-gemma
to summarise the oldest half of the session into one synthetic system
turn and rewrites the session DB to (summary + recent). You don't lose
the chronology of recent work.

### background log watching

```
joe-watch-logs ~/Desktop/GhostLM/runs/latest/train.log \
  --label "v0.9.34 retrain" \
  --interval 60
```

Tails files via `tail -F`. Fast-path regexes (errors, NaN, OOM, "saved
checkpoint", "epoch done", "deploy successful") fire instant alerts.
Every `--interval` seconds, the LLM second-pass checks the recent batch
and decides BORING vs INTERESTING. Hits push to ntfy + osascript.
`--no-llm` for rules-only. `--rule '<regex>'` adds your own.

### proactive helper

```
JOE_PROACTIVE=1 joe-proactive
```

Watches `~/.zsh_history` (or `$HISTFILE`). Detects:

- same command repeated within `--repeat-window` seconds
- idle gap longer than `--idle` (default 15 min)
- any `--trigger '<regex>'` you add

Nudges with a low-priority osascript banner offering a paste-able joe
one-liner. Opt-in: pass `--autostart` if running from launchd; the
daemon exits unless `JOE_PROACTIVE=1` is set, so you can wire it into
`joe-schedule` without it always being on.

### iOS bridge

```
joe ios-setup
```

Prints the complete Shortcut recipe with your real LAN IP and auth
token already substituted. The flow:

1. Start `joe-http` on the Mac.
2. On your phone, create an iOS Shortcut with one "Get Contents of URL"
   action: `POST http://<mac-ip>:8765/ios` with JSON body
   `{"prompt": "<Ask for Text>", "ntfy": "<your-ntfy-topic>"}`.
3. Subscribe to that ntfy topic in the ntfy.sh iOS app.

When the Shortcut posts, joe-http accepts immediately (202) and runs
joe-agent in the background; when it's done, the answer arrives as a
ntfy push on your phone.

Outside the LAN: front joe-http with Tailscale (best) or a Cloudflare
Tunnel. Do not open port 8765 to the public internet.

### MCP server

```
joe-mcp
```

Exposes joe's tools (ask, search_repos, pr_draft, standup) to Claude
Code via the Model Context Protocol. Wire it into Claude Code's MCP
config and you can drive joe (and via joe, your Mac) from any Claude
Code session.

---

## environment variables

```
NTFY_TOPIC               phone-push topic for tasks + watchers + ios
JOE_AUTO_YES=1           auto-approve every write/edit/bash
JOE_AUTO_TEST=1          run profile test_cmd after every successful edit
JOE_SHELL_HISTORY=1      inject last 10 zsh history lines as <recent_shell>
JOE_PROACTIVE=1          required for joe-proactive --autostart to run
JOE_VOICE                default macOS voice for joe-speak (Samantha)
JOE_RATE                 default speech rate (200)
JOE_EMBED_MODEL          embedding model (default: nomic-embed-text)
JOE_NUM_CTX              context budget for /cost meter (default: 131072)
JOE_SELF_UPDATE_FROM     scp/http source for `joe self-update`
JOE_HTTP_TOKEN           override joe-http's bearer token
```

Add the always-on ones to `~/.zshrc`:

```sh
export NTFY_TOPIC=joe-<something-unique>
export JOE_AUTO_TEST=1
```

---

## state layout

Everything joe owns lives under `~/.joe-agent/`:

```
joe-sessions.sqlite        chat history per session
history-index.sqlite       cross-session embeddings (nomic-embed-text)
provenance.sqlite          AI-blame log
lessons.sqlite             corrections / undos / manual rules
prompt-supplement.md       free-form additions joined to every turn
http-token                 bearer token for joe-http
input-history              REPL input history (prompt_toolkit)

agents/                    subagent .toml personas
profiles/                  per-repo profile .toml fallbacks
journal/YYYY-MM-DD.md      daily journals
exports/                   session markdown exports
edits/<sha>                content-addressed blobs for undo/redo
tasks/<id>.{json,log}      background task state + captured output
snaps/<name>.tar.gz        repo snapshots (/snap save)
macros/<name>.toml         recorded macro scripts
pastes/                    clipboard images captured via /paste
standups/                  joe-agent generated standup files
voice/                     kept WAV recordings (--keep-wav)
```

Nuking state is just `rm -rf ~/.joe-agent/<thing>`. Safe to delete any
of these; joe will recreate empty defaults.

---

## representative recipes

### morning routine

Define once:

```
/macro record morning
/standup
@@reviewer review .
/journal Up. coffee. let's go.
/macro stop
```

Then every morning:

```
/macro run morning
```

### pre-commit

```
/review                              # SHIP | FIX-FIRST verdict
/commit                              # auto-draft message in your style
/push
```

### long training run

On the Mac, kick the run and the watcher in parallel:

```
&PYTHONPATH=. python3 scripts/train_v0_9_34.py --steps 200000
joe-watch-logs ~/Desktop/GhostLM/runs/latest/train.log --label "v0.9.34"
```

Close the laptop. The watcher pings your phone (ntfy) on errors,
milestones, or completion.

### code refactor across multiple files

```
/plan refactor the auth middleware to use the new TokenStore
```

joe drafts a numbered plan, asks for approval, then drives each step
with checkpoints between. Per step it delegates code to the 14b coder,
shows the diff, runs your test_cmd, and pauses for the next step.

### audit a fresh PR

```
gh pr checkout 1234
@@security audit this branch
@@reviewer review the diff
```

### "I keep typing this huge prompt"

```
/macro record dailyhealth
/run gh run list --limit 5
/diff
/test
/macro stop
```

Now `/macro run dailyhealth` whenever you want to sanity-check before a
demo.

---

## fixing things

`joe doctor` is the first stop. Common misses:

```
ntfy topic                set NTFY_TOPIC in ~/.zshrc, restart shell
prompt_toolkit missing    /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m pip install --user prompt_toolkit
ollama models missing     ollama pull <name>
joe-listen / joe-speak    brew install whisper-cpp sox pngpaste fswatch
```

If joe stops mid-loop with "Same tool call emitted twice in a row":
the model got stuck. Tell it explicitly what to do differently and
retry. The same-call detector is intentional.

If a `<write>` writes to `path/to/file.py`: the model used a placeholder.
joe rejects placeholders. Re-prompt with the real absolute path.

If `joe blame` says `(no provenance)`: the code pre-dates joe, was
written by something else, or path resolution mismatched. The provenance
log only stamps writes that go through joe's tool path.

To wipe a session: `/clear` (starts a new session id) or `/save <name>`
to archive then `/clear`.

To wipe lessons: `rm ~/.joe-agent/lessons.sqlite`. To wipe everything:
`rm -rf ~/.joe-agent/`.

---

## the outstanding-features layer

These are the seven features that take joe past "comprehensive" and into
"this is yours and only yours" territory. Each one leverages the
infrastructure you already have (M4, GhostLM, multiple repos, ntfy, ML
training pipeline) and is not in any other CLI agent.

### 1. self-training (joe train)

joe collects your accepted answers + corrections, builds a JSONL training
set, and either bakes the lessons into a fresh ollama Modelfile or
launches a real LoRA on Apple Silicon.

```
joe train collect              gather sessions + lessons into JSONL
joe train modelfile [version]  rebuild joe-gemma:vYYYYMMDD with the
                                top examples + lessons baked in (fast,
                                ollama-only path)
joe train lora                 invoke mlx-lm.lora to actually fine-tune
                                gemma3:4b with your accepted examples
                                (real path, ~1-2h on M4)
joe train activate <ver>       record joe-gemma:<ver> in the state dir;
                                set JOE_DEFAULT_MODEL=joe-gemma:<ver>
                                in ~/.zshrc to flip the default
```

JSONL output lands in `~/.joe-agent/training-data/jsonl-*.jsonl`. The
schema is OpenAI chat format so the same file feeds either path.

Nightly distill + weekly rebuild:

```
joe-schedule add weekly-train --interval 604800 \
  --command "joe lessons distill && joe train collect && joe train modelfile"
```

### 2. smart inbox (joe inbox)

One panel covering: PRs requesting your review, issues mentioning you,
failing CI runs across every active repo, running background tasks,
recent prompt-supplement updates.

```
joe inbox
/inbox          (same, inside the REPL)
```

Prioritized P0 (red, action-required) -> P3 (dim, informational). Add to
your morning macro:

```
/macro record morning
/inbox
/standup
/macro stop
```

### 3. self-eval (joe eval)

Catches when your local models regress.

```
joe eval build [N]        snapshot N past prompts + their accepted answers
joe eval run [model]      rerun the eval set against current joe-gemma,
                          score answers by embedding similarity vs gold
joe eval report           trend line across past runs, deltas highlighted
```

Schedule weekly so you know when retraining hurts:

```
joe-schedule add weekly-eval --interval 604800 \
  --command "joe eval run && joe eval report"
```

A negative delta means the current model answers less like your accepted
gold than last time. Investigate the supplement, the Modelfile, or the
LoRA you just merged.

### 4. live pair-programming (joe-pair)

```
joe-pair                 watch cwd
joe-pair ~/GhostLM       explicit dir
joe-pair --interval 30   minimum seconds between alerts
joe-pair --no-llm        rules + tests only, never call the model
```

Watches your files via fswatch. On each save (debounced), it:

1. Runs the profile's `test_cmd` if defined; failures always alert.
2. Otherwise reads the changed file and asks joe-gemma whether anything
   in it is worth flagging. The model replies SILENT or one short
   sentence (under 140 chars). Silent 90% of the time.

Alerts go to osascript and (with `--topic` or `$NTFY_TOPIC`) to your
phone. joe-pair never writes files; it's strictly a quiet observer.

### 5. knowledge graph (`/ask`)

Every conversation gets parsed into (subject, relation, object) triples
in the background and stored in `~/.joe-agent/knowledge.sqlite`. Triples
are durable facts ("GhostLM uses MLX", "ghostloop launched on 2026-04-30",
"@@reviewer is the persona for code review"); transient state and shell
commands are skipped.

```
/ask what do I know about the GhostLM v0.9 retrain?
/ask which repo uses the linkdrop daemon?
joe ask "what's the difference between qwen:7b and qwen:14b in this setup?"
```

The query hits the graph by term overlap, expands 1-hop, then joe-gemma
synthesises an answer grounded in the matched triples (with citations to
the sessions where each fact came from).

### 6. cross-machine sync (joe sync)

Wrap `~/.joe-agent/` as a git repo and push to a private remote. Joe on
the Mac and joe on the Linux dev box then share one mind.

```
joe sync init <git-url>      first-time setup
joe sync push                publish recent state
joe sync pull                fetch updates from the other machine
joe sync status              what's local vs remote
```

The gitignore is preset to skip noisy state (`edits/`, `tasks/`, `voice/`,
`pastes/`, `snaps/`, `exports/`, `*.log`, the bearer token, the larger
sqlite caches). Sessions, lessons, agents, macros, profile, and the
prompt supplement all sync.

Auto-push every hour:

```
joe-schedule add sync-push --interval 3600 --command "joe sync push"
```

### 7. end-of-day reflection (joe reflect)

At 18:00, joe writes a 2-3 paragraph plain-prose reflection on the day
into `~/.joe-agent/journal/developer-journal.md`. Inputs: today's commits
across active repos, today's `/journal` notes, lessons captured, count of
writes + edits.

```
joe reflect           on-demand
/reflect              same, from REPL
```

Schedule it:

```
joe-schedule add reflect --at 18:00 --command "joe reflect"
```

After three months you have a personal narrative of what you've been
building, in your own voice, with context the average dev journal never
has. Read it on a slow weekend.

---

## what's coming next

Three of the four 2026-vintage open paths shipped (bidirectional MCP
in v0.7.0, /debate in v0.5.0, web dashboard at `joe-http /dashboard`
with full inbox / eval / blame / graph). Frontmost-window Accessibility
is still the one outstanding item.

What landed after the original v0.8.0 doc snapshot:

### v0.9.x — quality + correctness

- `_import_required_or_die` so VSCode-terminal launches no longer die
  with "ModuleNotFoundError: rich"; instead they print the exact
  interpreter path and the right pip line.
- Per-tool session trust: `[y/N/a]` permission prompt; `a` = always for
  this tool, this session. `/trust` for explicit grants + reset.
- Reproducibility passports: sha256 of (model + prompt + cwd + lessons
  + lora endpoint) for every turn. `/passport list`. `/passport replay
  <hash>` re-runs bit-for-bit.
- `/council <prompt>` fires same prompt at 3 local models concurrently
  (joe-gemma + qwen2.5:14b + deepseek-r1:14b) and auto-judges.
- `/blame <file>:<line>` shows AI-provenance (which session / prompt /
  model wrote that line).
- Python AST validation before write + tool-emission repair hints on
  parser failure.
- PC-control suite: `<screen>`, `<click>`, `<type>`, `<key>`, `<open>`,
  `<clipboard>` (Anthropic Computer-Use surface, locally).
- Custom slash commands as TOML at `~/.joe-agent/commands/*.toml`.
- Hooks: shell scripts in `~/.joe-agent/hooks/<event>.sh` for
  pre_tool / post_tool / user_prompt / stop.
- Eval harness: `joe eval add`, `joe eval run`, `joe eval diff <a> <b>`,
  auto-eval daemon on model swap, warn on regression.
- `<parallel>` runs N side-effect-free tools concurrently.
- Per-session cache for read / grep / glob / web_fetch.
- `<browser>` with 9 Playwright actions (open / click / type / wait /
  screenshot / extract / title / url / back / close).
- GitHub Actions test + auto-release pipeline (idempotent release job).
- joe-voice press-to-talk loop (joe-listen + joe -p + joe-speak).

### v0.10.x — everything-agent pack

- Plugin tools: `~/.joe-agent/tools/*.py` with `register()` get a new
  tag in the parser at load time.
- `AGENTS.md` / `CLAUDE.md` / `.joe/instructions.md` auto-loaded as
  `<project_context>` in every system prompt.
- `/diff-model <a> <b> <prompt>` (cheap two-model A/B, no judge).
- `capture_reasoning_trace()` strips and persists `<think>` blocks.
- Inline turn meter: `└ 1247 tok in · 412 tok out · 3.2s · 129 tok/s`.
- `/output-style` with 7 presets + custom `.md` overlays.
- `/statusline <fmt>` customises the bottom-of-REPL bar.
- `<multi_edit>` — atomic N-edits-in-one-tag.
- `<notebook_edit>` — Jupyter .ipynb cell mutations.
- `@path/to/file` in user input auto-injects as `<file>` block.
- Sandbox modes (`read-only` / `workspace-write` / `full`) gate the
  tool dispatcher and refuse writes outside cwd.
- Aider-style `<repo_map>` block per system prompt.
- `/mode act | plan | architect | debug | ask | review | security`
  atomically swaps output-style + sandbox.
- Skills (Claude Code SKILL.md packages). `/skills install <git-url>`
  clones a public skill directly into `~/.joe-agent/skills/`.
- `/loop N <prompt>` and `/loop until <cond> <prompt>` (max 12).
- `/ai-markers` + `/ai-markers fix` for Aider-style `# AI!` comments.

### v0.11.x — user-research polish + safety hardening

- `joe doctor --fix` pip-installs missing deps through the *same*
  interpreter running joe, killing the "rich not found" UX hole.
- `/swarm prompts.txt` fans out N independent agents concurrently.
- Cumulative session $-cost in `/cost` (Claude 4.x / GPT-5 / o3 /
  DeepSeek-V4 priced; local models render `$0 (local)`).
- Auto-compact at 85% context budget; one summarisation per
  ceiling-cross, keeps recent half verbatim.
- `bin/joe-mcp` now exposes 13 tools so MCP clients (Claude Desktop,
  Cursor, Zed) can drive ALL of joe — read_file, write_file,
  blame_line, council, recall, list_passports, replay_passport,
  list_skills, ai_markers_in.
- `bin/joe-watch-ai` daemon: polls cwd for saves, auto-fires `joe -p`
  on detected AI! markers, auto-commits. Aider's headline parity.
- Windows compat shims for `<screen>` (PowerShell + .NET),
  `<open>` (`cmd /c start ""`), and `<clipboard>` (Get-Clipboard +
  `clip`). Core tool surface works on Windows 10+ without modification.
- Knowledge-graph viz in `/dashboard`: newest triples rendered as a
  Mermaid `flowchart LR` (dark theme, lazy-loaded from CDN). Table
  preserved behind a `<details>` toggle.
- Tree-sitter edit guard for 25+ non-Python extensions
  (.js .ts .tsx .rs .go .rb .java .kt .swift .c .cpp .cs .php
  .lua .scala .sh .html .css .json .yaml .toml .sql). Optional dep:
  `pip install tree-sitter-languages` to activate. Same contract as
  the Python AST guard — broken parse refuses the write.
- OS-level `<bash>` jail: macOS `sandbox-exec` with Seatbelt SBPL
  profile; Linux `bwrap` (preferred) / `firejail` fallback. Wraps
  every `<bash>` when `/sandbox read-only` or `/sandbox
  workspace-write` is active so escape-via-subshell is denied at the
  kernel layer. `JOE_OS_SANDBOX=0` opts out; `/sandbox os on|off`
  toggles in REPL.

The remaining bucket is small. Future polish:

- HTTP / SSE transport for `joe-mcp` (FastMCP supports it; a small
  wiring job).
- `joe stats --export csv`.
- `/undo last-N` — atomic rollback of joe's recent writes via the
  provenance log + git reflog.
- Speculative parallel inference for cloud models.
- Voice on Windows (pyttsx3 + Sapi5).

`joe --help` and `/help` are the live source of truth; this doc
captures the model as of v0.11.8.
