/**
 * File browser. Two states:
 *
 *   - cwd is permission-granted → render directory contents,
 *     clickable up/down navigation, click a file to preview.
 *   - cwd is denied → render a big "Grant access to <path>" button
 *     that calls perms.grantPath and refreshes.
 *
 * Refuses to render contents the user hasn't authorised.
 */

import { useCallback, useEffect, useState } from 'react';
import { fs, perms, isPermissionDenied } from '../lib/invoke';
import type { DirEntry, FileContent } from '../lib/invoke';

interface Props {
  cwd: string;
  onChangeCwd: (path: string) => void;
}

export default function FileTreePane({ cwd, onChangeCwd }: Props) {
  const [entries, setEntries] = useState<DirEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [denied, setDenied] = useState<string | null>(null);
  const [preview, setPreview] = useState<FileContent | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    setDenied(null);
    setPreview(null);
    try {
      const result = await fs.listDir(cwd);
      setEntries(result);
    } catch (err) {
      const pd = isPermissionDenied(err);
      if (pd) {
        setDenied(pd.subject);
        setEntries(null);
      } else {
        setError(String(err));
        setEntries(null);
      }
    }
  }, [cwd]);

  useEffect(() => {
    reload();
  }, [reload]);

  const grantAndReload = async (persistent: boolean) => {
    if (denied) {
      await perms.grantPath(denied, persistent);
      await reload();
    }
  };

  const navigateInto = (entry: DirEntry) => {
    if (entry.is_dir) {
      onChangeCwd(entry.path);
    } else {
      openPreview(entry.path);
    }
  };

  const navigateUp = () => {
    const parent = cwd.replace(/\/+$/, '').split('/').slice(0, -1).join('/') || '/';
    onChangeCwd(parent);
  };

  const openPreview = async (path: string) => {
    try {
      const file = await fs.readFile(path);
      setPreview(file);
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="pane">
      <div className="pane-header">
        <button className="pane-btn" onClick={navigateUp} type="button" title="Up">
          ↑
        </button>
        <div className="pane-path" title={cwd}>
          {cwd}
        </div>
        <button className="pane-btn" onClick={reload} type="button" title="Refresh">
          ↻
        </button>
      </div>

      {denied && (
        <div className="permission-prompt">
          <div className="permission-prompt-title">Permission required</div>
          <div className="permission-prompt-body">
            joe needs access to <code>{denied}</code> before it can read files here.
          </div>
          <div className="permission-prompt-actions">
            <button className="btn btn-primary" onClick={() => grantAndReload(false)} type="button">
              Allow once (session)
            </button>
            <button className="btn" onClick={() => grantAndReload(true)} type="button">
              Always allow
            </button>
          </div>
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {entries && (
        <ul className="file-list">
          {entries.map((e) => (
            <li key={e.path}>
              <button
                className="file-row"
                onClick={() => navigateInto(e)}
                type="button"
                title={e.path}
              >
                <span className="file-icon">{e.is_dir ? 'dir' : 'file'}</span>
                <span className="file-name">{e.name}</span>
                {!e.is_dir && <span className="file-size">{prettyBytes(e.size)}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {preview && (
        <div className="file-preview">
          <div className="file-preview-header">
            <span>{preview.path}</span>
            <button className="pane-btn" onClick={() => setPreview(null)} type="button">
              ✕
            </button>
          </div>
          {preview.is_binary ? (
            <div className="file-preview-binary">[binary file, {prettyBytes(preview.bytes)}]</div>
          ) : (
            <pre className="file-preview-text">{preview.text}</pre>
          )}
          {preview.truncated && (
            <div className="file-preview-truncated">[truncated — file is {prettyBytes(preview.bytes)}]</div>
          )}
        </div>
      )}
    </div>
  );
}

function prettyBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
