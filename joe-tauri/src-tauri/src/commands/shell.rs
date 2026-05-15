//! Shell-exec command. The most dangerous surface; gated hardest.
//!
//! Each call requires `Permissions::command_allowed(<bare program name>)`.
//! Grants are *per command*, not per full command line. Granting `ls`
//! authorises every `ls` invocation regardless of args, but a granted
//! `ls` does not let the renderer call `rm` or `curl`.
//!
//! Output is captured with a 30-second timeout and a 2 MB cap on
//! combined stdout + stderr.

use std::path::PathBuf;
use std::process::Stdio;
use std::time::Duration;

use serde::Serialize;
use tauri::State;
use tokio::io::AsyncReadExt;
use tokio::process::Command;

use crate::permissions::Permissions;

#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ShellError {
    PermissionDenied { subject: String, scope: &'static str },
    Timeout { command: String, seconds: u64 },
    SpawnFailed { message: String },
    OutputTooLarge { bytes: usize },
}

#[derive(Serialize)]
pub struct ShellOutput {
    pub stdout: String,
    pub stderr: String,
    pub exit_code: i32,
}

const MAX_OUTPUT_BYTES: usize = 2 * 1024 * 1024;
const TIMEOUT_SECONDS: u64 = 30;

/// Exec a command. The first element of `argv` is the program name and
/// is what the permission check applies to.
#[tauri::command]
pub async fn shell_exec(
    argv: Vec<String>,
    cwd: Option<String>,
    perms: State<'_, Permissions>,
) -> Result<ShellOutput, ShellError> {
    let program = argv.first().cloned().unwrap_or_default();
    let program_basename = std::path::Path::new(&program)
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or(program.clone());
    if !perms.command_allowed(&program_basename) {
        return Err(ShellError::PermissionDenied {
            subject: program_basename,
            scope: "command",
        });
    }
    let mut cmd = Command::new(&program);
    if argv.len() > 1 {
        cmd.args(&argv[1..]);
    }
    if let Some(c) = cwd {
        cmd.current_dir(PathBuf::from(c));
    }
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped()).stdin(Stdio::null());
    let mut child = cmd
        .spawn()
        .map_err(|e| ShellError::SpawnFailed { message: e.to_string() })?;
    let mut stdout = child.stdout.take().expect("stdout piped");
    let mut stderr = child.stderr.take().expect("stderr piped");
    let mut out_buf = Vec::new();
    let mut err_buf = Vec::new();
    let wait = async {
        let _ = tokio::join!(
            stdout.read_to_end(&mut out_buf),
            stderr.read_to_end(&mut err_buf)
        );
        child.wait().await
    };
    let status = tokio::time::timeout(Duration::from_secs(TIMEOUT_SECONDS), wait)
        .await
        .map_err(|_| ShellError::Timeout {
            command: argv.join(" "),
            seconds: TIMEOUT_SECONDS,
        })?
        .map_err(|e| ShellError::SpawnFailed { message: e.to_string() })?;
    if out_buf.len() + err_buf.len() > MAX_OUTPUT_BYTES {
        return Err(ShellError::OutputTooLarge {
            bytes: out_buf.len() + err_buf.len(),
        });
    }
    Ok(ShellOutput {
        stdout: String::from_utf8_lossy(&out_buf).to_string(),
        stderr: String::from_utf8_lossy(&err_buf).to_string(),
        exit_code: status.code().unwrap_or(-1),
    })
}
