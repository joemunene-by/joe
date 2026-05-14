/**
 * Thin wrapper around Tauri's invoke() that gives us typed responses
 * and a consistent error shape. Every native command lives behind a
 * function here so components import a typed API surface, not raw
 * string command names.
 */

import { invoke } from '@tauri-apps/api/core';

// ------------------------------------------------------------
// Permission types (shared with permissions.rs)
// ------------------------------------------------------------

export interface PermsSnapshot {
  persistent_paths: string[];
  persistent_repos: string[];
  persistent_commands: string[];
  session_paths: string[];
  session_repos: string[];
  session_commands: string[];
}

// ------------------------------------------------------------
// File system types
// ------------------------------------------------------------

export interface DirEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  modified_ms: number | null;
}

export interface FileContent {
  path: string;
  bytes: number;
  text: string | null;
  is_binary: boolean;
  truncated: boolean;
}

// ------------------------------------------------------------
// Git types
// ------------------------------------------------------------

export interface GitStatusEntry {
  path: string;
  status: string;
}

export interface GitStatus {
  branch: string;
  upstream: string | null;
  ahead: number;
  behind: number;
  clean: boolean;
  entries: GitStatusEntry[];
}

// ------------------------------------------------------------
// Shell + agent types
// ------------------------------------------------------------

export interface ShellOutput {
  stdout: string;
  stderr: string;
  exit_code: number;
}

// ------------------------------------------------------------
// Permissions
// ------------------------------------------------------------

export const perms = {
  snapshot: () => invoke<PermsSnapshot>('perms_snapshot'),
  grantPath: (path: string, persistent: boolean) =>
    invoke<void>('perms_grant_path', { path, persistent }),
  grantRepo: (repo: string, persistent: boolean) =>
    invoke<void>('perms_grant_repo', { repo, persistent }),
  grantCommand: (command: string, persistent: boolean) =>
    invoke<void>('perms_grant_command', { command, persistent }),
  revokePath: (path: string) => invoke<void>('perms_revoke_path', { path }),
  revokeRepo: (repo: string) => invoke<void>('perms_revoke_repo', { repo }),
  revokeCommand: (command: string) => invoke<void>('perms_revoke_command', { command }),
};

// ------------------------------------------------------------
// File system
// ------------------------------------------------------------

export const fs = {
  listDir: (path: string) => invoke<DirEntry[]>('list_dir', { path }),
  readFile: (path: string) => invoke<FileContent>('read_file', { path }),
  writeFile: (path: string, contents: string) =>
    invoke<number>('write_file', { path, contents }),
};

// ------------------------------------------------------------
// Git
// ------------------------------------------------------------

export const git = {
  status: (repo: string) => invoke<GitStatus>('git_status', { repo }),
  diff: (repo: string, path?: string, staged?: boolean) =>
    invoke<string>('git_diff', { repo, path: path ?? null, staged: staged ?? false }),
  log: (repo: string, limit?: number) =>
    invoke<string>('git_log', { repo, limit: limit ?? null }),
  branches: (repo: string) => invoke<string[]>('git_branches', { repo }),
  stage: (repo: string, paths: string[]) => invoke<void>('git_stage', { repo, paths }),
  unstage: (repo: string, paths: string[]) => invoke<void>('git_unstage', { repo, paths }),
  commit: (repo: string, message: string) =>
    invoke<string>('git_commit', { repo, message }),
  push: (repo: string) => invoke<string>('git_push', { repo }),
  pull: (repo: string) => invoke<string>('git_pull', { repo }),
};

// ------------------------------------------------------------
// Shell + agent
// ------------------------------------------------------------

export const shell = {
  exec: (argv: string[], cwd?: string) =>
    invoke<ShellOutput>('shell_exec', { argv, cwd: cwd ?? null }),
};

export const agent = {
  run: (prompt: string) => invoke<void>('agent_run', { prompt }),
};

/**
 * Best-effort error-shape detection. Backend FsError / GitError /
 * ShellError variants are serialised as discriminated unions with a
 * `kind` field. UI can branch on that.
 */
export function isPermissionDenied(err: unknown): { subject: string; scope: string } | null {
  if (typeof err === 'object' && err && 'kind' in err && (err as any).kind === 'permission_denied') {
    return { subject: (err as any).subject ?? '', scope: (err as any).scope ?? '' };
  }
  return null;
}
