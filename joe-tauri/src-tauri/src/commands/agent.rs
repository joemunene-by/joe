//! Joe sidecar: spawn `joe -p <prompt>` from PATH, stream stdout to
//! the renderer as Tauri events. The renderer subscribes to two
//! channels:
//!
//!   joe://stdout    — each event carries a chunk of the agent's output
//!   joe://done      — fires once when the sidecar exits, with exit_code
//!
//! Spawning joe itself is *not* permission-gated — the user already
//! granted that by installing the desktop app and running joe locally.
//! What joe does *inside* its run (touching files, running bash, calling
//! git) is gated by joe's own sandbox modes, not ours.

use std::process::Stdio;

use serde::Serialize;
use tauri::{AppHandle, Emitter};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum AgentError {
    SpawnFailed { message: String },
    JoeNotFound,
}

#[derive(Clone, Serialize)]
pub struct StdoutChunk {
    pub line: String,
}

#[derive(Clone, Serialize)]
pub struct AgentDone {
    pub exit_code: i32,
}

/// Fire `joe -p <prompt>`. Returns immediately; the renderer receives
/// stdout lines as `joe://stdout` events and a final `joe://done`.
#[tauri::command]
pub async fn agent_run(prompt: String, app: AppHandle) -> Result<(), AgentError> {
    let joe_path = which_joe().ok_or(AgentError::JoeNotFound)?;
    let mut child = Command::new(&joe_path)
        .arg("-p")
        .arg(&prompt)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null())
        .spawn()
        .map_err(|e| AgentError::SpawnFailed { message: e.to_string() })?;
    let stdout = child.stdout.take().expect("stdout piped");
    let stderr = child.stderr.take().expect("stderr piped");

    let app_for_stdout = app.clone();
    let app_for_stderr = app.clone();
    tokio::spawn(async move {
        let reader = BufReader::new(stdout);
        let mut lines = reader.lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = app_for_stdout.emit("joe://stdout", StdoutChunk { line });
        }
    });
    tokio::spawn(async move {
        let reader = BufReader::new(stderr);
        let mut lines = reader.lines();
        while let Ok(Some(line)) = lines.next_line().await {
            let _ = app_for_stderr.emit(
                "joe://stdout",
                StdoutChunk { line: format!("[stderr] {}", line) },
            );
        }
    });
    tokio::spawn(async move {
        match child.wait().await {
            Ok(status) => {
                let _ = app.emit(
                    "joe://done",
                    AgentDone { exit_code: status.code().unwrap_or(-1) },
                );
            }
            Err(_) => {
                let _ = app.emit("joe://done", AgentDone { exit_code: -1 });
            }
        }
    });
    Ok(())
}

/// Look up the `joe` binary. Tries PATH first; falls back to common
/// install locations so users who have it at ~/.local/bin without it on
/// PATH still get a working desktop app.
fn which_joe() -> Option<std::path::PathBuf> {
    if let Ok(p) = std::env::var("JOE_BIN") {
        let path = std::path::PathBuf::from(p);
        if path.exists() {
            return Some(path);
        }
    }
    let path_env = std::env::var("PATH").unwrap_or_default();
    for dir in path_env.split(':') {
        let candidate = std::path::Path::new(dir).join("joe");
        if candidate.exists() {
            return Some(candidate);
        }
    }
    // Common install locations.
    let home = std::env::var("HOME").unwrap_or_default();
    for fallback in &[
        format!("{}/.local/bin/joe", home),
        "/usr/local/bin/joe".to_string(),
        "/opt/homebrew/bin/joe".to_string(),
    ] {
        let p = std::path::PathBuf::from(fallback);
        if p.exists() {
            return Some(p);
        }
    }
    None
}
