/**
 * Permissions inspector + revocation surface.
 *
 * Reads perms.snapshot() and lists every active grant grouped by
 * category (paths / repos / commands) and lifetime (persistent /
 * session). Each row has a revoke button so the user can pull access
 * back at any time without having to edit the backing JSON file.
 */

import { useCallback, useEffect, useState } from 'react';
import { perms } from '../lib/invoke';
import type { PermsSnapshot } from '../lib/invoke';

type Category = 'path' | 'repo' | 'command';
type Lifetime = 'persistent' | 'session';

interface Row {
  subject: string;
  lifetime: Lifetime;
}

export default function PermissionsPane() {
  const [snap, setSnap] = useState<PermsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      setSnap(await perms.snapshot());
    } catch (err) {
      setError(String(err));
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const revoke = async (cat: Category, subject: string) => {
    try {
      if (cat === 'path') await perms.revokePath(subject);
      else if (cat === 'repo') await perms.revokeRepo(subject);
      else await perms.revokeCommand(subject);
      await reload();
    } catch (err) {
      setError(String(err));
    }
  };

  if (!snap) {
    return (
      <div className="pane">
        <div className="pane-header">
          <span className="pane-path">Permissions</span>
          <button className="pane-btn" onClick={reload} type="button" title="Refresh">
            ↻
          </button>
        </div>
        {error && <div className="error-box">{error}</div>}
      </div>
    );
  }

  const paths: Row[] = [
    ...snap.persistent_paths.map((s) => ({ subject: s, lifetime: 'persistent' as const })),
    ...snap.session_paths.map((s) => ({ subject: s, lifetime: 'session' as const })),
  ];
  const repos: Row[] = [
    ...snap.persistent_repos.map((s) => ({ subject: s, lifetime: 'persistent' as const })),
    ...snap.session_repos.map((s) => ({ subject: s, lifetime: 'session' as const })),
  ];
  const commands: Row[] = [
    ...snap.persistent_commands.map((s) => ({ subject: s, lifetime: 'persistent' as const })),
    ...snap.session_commands.map((s) => ({ subject: s, lifetime: 'session' as const })),
  ];

  return (
    <div className="pane perms-pane">
      <div className="pane-header">
        <span className="pane-path">Permissions</span>
        <button className="pane-btn" onClick={reload} type="button" title="Refresh">
          ↻
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      <Section title="Filesystem paths" cat="path" rows={paths} onRevoke={revoke} />
      <Section title="Git repositories" cat="repo" rows={repos} onRevoke={revoke} />
      <Section title="Shell commands" cat="command" rows={commands} onRevoke={revoke} />

      <div className="perms-help">
        Persistent grants survive restarts and live in <code>~/.joe-agent/desktop-permissions.json</code>.
        Session grants disappear when joe exits.
      </div>
    </div>
  );
}

function Section({
  title,
  cat,
  rows,
  onRevoke,
}: {
  title: string;
  cat: Category;
  rows: Row[];
  onRevoke: (cat: Category, subject: string) => void;
}) {
  return (
    <div className="perms-section">
      <h3>{title}</h3>
      {rows.length === 0 ? (
        <div className="perms-empty">No grants</div>
      ) : (
        <ul className="perms-list">
          {rows.map((r) => (
            <li key={`${r.lifetime}:${r.subject}`}>
              <span className="perms-subject" title={r.subject}>
                {r.subject}
              </span>
              <span className={`perms-tag perms-tag-${r.lifetime}`}>{r.lifetime}</span>
              <button
                className="perms-revoke"
                onClick={() => onRevoke(cat, r.subject)}
                type="button"
              >
                revoke
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
