//! Renderer-facing native commands. Every module here exposes one or
//! more `#[tauri::command]` functions. They're all registered in
//! `main.rs::main` via `invoke_handler`.

pub mod agent;
pub mod fs;
pub mod git;
pub mod perms;
pub mod shell;
