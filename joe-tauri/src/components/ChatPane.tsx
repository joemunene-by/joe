/**
 * Chat surface that drives the joe sidecar.
 *
 *   - User types a prompt, presses Enter, we call agent.run()
 *   - Backend spawns the joe CLI and streams output as Tauri events.
 *     stderr is folded into joe://stdout with a [stderr] prefix, so a
 *     single line listener handles both.
 *   - We append each line to the in-flight agent message and finalize
 *     when joe://done arrives.
 *
 * Shift+Enter inserts a newline. Enter sends.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { listen } from '@tauri-apps/api/event';
import type { UnlistenFn } from '@tauri-apps/api/event';
import { agent } from '../lib/invoke';

interface Message {
  id: number;
  role: 'user' | 'agent';
  text: string;
  done: boolean;
  exitCode: number | null;
}

let nextId = 0;

function formatAgentError(err: unknown): string {
  if (typeof err === 'object' && err && 'kind' in err) {
    const e = err as { kind: string; message?: string };
    if (e.kind === 'joe_not_found') {
      return 'joe binary not found. Set JOE_BIN or install joe on PATH.';
    }
    if (e.kind === 'spawn_failed') {
      return `failed to spawn joe: ${e.message ?? 'unknown reason'}`;
    }
    return e.kind;
  }
  return String(err);
}

export default function ChatPane() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Subscribe to the joe sidecar event stream.
  useEffect(() => {
    let mounted = true;
    let unlisteners: UnlistenFn[] = [];

    (async () => {
      // Backend merges stderr into the stdout channel (with a "[stderr] "
      // prefix), so we only need one line listener.
      const u1 = await listen<{ line: string }>('joe://stdout', (e) => {
        appendAgentLine(e.payload.line);
      });
      const u2 = await listen<{ exit_code: number }>('joe://done', (e) => {
        finalizeAgent(e.payload.exit_code);
        setRunning(false);
      });
      if (!mounted) {
        u1();
        u2();
        return;
      }
      unlisteners = [u1, u2];
    })();

    return () => {
      mounted = false;
      unlisteners.forEach((u) => u());
    };
  }, []);

  // Scroll on new messages.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const appendAgentLine = useCallback((line: string) => {
    setMessages((m) => {
      const last = m[m.length - 1];
      if (last && last.role === 'agent' && !last.done) {
        const updated: Message = { ...last, text: last.text + line + '\n' };
        return [...m.slice(0, -1), updated];
      }
      // No active agent message; create one (defensive: should not
      // normally happen because we add the placeholder on send).
      return [
        ...m,
        { id: ++nextId, role: 'agent', text: line + '\n', done: false, exitCode: null },
      ];
    });
  }, []);

  const finalizeAgent = useCallback((exitCode: number) => {
    setMessages((m) => {
      const last = m[m.length - 1];
      if (last && last.role === 'agent' && !last.done) {
        const updated: Message = { ...last, done: true, exitCode };
        return [...m.slice(0, -1), updated];
      }
      return m;
    });
  }, []);

  const send = async () => {
    const text = prompt.trim();
    if (!text || running) return;
    setError(null);
    setPrompt('');
    setRunning(true);
    setMessages((m) => [
      ...m,
      { id: ++nextId, role: 'user', text, done: true, exitCode: null },
      { id: ++nextId, role: 'agent', text: '', done: false, exitCode: null },
    ]);
    try {
      await agent.run(text);
    } catch (err) {
      setRunning(false);
      setError(formatAgentError(err));
      // Mark the empty agent placeholder as done so a new one can start.
      finalizeAgent(-1);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="chat-pane">
      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">Ask joe anything. Shift+Enter for newline.</div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`chat-msg chat-msg-${m.role}`}>
            {m.text || (m.role === 'agent' && !m.done ? '...' : '')}
            {m.role === 'agent' && m.done && m.exitCode !== null && m.exitCode !== 0 && (
              <div className="chat-msg-exit">[exit {m.exitCode}]</div>
            )}
          </div>
        ))}
        {error && <div className="error-box">{error}</div>}
      </div>
      <div className="chat-input-area">
        <textarea
          className="chat-input"
          placeholder={running ? 'joe is thinking...' : 'Ask joe...'}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={running}
          rows={2}
        />
        <button
          className="btn btn-primary"
          onClick={send}
          disabled={running || !prompt.trim()}
          type="button"
        >
          Send
        </button>
      </div>
    </div>
  );
}
