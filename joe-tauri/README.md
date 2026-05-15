# joe-tauri

joe's native desktop surface. Tray icon for quick access to the
`joe-http` dashboard, plus a full desktop app that drives the joe
sidecar directly with permission-gated file, git, and shell access.

## what you get

Two surfaces in one Tauri binary:

1. **Menu-bar mode** (default): click the tray icon to open the
   `joe-http` dashboard in a floating webview. Same v0.2 behavior.
2. **Desktop mode**: full window with a file tree, git pane, agent
   chat, and a permissions inspector. Every native operation goes
   through a default-deny grant flow you control.

## permission model

The desktop app never touches your filesystem, git repos, or shell
without an explicit grant. Three scopes, two lifetimes each:

| scope    | what it covers                                       |
|----------|------------------------------------------------------|
| path     | reads/writes under a directory tree                  |
| repo     | every `git` command inside a given working copy      |
| command  | a specific shell binary (by basename)                |

Grants are either **session** (held in memory, gone on restart) or
**persistent** (saved to `~/.joe-agent/desktop-permissions.json`).

When a native call hits a denied path or repo, the UI shows an
in-place prompt: "Allow once (session)" or "Always allow". You can
also review and revoke every grant from the **Permissions** tab.

## architecture

```
joe-tauri/
  src-tauri/                 Rust + Tauri 2
    src/main.rs              tray icon, window mgmt, joe-http boot
    src/permissions.rs       grant store + path/repo/command checks
    src/commands/
      fs.rs                  list_dir, read_file, write_file
      git.rs                 status, diff, stage, commit, push, pull
      shell.rs               permission-gated subprocess exec
      agent.rs               spawn joe sidecar, stream stdout events
      perms.rs               grant/revoke/snapshot for the UI
  src/                       React + Vite
    App.tsx                  sidebar tabs + chat layout
    lib/invoke.ts            typed wrappers around tauri's invoke()
    components/
      FileTreePane.tsx       browse + preview, with grant prompt
      GitPane.tsx            porcelain status, diff, commit, push/pull
      PermissionsPane.tsx    snapshot + revoke
      ChatPane.tsx           streams joe sidecar stdout via events
      StatusBar.tsx          cwd + sandbox indicator
  index.html                 menu-bar fallback (static HTML)
  desktop.html               React app entry
```

The Rust side never trusts the renderer. Every native command takes
the path or repo it operates on as an argument, then asks
`Permissions::path_allowed` / `repo_allowed` / `command_allowed`
before doing anything. Denials come back as a discriminated-union
error (`{ kind: "permission_denied", subject, scope }`) so the UI
can branch on scope and offer the right grant button.

## prerequisites

- Rust + cargo. Install via rustup (preferred); `brew install rust`
  ships an older toolchain and doesn't manage targets cleanly:
  ```sh
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  source ~/.cargo/env
  ```
- Tauri CLI: `cargo install tauri-cli --version "^2.0"`
- Node 18+ and npm (frontend is a Vite+React build)

## dev

```sh
cd joe-tauri
npm install
npm run dev      # vite dev server on :5174
# in another terminal:
cargo tauri dev  # boots the app, hot-reloads from vite
```

Open the desktop window by right-clicking the tray icon and choosing
"Open desktop". Or just launch the app and click the tray icon, then
hit the desktop shortcut.

## build a release bundle

```sh
npm run build      # vite production build into ../dist
cargo tauri build  # signs and bundles .app / .deb / .msi
```

The artifact lands in `src-tauri/target/release/bundle/`. Drag the
`.app` into `/Applications` on macOS.

## env vars

| variable        | meaning                                              |
|-----------------|------------------------------------------------------|
| `JOE_BIN`       | path to the joe binary (defaults to `$PATH` lookup)  |
| `JOE_HTTP_PORT` | port for the menu-bar dashboard (default 8765)       |
| `JOE_HTTP_TOKEN`| override the token used when calling joe-http        |

## what's intentionally not here

- no embedded model runtime; the agent shells out to `joe`
- no auto-grant: every new path or repo is denied until you say yes
- no global file watcher; the file tree only refreshes on request

## changelog

- **v0.3.0**: desktop window with file tree, git, chat, and
  permissions. Default-deny permission model with session +
  persistent grants. Multi-page Vite build alongside the menu-bar
  fallback.
- **v0.2.x**: menu-bar shell around `joe-http`.
