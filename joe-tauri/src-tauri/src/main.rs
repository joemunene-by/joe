// joe-tauri: menu-bar shell for the joe-http dashboard.
//
// One window, hidden on launch. Clicking the menu-bar icon toggles it.
// The window navigates to joe-http's /dashboard with the bearer token
// from ~/.joe-agent/http-token (or $JOE_HTTP_TOKEN) appended as ?token=.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::PathBuf;

use tauri::{
    menu::{Menu, MenuItem},
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

fn dashboard_url(port: u16) -> String {
    let token = http_token();
    if token.is_empty() {
        // Fall back to the bundled index.html which renders the "start
        // joe-http first" message.
        return "tauri://localhost/index.html".to_string();
    }
    format!("http://127.0.0.1:{}/dashboard?token={}", port, token)
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
            let open_item = MenuItem::with_id(app, "open", "Open joe", true, None::<&str>)?;
            let refresh_item =
                MenuItem::with_id(app, "refresh", "Refresh dashboard", true, None::<&str>)?;
            let quit_item =
                MenuItem::with_id(app, "quit", "Quit joe", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_item, &refresh_item, &quit_item])?;

            let _tray = TrayIconBuilder::with_id("joe-tray")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .menu_on_left_click(false)
                .on_menu_event({
                    let handle = handle.clone();
                    move |app_handle, event| match event.id.as_ref() {
                        "open" => {
                            if let Some(win) = handle.get_webview_window("main") {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
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
