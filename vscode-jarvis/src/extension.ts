import * as vscode from 'vscode';

const API_URL = () =>
    vscode.workspace.getConfiguration('jarvis').get<string>('apiUrl', 'http://localhost:8000');

// ── Chat WebView ──────────────────────────────────────────────────────────────

function getChatHtml(nonce: string): string {
    return `<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <style>
    body { font-family: var(--vscode-font-family); font-size: 13px;
           background: var(--vscode-editor-background);
           color: var(--vscode-editor-foreground); margin: 0; padding: 8px; }
    #messages { height: calc(100vh - 80px); overflow-y: auto;
                display: flex; flex-direction: column; gap: 8px; }
    .msg { padding: 8px 10px; border-radius: 6px; max-width: 90%; word-wrap: break-word; }
    .user { background: var(--vscode-button-background);
            color: var(--vscode-button-foreground); align-self: flex-end; }
    .jarvis { background: var(--vscode-editor-inactiveSelectionBackground);
              align-self: flex-start; white-space: pre-wrap; }
    .label { font-size: 10px; opacity: 0.6; margin-bottom: 2px; }
    #input-row { display: flex; gap: 6px; margin-top: 8px; }
    #input { flex: 1; background: var(--vscode-input-background);
             color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border);
             padding: 6px; border-radius: 4px; }
    button { background: var(--vscode-button-background);
             color: var(--vscode-button-foreground); border: none;
             padding: 6px 12px; border-radius: 4px; cursor: pointer; }
    button:hover { background: var(--vscode-button-hoverBackground); }
    #status { font-size: 10px; opacity: 0.5; padding: 2px 0; }
  </style>
</head>
<body>
  <div id="messages"></div>
  <div id="status">Gotowy</div>
  <div id="input-row">
    <input id="input" type="text" placeholder="Wpisz pytanie..." autocomplete="off"/>
    <button onclick="send()">Wyślij</button>
  </div>
<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();
  let history = [];

  function addMessage(role, text) {
    const box = document.getElementById('messages');
    const wrap = document.createElement('div');
    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = role === 'user' ? 'Ty' : 'J.A.R.V.I.S.';
    const msg = document.createElement('div');
    msg.className = 'msg ' + role;
    msg.textContent = text;
    wrap.appendChild(label);
    wrap.appendChild(msg);
    box.appendChild(wrap);
    box.scrollTop = box.scrollHeight;
  }

  function send() {
    const input = document.getElementById('input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage('user', text);
    document.getElementById('status').textContent = 'Jarvis myśli...';
    vscode.postMessage({ type: 'chat', message: text, history });
  }

  document.getElementById('input').addEventListener('keydown', e => {
    if (e.key === 'Enter') send();
  });

  window.addEventListener('message', e => {
    const msg = e.data;
    if (msg.type === 'response') {
      addMessage('jarvis', msg.text);
      history = msg.history;
      document.getElementById('status').textContent = 'Gotowy';
    } else if (msg.type === 'inject') {
      document.getElementById('input').value = msg.text;
      document.getElementById('input').focus();
    } else if (msg.type === 'error') {
      document.getElementById('status').textContent = 'Błąd: ' + msg.text;
    }
  });
</script>
</body>
</html>`;
}

// ── Extension ─────────────────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext) {
    let chatPanel: vscode.WebviewPanel | undefined;

    // Otwórz panel czatu
    const openChat = vscode.commands.registerCommand('jarvis.openChat', () => {
        if (chatPanel) { chatPanel.reveal(); return; }

        chatPanel = vscode.window.createWebviewPanel(
            'jarvisChat', 'J.A.R.V.I.S.', vscode.ViewColumn.Beside,
            { enableScripts: true, retainContextWhenHidden: true }
        );
        const nonce = Math.random().toString(36).slice(2);
        chatPanel.webview.html = getChatHtml(nonce);
        chatPanel.onDidDispose(() => { chatPanel = undefined; });

        chatPanel.webview.onDidReceiveMessage(async (msg) => {
            if (msg.type !== 'chat') return;
            try {
                const res = await fetch(`${API_URL()}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg.message, history: msg.history })
                });
                const data = await res.json();
                chatPanel?.webview.postMessage({
                    type: 'response',
                    text: data.response,
                    history: data.history
                });
            } catch (e: any) {
                chatPanel?.webview.postMessage({ type: 'error', text: e.message });
                vscode.window.showErrorMessage(
                    `J.A.R.V.I.S.: Brak połączenia z API (${API_URL()})`
                );
            }
        });
    });

    // Zapytaj o zaznaczony kod
    const askSelection = vscode.commands.registerCommand('jarvis.askSelection', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) return;
        const selected = editor.document.getText(editor.selection);
        if (!selected) { vscode.window.showWarningMessage('Zaznacz kod!'); return; }

        const question = await vscode.window.showInputBox({
            prompt: 'Zapytaj Jarvisa o ten kod',
            placeHolder: 'np. wyjaśnij, zoptymalizuj, znajdź błąd...'
        });
        if (!question) return;

        vscode.commands.executeCommand('jarvis.openChat');
        setTimeout(() => {
            chatPanel?.webview.postMessage({
                type: 'inject',
                text: `${question}\n\`\`\`\n${selected.slice(0, 2000)}\n\`\`\``
            });
        }, 500);
    });

    // Agent Mode z input box
    const runAgent = vscode.commands.registerCommand('jarvis.runAgent', async () => {
        const task = await vscode.window.showInputBox({
            prompt: 'Zadanie dla Jarvisa (Agent Mode)',
            placeHolder: 'np. utwórz testy dla auth.py, zoptymalizuj SQL w models.py'
        });
        if (!task) return;

        await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: 'J.A.R.V.I.S. Agent...', cancellable: false },
            async () => {
                try {
                    const res = await fetch(`${API_URL()}/agent`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ task, verbose: false })
                    });
                    const data = await res.json();
                    vscode.window.showInformationMessage(`JARVIS: ${data.result.slice(0, 200)}`);
                } catch (e: any) {
                    vscode.window.showErrorMessage(`Agent błąd: ${e.message}`);
                }
            }
        );
    });

    // Pokaż pamięć
    const showMemory = vscode.commands.registerCommand('jarvis.showMemory', async () => {
        try {
            const res = await fetch(`${API_URL()}/memory`);
            const data = await res.json();
            const doc = await vscode.workspace.openTextDocument({
                content: JSON.stringify(data, null, 2),
                language: 'json'
            });
            vscode.window.showTextDocument(doc);
        } catch (e: any) {
            vscode.window.showErrorMessage(`Błąd: ${e.message}`);
        }
    });

    context.subscriptions.push(openChat, askSelection, runAgent, showMemory);

    vscode.window.setStatusBarMessage('$(robot) J.A.R.V.I.S. aktywny', 3000);
}

export function deactivate() {}
