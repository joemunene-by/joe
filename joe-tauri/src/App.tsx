/**
 * joe desktop: top-level layout.
 *
 *   ┌──────────────────┬──────────────────────────────────────┐
 *   │ File tree        │  Chat (streaming agent output)        │
 *   │  + Git pane      │                                       │
 *   │                  │                                       │
 *   │                  ├──────────────────────────────────────┤
 *   │ Permissions      │  Prompt input                         │
 *   └──────────────────┴──────────────────────────────────────┘
 *
 * The left rail is a tabbed sidebar (Files / Git / Permissions).
 * The right column is the chat surface that drives the joe sidecar.
 */

import { useState } from 'react';
import ChatPane from './components/ChatPane';
import FileTreePane from './components/FileTreePane';
import GitPane from './components/GitPane';
import PermissionsPane from './components/PermissionsPane';
import StatusBar from './components/StatusBar';

type SidebarTab = 'files' | 'git' | 'perms';

export default function App() {
  const [tab, setTab] = useState<SidebarTab>('files');
  // Current working directory the desktop app is "rooted" at. The
  // FileTree pane reflects it; the GitPane runs commands against it.
  // Defaulting to $HOME is the safest first-launch choice; the user
  // explicitly grants read access from there.
  const [cwd, setCwd] = useState<string>(homeDir());

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-tabs">
          <SidebarTabButton active={tab === 'files'} label="Files" onClick={() => setTab('files')} />
          <SidebarTabButton active={tab === 'git'} label="Git" onClick={() => setTab('git')} />
          <SidebarTabButton active={tab === 'perms'} label="Permissions" onClick={() => setTab('perms')} />
        </div>
        <div className="sidebar-body">
          {tab === 'files' && <FileTreePane cwd={cwd} onChangeCwd={setCwd} />}
          {tab === 'git' && <GitPane repo={cwd} />}
          {tab === 'perms' && <PermissionsPane />}
        </div>
      </aside>
      <main className="main">
        <ChatPane />
        <StatusBar cwd={cwd} />
      </main>
    </div>
  );
}

function SidebarTabButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button className={`sidebar-tab${active ? ' sidebar-tab-active' : ''}`} onClick={onClick} type="button">
      {label}
    </button>
  );
}

function homeDir(): string {
  // Browsers don't expose $HOME directly; the Tauri webview environment
  // does, but we read it lazily via the FileTree's "browse from root"
  // affordance instead of crashing on first paint.
  return '/';
}
