// joe-vscode: VS Code extension that talks to a local joe-http server.
//
// Three entry points:
//   - joe.ask              -> input box, sends to /v1/chat/completions,
//                             streams the answer into a notification.
//   - joe.askSelection     -> sends current selection as quoted context
//                             plus an input-box question, opens result
//                             in an output channel.
//   - joe.openChat sidebar -> webview that talks to /chat-stream (SSE)
//                             with a persistent transcript.
//
// All endpoints come from the `joe.httpUrl` setting (default
// http://127.0.0.1:8765). Auth via the `joe.httpToken` setting or the
// JOE_HTTP_TOKEN environment variable, whichever is set first.

import * as vscode from "vscode";
import * as http from "http";
import * as https from "https";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

function config(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration("joe");
}

function httpBase(): string {
  const v = (config().get<string>("httpUrl") || "").trim();
  return v.replace(/\/$/, "") || "http://127.0.0.1:8765";
}

function token(): string {
  const fromSetting = (config().get<string>("httpToken") || "").trim();
  if (fromSetting) return fromSetting;
  const fromEnv = (process.env.JOE_HTTP_TOKEN || "").trim();
  if (fromEnv) return fromEnv;
  try {
    const p = path.join(os.homedir(), ".joe-agent", "http-token");
    return fs.readFileSync(p, "utf8").trim();
  } catch {
    return "";
  }
}

function model(): string {
  return (config().get<string>("model") || "joe-gemma").trim();
}

interface ChatChoice {
  message: { role: string; content: string };
}
interface ChatResponse {
  choices: ChatChoice[];
}

/**
 * One-shot ask via /v1/chat/completions (non-streaming). Returns the
 * assistant text. Throws on HTTP/connect errors.
 */
async function askOnce(prompt: string): Promise<string> {
  const base = httpBase();
  const url = base + "/v1/chat/completions";
  const tok = token();
  const body = JSON.stringify({
    model: model(),
    messages: [{ role: "user", content: prompt }],
    stream: false,
  });
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const lib = u.protocol === "https:" ? https : http;
    const req = lib.request(
      {
        method: "POST",
        hostname: u.hostname,
        port: u.port,
        path: u.pathname,
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body).toString(),
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
        },
        timeout: 600_000,
      },
      (res) => {
        let raw = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          if (!res.statusCode || res.statusCode >= 400) {
            return reject(
              new Error(`joe-http ${res.statusCode}: ${raw.slice(0, 240)}`),
            );
          }
          try {
            const parsed = JSON.parse(raw) as ChatResponse;
            const text =
              parsed.choices?.[0]?.message?.content?.trim() ||
              "(empty response)";
            resolve(text);
          } catch (e) {
            reject(new Error(`bad JSON from joe-http: ${(e as Error).message}`));
          }
        });
      },
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy(new Error("joe-http request timed out after 10m"));
    });
    req.write(body);
    req.end();
  });
}

function logChannel(): vscode.OutputChannel {
  if (!(globalThis as any).__joeChannel) {
    (globalThis as any).__joeChannel = vscode.window.createOutputChannel("joe");
  }
  return (globalThis as any).__joeChannel as vscode.OutputChannel;
}

async function cmdAsk() {
  const prompt = await vscode.window.showInputBox({
    prompt: "Ask joe",
    placeHolder: "what does this function do?",
  });
  if (!prompt) return;
  const ch = logChannel();
  ch.show(true);
  ch.appendLine(`\n>>> ${prompt}\n`);
  try {
    const text = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "joe is thinking..." },
      () => askOnce(prompt),
    );
    ch.appendLine(text);
  } catch (e) {
    const msg = (e as Error).message;
    ch.appendLine(`[error] ${msg}`);
    vscode.window.showErrorMessage(`joe: ${msg}`);
  }
}

async function cmdAskSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("joe: no active editor");
    return;
  }
  const sel = editor.document.getText(editor.selection);
  if (!sel.trim()) {
    vscode.window.showWarningMessage("joe: nothing selected");
    return;
  }
  const question = await vscode.window.showInputBox({
    prompt: `Ask joe about this ${sel.split("\n").length}-line selection`,
    placeHolder: "explain / refactor / spot the bug / etc.",
  });
  if (!question) return;
  const lang = editor.document.languageId;
  const filename = path.basename(editor.document.uri.fsPath);
  const wrapped =
    `Question: ${question}\n\n` +
    `Context: \`${filename}\`, language \`${lang}\`, ` +
    `lines ${editor.selection.start.line + 1}-${editor.selection.end.line + 1}.\n\n` +
    `\`\`\`${lang}\n${sel}\n\`\`\``;
  const ch = logChannel();
  ch.show(true);
  ch.appendLine(`\n>>> [selection from ${filename}] ${question}\n`);
  try {
    const text = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "joe is thinking..." },
      () => askOnce(wrapped),
    );
    ch.appendLine(text);
  } catch (e) {
    const msg = (e as Error).message;
    ch.appendLine(`[error] ${msg}`);
    vscode.window.showErrorMessage(`joe: ${msg}`);
  }
}

function cmdOpenDashboard() {
  const tok = token();
  const base = httpBase();
  const url = tok ? `${base}/dashboard?token=${encodeURIComponent(tok)}` : `${base}/dashboard`;
  vscode.env.openExternal(vscode.Uri.parse(url));
}

class JoeChatViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "joe.chatView";
  constructor(private readonly extensionUri: vscode.Uri) {}

  resolveWebviewView(view: vscode.WebviewView) {
    view.webview.options = { enableScripts: true };
    view.webview.html = this.html(view.webview);
    view.webview.onDidReceiveMessage(async (msg) => {
      if (msg?.type === "ask") {
        try {
          const text = await askOnce(msg.prompt);
          view.webview.postMessage({ type: "reply", text });
        } catch (e) {
          view.webview.postMessage({
            type: "reply",
            text: `[error] ${(e as Error).message}`,
          });
        }
      } else if (msg?.type === "openExternal") {
        const tok = token();
        const url = `${httpBase()}/dashboard${tok ? `?token=${encodeURIComponent(tok)}` : ""}`;
        vscode.env.openExternal(vscode.Uri.parse(url));
      }
    });
  }

  private html(_w: vscode.Webview): string {
    return /* html */ `<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body { font: 13px/1.45 -apple-system, BlinkMacSystemFont, sans-serif;
         color: var(--vscode-foreground); background: var(--vscode-sideBar-background);
         margin: 0; padding: 10px; display: flex; flex-direction: column;
         min-height: 100vh; }
  h2 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
       margin: 0 0 6px; color: var(--vscode-descriptionForeground); }
  #log { flex: 1; overflow-y: auto; white-space: pre-wrap;
         font: 12px/1.4 ui-monospace, SFMono-Regular, monospace;
         border: 1px solid var(--vscode-input-border, transparent);
         padding: 8px; min-height: 100px; margin-bottom: 8px;
         background: var(--vscode-editor-background); border-radius: 3px; }
  .user { color: var(--vscode-charts-blue); font-weight: 600; margin-top: 8px; }
  .err { color: var(--vscode-errorForeground); }
  textarea { width: 100%; min-height: 60px; resize: vertical;
             font: 12px/1.4 ui-monospace, SFMono-Regular, monospace;
             background: var(--vscode-input-background); color: var(--vscode-input-foreground);
             border: 1px solid var(--vscode-input-border, transparent);
             padding: 6px; border-radius: 3px; }
  .row { display: flex; gap: 6px; margin-top: 6px; }
  button { background: var(--vscode-button-background); color: var(--vscode-button-foreground);
           border: 0; padding: 6px 12px; cursor: pointer; border-radius: 3px;
           font: 12px/1 -apple-system, sans-serif; }
  button:hover { background: var(--vscode-button-hoverBackground); }
  .alt { background: transparent; color: var(--vscode-foreground);
         border: 1px solid var(--vscode-button-border, transparent); }
  a { color: var(--vscode-textLink-foreground); cursor: pointer; }
</style></head>
<body>
  <h2>joe chat <a id="openExt">[open dashboard]</a></h2>
  <div id="log">Hi. Type a question below and hit Enter.</div>
  <form id="f"><textarea id="i" placeholder="ask joe..." rows="3"></textarea>
    <div class="row">
      <button type="submit">Ask</button>
      <button type="button" class="alt" id="clr">Clear</button>
    </div>
  </form>
<script>
  const vscode = acquireVsCodeApi();
  const logEl = document.getElementById('log');
  const i = document.getElementById('i');
  document.getElementById('f').addEventListener('submit', (e) => {
    e.preventDefault();
    const prompt = i.value.trim();
    if (!prompt) return;
    logEl.innerHTML += '<div class="user">&gt; ' + prompt.replace(/</g, '&lt;') + '</div>';
    logEl.innerHTML += '<div id="pending" style="opacity:0.6">thinking…</div>';
    logEl.scrollTop = logEl.scrollHeight;
    i.value = '';
    vscode.postMessage({type: 'ask', prompt});
  });
  document.getElementById('clr').addEventListener('click', () => { logEl.innerHTML = ''; });
  document.getElementById('openExt').addEventListener('click', () => {
    vscode.postMessage({type: 'openExternal'});
  });
  window.addEventListener('message', (e) => {
    const m = e.data;
    if (m?.type === 'reply') {
      const p = document.getElementById('pending');
      if (p) p.remove();
      const div = document.createElement('div');
      div.textContent = m.text;
      if (m.text.startsWith('[error]')) div.className = 'err';
      logEl.appendChild(div);
      logEl.scrollTop = logEl.scrollHeight;
    }
  });
</script>
</body></html>`;
  }
}

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.commands.registerCommand("joe.ask", cmdAsk),
    vscode.commands.registerCommand("joe.askSelection", cmdAskSelection),
    vscode.commands.registerCommand("joe.openDashboard", cmdOpenDashboard),
    vscode.commands.registerCommand("joe.openChat", () => {
      vscode.commands.executeCommand("workbench.view.extension.joe-sidebar");
    }),
    vscode.window.registerWebviewViewProvider(
      JoeChatViewProvider.viewType,
      new JoeChatViewProvider(context.extensionUri),
    ),
  );
}

export function deactivate() {}
