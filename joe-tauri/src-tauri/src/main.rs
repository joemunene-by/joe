// joe-tauri: desktop app for the joe agent.
//
// Two surfaces live in one Tauri process:
//
//   1. The menu-bar shell (the v0.2 behaviour, preserved). Tray icon
//      opens the joe-http dashboard in a small webview.
//   2. The full desktop window (v0.3, the new mode). React frontend
//      with chat + file tree + git pane + permissions pane, talks to
//      native Rust commands for fs / git / shell / agent. Default-deny
//      permissions: every path, repo, and shell command needs an
//      explicit grant before joe-tauri will touch it.
//
// The menu-bar shell is still hidden-on-launch + tray-toggled. The
// desktop window opens explicitly via the tray's "Open desktop app"
// item. Both share the same Permissions state.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod permissions;

use std::fs;
use std::path::PathBuf;
use std::process::Command;

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, WebviewUrl, WebviewWindowBuilder,
};

use permissions::Permissions;

fn http_token() -> String {
    if let Ok(t) = std::env::var("JOE_HTTP_TOKEN") {
        return t;
    }
    let home = std::env::var("HOME").unwrap_or_default();
    let p: PathBuf = [&home, ".joe-agent", "http-token"].iter().collect();
    fs::read_to_string(&p).unwrap_or_default().trim().to_string()
}

fn page_url(port: u16, path: &str) -> String {
    let token = http_token();
    if token.is_empty() {
        return "tauri://localhost/index.html".to_string();
    }
    format!("http://127.0.0.1:{}{}?token={}", port, path, token)
}

fn dashboard_url(port: u16) -> String {
    page_url(port, "/dashboard")
}

fn open_terminal_with_joe() {
    #[cfg(target_os = "macos")]
    {
        let _ = Command::new("osascript")
            .arg("-e")
            .arg(
                r#"tell application "Terminal"
                    activate
                    do script "joe --transcript"
                end tell"#,
            )
            .spawn();
    }
    #[cfg(target_os = "linux")]
    {
        for term in &["gnome-terminal", "konsole", "xfce4-terminal", "xterm"] {
            if Command::new(term).arg("-e").arg("joe --transcript").spawn().is_ok() {
                break;
            }
        }
    }
}

/// Open (or focus) the full desktop window. Lazily created on first
/// invocation so the menu-bar-only users don't pay the React-load tax.
fn open_desktop_window(handle: &tauri::AppHandle) {
    if let Some(win) = handle.get_webview_window("desktop") {
        let _ = win.show();
        let _ = win.set_focus();
        return;
    }
    let url = WebviewUrl::App("desktop.html".into());
    let win = WebviewWindowBuilder::new(handle, "desktop", url)
        .title("joe")
        .inner_size(1200.0, 800.0)
        .min_inner_size(720.0, 480.0)
        .decorations(true)
        .resizable(true)
        .visible(true)
        .build();
    match win {
        Ok(w) => {
            let _ = w.set_focus();
        }
        Err(e) => eprintln!("[joe-tauri] failed to build desktop window: {}", e),
    }
}

fn main() {
    let port: u16 = std::env::var("JOE_HTTP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8765);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Permissions::load())
        .invoke_handler(tauri::generate_handler![
            commands::fs::list_dir,
            commands::fs::read_file,
            commands::fs::write_file,
            commands::git::git_status,
            commands::git::git_diff,
            commands::git::git_log,
            commands::git::git_branches,
            commands::git::git_stage,
            commands::git::git_unstage,
            commands::git::git_commit,
            commands::git::git_push,
            commands::git::git_pull,
            commands::shell::shell_exec,
            commands::agent::agent_run,
            commands::perms::perms_snapshot,
            commands::perms::perms_grant_path,
            commands::perms::perms_grant_repo,
            commands::perms::perms_grant_command,
            commands::perms::perms_revoke_path,
            commands::perms::perms_revoke_repo,
            commands::perms::perms_revoke_command,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let open_dashboard =
                MenuItem::with_id(app, "open", "Open joe-http dashboard", true, None::<&str>)?;
            let open_desktop =
                MenuItem::with_id(app, "desktop", "Open desktop app", true, None::<&str>)?;
            let mobile_item =
                MenuItem::with_id(app, "mobile", "Open mobile view", true, None::<&str>)?;
            let keys_item =
                MenuItem::with_id(app, "keys", "Open sync keys", true, None::<&str>)?;
            let sep1 = PredefinedMenuItem::separator(app)?;
            let term_item = MenuItem::with_id(
                app,
                "terminal",
                "New terminal (joe --transcript)",
                true,
                None::<&str>,
            )?;
            let refresh_item =
                MenuItem::with_id(app, "refresh", "Refresh dashboard", true, None::<&str>)?;
            let sep2 = PredefinedMenuItem::separator(app)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit joe", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[
                    &open_desktop,
                    &open_dashboard,
                    &mobile_item,
                    &keys_item,
                    &sep1,
                    &term_item,
                    &refresh_item,
                    &sep2,
                    &quit_item,
                ],
            )?;

            let _tray = TrayIconBuilder::with_id("joe-tray")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event({
                    let handle = handle.clone();
                    move |app_handle, event| match event.id.as_ref() {
                        "desktop" => open_desktop_window(&handle),
                        "open" => {
                            if let Some(win) = handle.get_webview_window("main") {
                                let url = dashboard_url(port);
                                let _ = win.eval(&format!("window.location='{}'", url));
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                        "mobile" => {
                            if let Some(win) = handle.get_webview_window("main") {
                                let url = page_url(port, "/m");
                                let _ = win.eval(&format!("window.location='{}'", url));
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                        "keys" => {
                            if let Some(win) = handle.get_webview_window("main") {
                                let url = page_url(port, "/keys");
                                let _ = win.eval(&format!("window.location='{}'", url));
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                        "terminal" => open_terminal_with_joe(),
                        "refresh" => {
                            if let Some(win) = handle.get_webview_window("main") {
                                let url = dashboard_url(port);
                                let _ = win.eval(&format!("window.location='{}'", url));
                            }
                        }
                        "quit" => app_handle.exit(0),
                        _ => {}
                    }
                })
                .on_tray_icon_event({
                    let handle = handle.clone();
                    move |_tray, event| {
                        if let TrayIconEvent::Click {
                            button: MouseButton::Left,
                            button_state: MouseButtonState::Up,
                            ..
                        } = event
                        {
                            if let Some(win) = handle.get_webview_window("main") {
                                let visible = win.is_visible().unwrap_or(false);
                                if visible {
                                    let _ = win.hide();
                                } else {
                                    let _ = win.show();
                                    let _ = win.set_focus();
                                }
                            }
                        }
                    }
                })
                .build(app)?;

            // Point the menu-bar window at the dashboard.
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.eval(&format!("window.location='{}'", dashboard_url(port)));
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running joe-tauri");
}
