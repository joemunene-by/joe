# joe-tauri

A tiny Tauri 2 menu-bar app for joe. Click the icon, get the joe-http
dashboard in a floating webview. Tail your inbox, blame timeline, eval
trend, and SSE chat without leaving your menu bar.

## what this is

A thin Tauri shell around the existing `joe-http` dashboard. It doesn't
talk to ollama directly; everything routes through `joe-http`'s bearer-
authenticated endpoints. Means:

- if `joe-http` isn't running, the app shows a clear "start joe-http"
  message instead of erroring
- the auth token comes from `~/.joe-agent/http-token` at app launch (or
  via `JOE_HTTP_TOKEN` env var when you run the dev build)
- no separate server lives inside the app

## prerequisites

- Rust + cargo (`brew install rust`)
- Tauri CLI (`cargo install tauri-cli --version "^2.0"`)
- Node not required (we serve a static HTML file)

## dev

```sh
cd joe-tauri
cargo tauri dev
```

The app expects `joe-http` running on `127.0.0.1:8765`. Start it with:

```sh
joe-http --host 127.0.0.1
```

## build a .app

```sh
cargo tauri build
```

The signed `.app` lands in `src-tauri/target/release/bundle/macos/`.
Drag it into `/Applications`. The menu bar icon appears on next launch.

## what's intentionally not here

- no electron, no node toolchain
- no fancy frontend framework; the dashboard HTML comes from `joe-http`
  via webview navigation, and the local index.html only handles auth
  bootstrapping
- no offline mode; if `joe-http` is down, the app says so

The whole thing is one Rust file and one HTML file by design. Anything
more complex belongs in `joe-http` itself.
