// joe-tauri: menu-bar shell for the joe-http dashboard.
//
// One window, hidden on launch. Clicking the menu-bar icon toggles it.
// The window navigates to joe-http's /dashboard with the bearer token
// from ~/.joe-agent/http-token (or $JOE_HTTP_TOKEN) appended as ?token=.
//
// Menu items beyond the dashboard:
//   - "Open dashboard"  / "Open mobile view" / "Open keys"  pick a page.
//   - "New terminal session" shells out to Terminal.app so users can
//     launch `joe --transcript` without leaving the tray.
//   - "Reload joe-http"  curl's /health to confirm the server's reachable.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;
use std::process::Command;

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};

fn http_token() -> String {
    if let Ok(t) = std::env::var("JOE_HTTP_TOKEN") {
        return t;
    }
    let home = std::env::var("HOME").unwrap_or_default();
    let p: PathBuf = [&home, ".joe-agent", "http-token"].iter().collect();
    fs::read_to_string(&p)
        .unwrap_or_default()
        .trim()
        .to_string()
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
    // macOS: launch Terminal.app with `joe --transcript`. The user can
    // dismiss the Terminal window when done; we don't track it.
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
    // Linux: try a few common terminals in order. If none are present
    // this silently no-ops (the user can still open one themselves).
    #[cfg(target_os = "linux")]
    {
        for term in &["gnome-terminal", "konsole", "xfce4-terminal", "xterm"] {
            if Command::new(term)
                .arg("-e")
                .arg("joe --transcript")
                .spawn()
                .is_ok()
            {
                break;
            }
        }
    }
}

fn main() {
    let port: u16 = std::env::var("JOE_HTTP_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8765);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let handle = app.handle().clone();
            let open_item = MenuItem::with_id(app, "open", "Open dashboard", true, None::<&str>)?;
            let mobile_item =
                MenuItem::with_id(app, "mobile", "Open mobile view", true, None::<&str>)?;
            let keys_item =
                MenuItem::with_id(app, "keys", "Open sync keys", true, None::<&str>)?;
            let sep1 = PredefinedMenuItem::separator(app)?;
            let term_item =
                MenuItem::with_id(app, "terminal", "New terminal (joe --transcript)", true, None::<&str>)?;
            let refresh_item =
                MenuItem::with_id(app, "refresh", "Refresh dashboard", true, None::<&str>)?;
            let sep2 = PredefinedMenuItem::separator(app)?;
            let quit_item =
                MenuItem::with_id(app, "quit", "Quit joe", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[
                    &open_item, &mobile_item, &keys_item,
                    &sep1,
                    &term_item, &refresh_item,
                    &sep2,
                    &quit_item,
                ],
            )?;

            let _tray = TrayIconBuilder::with_id("joe-tray")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .menu_on_left_click(false)
                .on_menu_event({
                    let handle = handle.clone();
                    move |app_handle, event| match event.id.as_ref() {
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

            // Point the main window at the dashboard. Webview navigation
            // here means the window lives at http://127.0.0.1:8765/...
            // when joe-http is up; the local index.html only appears when
            // the token can't be found.
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.eval(&format!("window.location='{}'", dashboard_url(port)));
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running joe-tauri");
}
