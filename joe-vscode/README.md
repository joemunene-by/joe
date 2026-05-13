# joe-vscode

VS Code extension that talks to a local [joe](https://github.com/joemunene-by/joe) agent shell via `joe-http`. Quick ask box, ask-about-selection, sidebar chat, and a one-click "open dashboard" command.

## Install (local dev)

```bash
cd joe-vscode
npm install
npm run compile
# then in VS Code: F5 to open an Extension Development Host.
```

Or package and install:

```bash
npm install -g @vscode/vsce
vsce package
code --install-extension joe-vscode-0.1.0.vsix
```

## Setup

You need [joe-http](https://github.com/joemunene-by/joe) running. The extension reads the bearer token in this order:

1. `joe.httpToken` setting in VS Code (preferred for per-workspace overrides).
2. `JOE_HTTP_TOKEN` environment variable.
3. `~/.joe-agent/http-token` on disk.

Default URL is `http://127.0.0.1:8765`. Change `joe.httpUrl` to point at a remote joe over Tailscale / LAN.

## Commands

| Command | Default keybind | What it does |
| --- | --- | --- |
| `joe: Ask` | `Cmd-Alt-J` / `Ctrl-Alt-J` | Quick ask. Streams into the joe output channel. |
| `joe: Ask about selection` | `Cmd-Alt-Shift-J` / `Ctrl-Alt-Shift-J` | Wraps the current editor selection in a code block plus an input-box question. |
| `joe: Open chat sidebar` | none | Opens the persistent chat webview in the activity bar. |
| `joe: Open dashboard in browser` | none | Opens `joe-http /dashboard` in the default browser. |

## Notes

- Talks to joe's OpenAI-shaped `/v1/chat/completions` shim, so your distilled lessons and prompt supplement are applied automatically.
- The sidebar chat is one-shot per turn; for streaming, use the `/dashboard` page in your browser.
- The selection-aware command quotes the code with its language and line range so joe knows what file it's looking at.
