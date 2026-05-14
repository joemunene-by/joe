/**
 * Bottom status strip. Shows the current working directory and a
 * small "sandboxed" indicator so the user is reminded that every
 * native action is permission-gated.
 */

interface Props {
  cwd: string;
}

export default function StatusBar({ cwd }: Props) {
  return (
    <div className="status-bar">
      <span className="status-label">cwd</span>
      <span className="status-cwd" title={cwd}>
        {cwd}
      </span>
      <span className="status-spacer" />
      <span className="status-sandbox">sandboxed</span>
    </div>
  );
}
