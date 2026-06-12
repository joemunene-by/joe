# Changelog

The headline feature per release. Full git log between tags has more.

## v0.12.2 — bake proven skills into the model

`joe train collect` now also emits chat-format training records for skills
that earned their place: injected at least once and net-positive (wins >
losses) per the v0.12.1 ledger. The on-device LoRA learns the procedures
that actually worked, not just raw accepted turns. This closes the full
loop: synthesise from wins -> measure against /undo -> prune the failures ->
train on the survivors.

- `proven_skills()` / `skill_training_records()` select and format the
  survivors; records match the existing `{"messages": [...]}` shape so the
  modelfile and LoRA pipelines consume them unchanged.
- `joe train collect` reports a new "skill records" count.
- 5 new tests in `tests/test_skill_training.py`, all offline.

## v0.12.1 — skill effectiveness ledger: close the loop

Synthesis (v0.12.0) writes skills from wins. This release measures whether
they help. Every time a skill is injected into a turn it is logged; a usage
is a "win" unless an `/undo` landed in the same session within the same hour
(the heuristic `train collect` already uses), in which case it is a "loss".

- `joe skill review` / `/skills review` — per-skill ledger (uses, W/L,
  synth-vs-installed).
- `joe skill prune [apply]` / `/skills prune [apply]` — archive synthesized
  skills that never trigger or go net-negative (losses > wins) under
  `skills/_archived/` so the loader stops injecting them. Dry-run by default;
  only ever touches synthesized skills, never ones you installed.
- Synthesized skills now carry a `.synth` provenance marker.
- 9 new tests in `tests/test_skill_ledger.py`, all offline.

## v0.12.0 — skill synthesis: joe learns from wins, not just corrections

joe's lessons loop already learns from every `/undo` (corrections). Skill
synthesis is the mirror image: it learns from successful sessions. After a
multi-step task that worked, joe distils the session transcript into a
reusable `SKILL.md` package under `~/.joe-agent/skills/<slug>/`, which the
existing skill loader auto-injects into future matching turns. This is the
Voyager "ever-growing skill library" loop, local-first, with no retraining.

- `joe skill synth [session]` — synthesise a skill from a session (defaults
  to the most recent one).
- `/skills synth [session]` — same, from inside the REPL, then hot-reloads.
- The orchestrator returns either `NONE` (nothing reusable) or a `SKILL.md`;
  output is validated by the canonical parser before it is written, and an
  existing slug is never clobbered (`<slug>-2`, `<slug>-3`, ...).
- 14 new tests in `tests/test_skill_synth.py`, model call stubbed so the
  suite stays offline.

## v0.11.12 — docs sync (v0.11.10 + v0.11.11)

- README.md grows new sections for **v0.11.10** (secrets guardrail)
  and **v0.11.11** (codebase RAG + linter ACI + microagent compat).
- "what's not in here yet" rewritten with the prioritised 13-item
  backlog surfaced by the 2026-landscape sweep — OTLP, full LSP loop,
  `response_schema` on `/plan`, shadow-git checkpoints, OpenHands
  condenser, `.aiignore`, architect-pair, SWE-bench trajectory export,
  plus the older HTTP-MCP / undo / speculative / Windows-voice items.
- JOE.md mirrors the same content under its v0.11.x retrospective.

## v0.11.11 — landscape-sweep batch: RAG + linter ACI + microagent compat

A deep mine of 2026's OSS coding-agent ecosystem (Goose, OpenHands,
SWE-agent, Open Interpreter, Cody, gptme, Continue, Warp, Zed, OpenCode,
JetBrains, Cline/Roo checkpoints) surfaced three near-free wins. All
three ship here.

- **Codebase vector RAG** auto-injects top-K chunks from the `joe-index`
  vector store under cwd into every turn's system prompt. The
  infrastructure existed since the v0.4-era `joe-index` binary; this
  wires it into the chat loop the same way Cursor's `@codebase`,
  Cody's agentic context, and Continue's `@codebase` do. New
  `repo_rag_query` + `repo_rag_block` helpers in `bin/joe`. Gated on
  `JOE_AUTO_RAG=1` (default), silent no-op when no index exists.
- **Linter-feedback ACI on edit** — SWE-agent's central insight: the
  model self-corrects far better when it sees lint diagnostics on the
  SAME turn as the edit. `tool_write` / `tool_edit` / `tool_multi_edit`
  now run the per-file linter (ruff / eslint / go vet / shellcheck)
  after a successful write and append a `<lint_after_write>` block to
  the tool result. `JOE_AUTO_LINT=0` to disable.
- **OpenHands microagent compatibility** — SKILL.md frontmatter now
  parses `triggers: [a, b, c]` (OpenHands inline-list form) and folds
  it into `when_to_use`. OpenHands microagents shared publicly drop
  into `~/.joe-agent/skills/` without translation.

15 new tests in `tests/test_v0_11_11_features.py`. 296 / 299 passing
across the full suite.

## v0.11.10 — secrets-pattern guardrail

- New `_scan_secrets()` scanner refuses `<write>` / `<edit>` /
  `<multi_edit>` bodies that match 11 known secret patterns: AWS access
  + secret keys, OpenAI / Anthropic API keys, GitHub PATs (classic +
  fine-grained), Stripe live keys, Google API keys, Slack webhooks +
  tokens, JWTs, PEM-block private keys.
- Refusals print a redacted finding (first 8 + last 4 chars only) so
  the matched secret never lands in terminal scrollback.
- Inspired by Future AGI's gateway-level guardrail action triad
  (block / warn / log) -- adapted to the local-first threat model
  where the actual risk is a model writing your live API key into
  a file you then commit.
- `JOE_GUARDRAILS=0` disables for a session; bypass is intentionally
  per-session (not per-write) so even a `/trust=all` flow can't silently
  leak.

## v0.11.9 — comprehensive docs sync

- README.md grew a `## v0.11.x — user-research polish + safety
  hardening` section covering v0.11.1 through v0.11.8 (8 releases).
- JOE.md appended a structured `v0.9.x / v0.10.x / v0.11.x` retrospective
  to replace the v0.8.0-era "what's coming next" stub. Three of the
  four open paths there shipped; the doc now reflects that.
- "what's not in here yet" sections in both files refreshed: shipped
  items removed, replaced with the actual remaining backlog (HTTP/SSE
  MCP transport, `/undo last-N`, speculative parallel, voice on
  Windows, `joe stats --export csv`).

## v0.11.8 — OS-level <bash> sandbox

- When joe's tool-layer sandbox is `read-only` or `workspace-write`,
  every `<bash>` command is now wrapped in an OS-native jail so escape
  via subshells / `eval` / nested commands is blocked at the kernel,
  not just at the Python tool dispatcher.
- macOS: `sandbox-exec` with a Seatbelt (SBPL) profile that denies
  `file-write*` and re-allows only `/tmp`, `/dev/null`, and (in
  workspace-write) the cwd.
- Linux: `bwrap` (from `bubblewrap`) preferred — `--ro-bind /`,
  tmpfs `/tmp`, cwd re-bound rw in workspace-write. Falls back to
  `firejail --read-only=/` when bwrap is absent.
- `JOE_OS_SANDBOX=0` env or `/sandbox os off` opts out. The
  `/sandbox` status panel prints which jail is active.

## v0.11.7 — tree-sitter edit validation

- Non-Python writes / edits now route through `tree-sitter-languages`
  when installed. Same contract as the v0.9.6 Python AST guard: if the
  parse tree has error nodes, joe refuses the write and reflects the
  first error's line:col back to the model so the next turn fixes it.
- 25+ extensions covered: js, ts, tsx, jsx, rs, go, rb, java, kt,
  swift, c, cpp, cs, php, lua, scala, bash, html, css, json, yaml,
  toml, sql.
- `tree-sitter-languages` stays an optional dep; absent => silent skip.

## v0.11.6 — knowledge-graph viz in /dashboard

- `/dashboard` renders the newest subject-relation-object triples as a
  Mermaid flowchart (dark-themed, lazy-loaded from the CDN). The
  raw triple table is preserved under a `<details>` toggle.

## v0.11.0 — 2026-05-13

- Comprehensive README + JOE.md update covering everything shipped
  v0.10.1 through v0.10.7 in one place.
- New CHANGELOG.md as the per-release reference.

## v0.10.7 — AI! markers + /skills install

- `/ai-markers` scans cwd for `# AI!` / `// AI!` / `<!-- AI! -->`
  comments. `/ai-markers fix` runs one turn per marker. Aider's
  signature feature, ported.
- `/skills install <git-url>` clones a SKILL.md package directly into
  `~/.joe-agent/skills/`. Validated, idempotent, reloads after install.

## v0.10.6 — Skills + /loop

- Skills system: Claude Code's SKILL.md packages. Drop a directory
  with frontmatter (name, description, when_to_use, allowed_tools).
  Auto-injected when user message matches triggers.
- `/loop N <prompt>` runs the same prompt N times.
- `/loop until <condition> <prompt>` iterates up to 12 times.

## v0.10.5 — repo map + mode switching

- Aider-style `<repo_map>` block in system prompt. Per-file symbol
  table for Python, TypeScript, Rust, Go.
- `/mode act | plan | architect | debug | ask | review | security`
  atomically swaps output-style + sandbox. Cline / Roo Code pattern.

## v0.10.4 — @-mentions + sandbox modes

- `@path/to/file` in user input auto-injects the file as a
  `<file>` block. Cursor / Continue.dev pattern.
- Sandbox modes (`read-only` / `workspace-write` / `full`) gate the
  tool dispatcher. `workspace-write` refuses writes outside cwd.

## v0.10.3 — Claude-Code parity pack

- `/output-style` with 7 presets (concise, explanatory, learning,
  security, review, ship-it, default). Custom `.md` files extend.
- `/statusline <fmt>` customises the bottom-of-REPL bar.
- `<multi_edit>` — atomic N-edits-in-one-tag.
- `<notebook_edit>` — Jupyter .ipynb cell mutations.

## v0.10.2 — /diff-model + reasoning trace + turn meter

- `/diff-model <a> <b> <prompt>` is the cheap 2-model A/B without a
  judge spend.
- `capture_reasoning_trace()` strips and persists `<think>` blocks
  from DeepSeek-R1-style models.
- `/think show <hash>` surfaces past traces.
- Inline turn meter: `└ 1247 tok in · 412 tok out · 3.2s · 129 tok/s`.

## v0.10.1 — plugins + AGENTS.md auto-load

- Plugin tools: drop `.py` files in `~/.joe-agent/tools/` with a
  `register()` function. Parser regenerates to recognise the new tag.
- `AGENTS.md` / `CLAUDE.md` / `.joe/instructions.md` in cwd are
  auto-loaded as `<project_context>` in every system prompt.

## v0.10.0 — comprehensive docs

- README rewritten with the full v0.9.x tour + 22-tool registry.
- JOE.md (806 lines) created at `~/Desktop/JOE.md`.

## v0.9.10 — Playwright browser tool

- `<browser>` with 9 actions (open / click / type / wait / screenshot
  / extract / title / url / back / close). Single Playwright session
  per REPL.

## v0.9.9 — `<parallel>` + tool result cache

- `<parallel>` runs N side-effect-free tools concurrently.
- Per-session cache for read / grep / glob / web_fetch.

## v0.9.8 — eval diff + auto-eval on swap

- `joe eval diff <a> <b>` for per-case A/B regression.
- `joe eval cases` to preview the benchmark.
- Auto-eval daemon thread fires on `/model` swap, warns on regression.

## v0.9.7 — PC control + custom commands + hooks

- Six new tools: `<screen>`, `<click>`, `<type>`, `<key>`, `<open>`,
  `<clipboard>`. Anthropic Computer Use surface, locally.
- Custom slash commands as TOML files in `~/.joe-agent/commands/`.
- Hooks: shell scripts in `~/.joe-agent/hooks/<event>.sh` for
  pre_tool / post_tool / user_prompt / stop.

## v0.9.6 — reproducibility passport + /council + /blame

- Passport: sha256 of (model + prompt + cwd + lessons + lora) for
  every turn. `/passport replay <hash>` re-runs bit-for-bit.
- `/council <prompt>` fires same prompt at 3 models + auto-judge.
- `/blame <file>:<line>` surfaces AI provenance.
- Tool-emission repair hints when the parser fails.
- Python AST validation before write.

## v0.9.5 — per-tool session trust

- `[y/N/a]` permission prompt. `a` = always for this tool, this
  session. `/trust` for explicit grants + reset.

## v0.9.4 — friendly missing-dep error + project orient banner

- `_import_required_or_die` prints the exact interpreter path + pip
  command on missing rich/prompt_toolkit.
- `_orient()` shows `project: X · framework, git: branch · last
  commit, about: README first line, llm: mlx_lm.server` under banner.

## v0.9.3 — CI fixes (py3.10 dropped, idempotent release)

## v0.9.2 — CI runtime deps + fail-fast off

## v0.9.1 — CI cache directive fix

## v0.9.0 — LoRA REPL routing + GitHub Actions CI + joe-voice

- `/lora on/off/status` + auto-detect mlx_lm.server on :8081.
- GitHub Actions test.yml + release.yml.
- joe-voice press-to-talk loop (joe-listen + joe -p + joe-speak).
