/**
 * Git pane: status table + stage / unstage / commit / push / pull
 * buttons + a diff viewer for the selected file.
 *
 * Same permission flow as the FileTree pane: refuses to do anything
 * in an un-granted repo, prompts the user, retries on grant.
 */

import { useCallback, useEffect, useState } from 'react';
import { git, perms, isPermissionDenied } from '../lib/invoke';
import type { GitStatus } from '../lib/invoke';

interface Props {
  repo: string;
}

export default function GitPane({ repo }: Props) {
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [denied, setDenied] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [diff, setDiff] = useState<string>('');
  const [commitMsg, setCommitMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setError(null);
    setDenied(null);
    setBusy(true);
    try {
      const s = await git.status(repo);
      setStatus(s);
    } catch (err) {
      const pd = isPermissionDenied(err);
      if (pd) {
        setDenied(pd.subject);
      } else if (typeof err === 'object' && err && (err as any).kind === 'not_a_repo') {
        setError(`Not a git repository: ${repo}`);
      } else {
        setError(String(err));
      }
      setStatus(null);
    } finally {
      setBusy(false);
    }
  }, [repo]);

  useEffect(() => {
    reload();
  }, [reload]);

  const grantAndReload = async (persistent: boolean) => {
    if (denied) {
      await perms.grantRepo(denied, persistent);
      await reload();
    }
  };

  const loadDiff = async (path: string, staged: boolean) => {
    setSelected(path);
    try {
      const d = await git.diff(repo, path, staged);
      setDiff(d || '(no changes)');
    } catch (err) {
      setDiff(`error: ${err}`);
    }
  };

  const stage = async (path: string) => {
    setBusy(true);
    try {
      await git.stage(repo, [path]);
      await reload();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const unstage = async (path: string) => {
    setBusy(true);
    try {
      await git.unstage(repo, [path]);
      await reload();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const commit = async () => {
    if (!commitMsg.trim()) return;
    setBusy(true);
    try {
      await git.commit(repo, commitMsg.trim());
      setCommitMsg('');
      await reload();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const push = async () => {
    setBusy(true);
    try {
      await git.push(repo);
      await reload();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const pull = async () => {
    setBusy(true);
    try {
      await git.pull(repo);
      await reload();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pane">
      <div className="pane-header">
        <span className="pane-path" title={repo}>
          {repo}
        </span>
        <button className="pane-btn" onClick={reload} disabled={busy} type="button" title="Refresh">
          ↻
        </button>
      </div>

      {denied && (
        <div className="permission-prompt">
          <div className="permission-prompt-title">Git access required</div>
          <div className="permission-prompt-body">
            joe needs access to the git repo at <code>{denied}</code>.
          </div>
          <div className="permission-prompt-actions">
            <button className="btn btn-primary" onClick={() => grantAndReload(false)} type="button">
              Allow once (session)
            </button>
            <button className="btn" onClick={() => grantAndReload(true)} type="button">
              Always allow this repo
            </button>
          </div>
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {status && (
        <>
          <div className="git-summary">
            <strong>{status.branch}</strong>
            {status.upstream && (
              <span className="git-upstream">
                {' '}↔ {status.upstream}
                {status.ahead > 0 && <span className="git-ahead"> ↑{status.ahead}</span>}
                {status.behind > 0 && <span className="git-behind"> ↓{status.behind}</span>}
              </span>
            )}
            {status.clean && <span className="git-clean"> • clean</span>}
          </div>

          <div className="git-actions">
            <button className="btn" onClick={pull} disabled={busy} type="button">
              Pull
            </button>
            <button className="btn" onClick={push} disabled={busy || status.clean === false} type="button">
              Push
            </button>
          </div>

          {!status.clean && (
            <ul className="git-status-list">
              {status.entries.map((e) => {
                const isStaged = e.status[0] !== ' ' && e.status[0] !== '?';
                return (
                  <li key={e.path} className={selected === e.path ? 'git-status-row-selected' : ''}>
                    <button className="git-status-row" onClick={() => loadDiff(e.path, isStaged)} type="button">
                      <span className="git-status-code">{e.status}</span>
                      <span className="git-status-path">{e.path}</span>
                    </button>
                    <button
                      className="git-status-action"
                      onClick={() => (isStaged ? unstage(e.path) : stage(e.path))}
                      disabled={busy}
                      type="button"
                    >
                      {isStaged ? 'unstage' : 'stage'}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {selected && diff && (
            <div className="git-diff">
              <div className="git-diff-header">{selected}</div>
              <pre className="git-diff-body">{colorDiff(diff)}</pre>
            </div>
          )}

          {!status.clean && (
            <div className="git-commit">
              <input
                className="git-commit-input"
                placeholder="Commit message"
                value={commitMsg}
                onChange={(e) => setCommitMsg(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && commit()}
              />
              <button className="btn btn-primary" onClick={commit} disabled={busy || !commitMsg.trim()} type="button">
                Commit
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function colorDiff(d: string): React.ReactNode {
  return d.split('\n').map((line, i) => {
    let color = '#aaa';
    if (line.startsWith('+') && !line.startsWith('+++')) color = '#7fd17f';
    else if (line.startsWith('-') && !line.startsWith('---')) color = '#ff6b6b';
    else if (line.startsWith('@@')) color = '#5a9fd4';
    return (
      <span key={i} style={{ color, display: 'block' }}>
        {line}
      </span>
    );
  });
}
