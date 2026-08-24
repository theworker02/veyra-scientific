const { execFile } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const vscode = require("vscode");

const LAB = "http://127.0.0.1:8765";

function workspaceRoot() {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
}

function pythonBin() {
  const root = workspaceRoot();
  const local = [
    path.join(root, ".venv", "Scripts", "python.exe"),
    path.join(root, ".venv", "bin", "python"),
    path.join(root, "venv", "Scripts", "python.exe"),
    path.join(root, "venv", "bin", "python"),
  ].find((candidate) => fs.existsSync(candidate));
  return local || (process.platform === "win32" ? "python" : "python3");
}

function quote(bin) {
  return /\s/.test(bin) ? `"${bin}"` : bin;
}

function runVeyra(args) {
  const root = workspaceRoot();
  const attempts = [
    [pythonBin(), ["-m", "veyra", ...args]],
    ["veyra", args],
  ];
  const trySpawn = ([cmd, cmdArgs]) =>
    new Promise((ok, fail) => {
      execFile(cmd, cmdArgs, { cwd: root, windowsHide: true }, (error, stdout, stderr) => {
        if (error && !stdout) {
          fail(new Error(stderr || error.message));
          return;
        }
        ok(stdout || stderr);
      });
    });
  return (async () => {
    let last = new Error("veyra is not installed");
    for (const invocation of attempts) {
      try {
        return await trySpawn(invocation);
      } catch (error) {
        last = error;
      }
    }
    throw last;
  })();
}

function labUrl(model = "") {
  if (!model) return `${LAB}/`;
  return `${LAB}/?model=${encodeURIComponent(model)}`;
}

function modelFromEditor() {
  const document = vscode.window.activeTextEditor?.document;
  if (!document) return "";
  const match = document.getText().match(/^\s*model\s+(\S+)/m);
  return match ? match[1] : "";
}

async function labUp() {
  try {
    const response = await fetch(`${LAB}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForLab(ms = 10000) {
  const start = Date.now();
  while (Date.now() - start < ms) {
    if (await labUp()) return true;
    await sleep(400);
  }
  return false;
}

function startLabTerminal() {
  const existing = vscode.window.terminals.find((item) => item.name === "Veyra Lab");
  const term = existing || vscode.window.createTerminal({ name: "Veyra Lab", cwd: workspaceRoot() });
  term.sendText(`${quote(pythonBin())} -m veyra serve examples`);
  term.show(true);
  return term;
}

class LabTree {
  constructor() {
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    this.running = false;
  }

  refresh(running) {
    this.running = running;
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(item) {
    return item;
  }

  getChildren() {
    const rows = [
      ["Open Laboratory", "veyra.openWorkbench", this.running ? "Workbench is up" : "Starts the lab if it is down", "play"],
      ["New experiment", "veyra.newExperiment", "Write a .veyra file from the catalog", "file-add"],
      ["Start laboratory", "veyra.startLab", "python -m veyra serve examples", "terminal"],
      ["Doctor", "veyra.doctor", "Install or check the laboratory kernel", "pulse"],
      ["Catalog", "veyra.catalog", "Installed models", "book"],
      ["Run examples", "veyra.runAllTests", "veyra test examples", "beaker"],
    ];
    return rows.map(([label, command, tooltip, icon]) => {
      const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
      item.command = { command, title: label };
      item.tooltip = tooltip;
      item.contextValue = command;
      item.iconPath = new vscode.ThemeIcon(icon);
      return item;
    });
  }
}

function activate(context) {
  const diagnostics = vscode.languages.createDiagnosticCollection("veyra");
  const output = vscode.window.createOutputChannel("Veyra");
  const tree = new LabTree();
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 1000);
  status.command = "veyra.openWorkbench";
  status.show();
  let kernelInstalled = false;

  async function probeKernel() {
    try {
      await runVeyra(["--version"]);
      kernelInstalled = true;
      return true;
    } catch {
      kernelInstalled = false;
      status.text = "$(beaker) Veyra not installed";
      status.command = "veyra.doctor";
      status.tooltip = "The laboratory is not installed. Run Veyra: Doctor.";
      tree.refresh(false);
      return false;
    }
  }

  function installKernel() {
    const script = path.join(workspaceRoot(), "hooks", "bootstrap.py");
    const term =
      vscode.window.terminals.find((item) => item.name === "Veyra Doctor") ||
      vscode.window.createTerminal({ name: "Veyra Doctor", cwd: workspaceRoot() });
    term.sendText(`${quote(pythonBin())} "${script}" --dev`);
    term.show(true);
    vscode.window.showInformationMessage(
      "Installing the Veyra laboratory and Workbench extension. When it finishes, run Veyra: Doctor again.",
    );
  }

  async function offerDoctor() {
    const key = "veyra.offeredDoctor";
    if (context.globalState.get(key)) return;
    await context.globalState.update(key, true);
    const choice = await vscode.window.showWarningMessage(
      "The Veyra laboratory is not installed.",
      "Run Doctor",
    );
    if (choice === "Run Doctor") {
      await vscode.commands.executeCommand("veyra.doctor");
    }
  }

  async function setRunning(up) {
    tree.refresh(up);
    if (!kernelInstalled) {
      status.text = "$(beaker) Veyra not installed";
      status.command = "veyra.doctor";
      status.tooltip = "The laboratory is not installed. Run Veyra: Doctor.";
      return;
    }
    status.command = "veyra.openWorkbench";
    status.text = up ? "$(beaker) Veyra Ready" : "$(beaker) Veyra Offline";
    status.tooltip = up ? `Laboratory ${LAB}` : "Start the laboratory from the Veyra sidebar";
  }

  async function refreshHealth() {
    if (!kernelInstalled && !(await probeKernel())) {
      return;
    }
    try {
      const response = await fetch(`${LAB}/api/health`);
      if (!response.ok) {
        await setRunning(false);
        return;
      }
      const payload = await response.json();
      tree.refresh(true);
      status.command = "veyra.openWorkbench";
      status.text = `$(beaker) Veyra ${payload.veyra || "Ready"}`;
      status.tooltip = `Laboratory ${LAB} · ${payload.models ?? ""} models`;
    } catch {
      await setRunning(false);
    }
  }

  async function showOutput(title, body) {
    output.clear();
    output.appendLine(title);
    output.appendLine(body.trimEnd());
    output.show(true);
  }

  async function refreshLens(document) {
    if (!document || document.languageId !== "python") return;
    try {
      const out = await runVeyra(["lens", "--file", document.fileName, "--json"]);
      const parsed = JSON.parse(out.slice(out.indexOf("{")));
      const hits = parsed.details?.hits || [];
      const items = hits
        .filter((hit) => hit.ok === false)
        .map((hit) => {
          const range = document.lineAt(Math.max(0, (hit.line || 1) - 1)).range;
          return new vscode.Diagnostic(
            range,
            `Veyra Lens: ${hit.message || "scientific inconsistency"}`,
            vscode.DiagnosticSeverity.Warning,
          );
        });
      diagnostics.set(document.uri, items);
    } catch {
      diagnostics.delete(document.uri);
    }
  }

  async function refreshExperiment(document) {
    if (!document || document.languageId !== "veyra") return;
    try {
      const out = await runVeyra(["run", document.fileName, "--json"]);
      const parsed = JSON.parse(out.slice(out.indexOf("{")));
      const failed = (parsed.checks || []).filter((check) => check.passed === false);
      const items = failed.map(
        (check) =>
          new vscode.Diagnostic(
            document.lineAt(0).range,
            `Veyra: ${check.name}${check.detail ? ` — ${check.detail}` : ""}`,
            vscode.DiagnosticSeverity.Error,
          ),
      );
      diagnostics.set(document.uri, items);
    } catch (error) {
      diagnostics.set(document.uri, [
        new vscode.Diagnostic(
          document.lineAt(0).range,
          `Veyra: ${error instanceof Error ? error.message : "run failed"}`,
          vscode.DiagnosticSeverity.Error,
        ),
      ]);
    }
  }

  async function openLaboratory(model) {
    if (!(await probeKernel())) {
      await offerDoctor();
      return;
    }
    const name = typeof model === "string" && /^[A-Za-z][\w-]*$/.test(model) ? model : modelFromEditor();
    const target = labUrl(name);
    if (!(await labUp())) {
      startLabTerminal();
      await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "Starting Veyra laboratory…" },
        async () => {
          await waitForLab();
        },
      );
    }
    if (await labUp()) {
      await setRunning(true);
      try {
        await vscode.commands.executeCommand("simpleBrowser.show", target);
        return;
      } catch {
        const panel = vscode.window.createWebviewPanel("veyraWorkbench", "Veyra Laboratory", vscode.ViewColumn.Beside, {
          enableScripts: true,
        });
        panel.webview.html = `<!DOCTYPE html><html><body style="margin:0;height:100vh;background:#ffffff">
          <iframe src="${target}" style="border:0;width:100%;height:100%"></iframe>
        </body></html>`;
        return;
      }
    }
    vscode.window.showWarningMessage("Veyra laboratory did not start. Run Veyra: Doctor, then Open Laboratory.");
  }

  context.subscriptions.push(
    diagnostics,
    output,
    status,
    vscode.window.registerTreeDataProvider("veyra.lab", tree),
    vscode.commands.registerCommand("veyra.openWorkbench", openLaboratory),
    vscode.commands.registerCommand("veyra.openInLab", () => openLaboratory(modelFromEditor())),
    vscode.languages.registerCodeLensProvider("veyra", {
      provideCodeLenses(document) {
        const lenses = [];
        for (let i = 0; i < document.lineCount; i++) {
          const line = document.lineAt(i);
          if (/^\s*experiment\s+\S+/.test(line.text)) {
            lenses.push(
              new vscode.CodeLens(line.range, {
                title: "Run with Veyra",
                command: "veyra.runExperiment",
              }),
            );
          }
          const model = line.text.match(/^\s*model\s+(\S+)/);
          if (model) {
            lenses.push(
              new vscode.CodeLens(line.range, {
                title: "Open in Laboratory",
                command: "veyra.openWorkbench",
                arguments: [model[1]],
              }),
            );
          }
        }
        return lenses;
      },
    }),
    vscode.commands.registerCommand("veyra.startLab", async () => {
      if (!(await probeKernel())) {
        await offerDoctor();
        return;
      }
      startLabTerminal();
      vscode.window.showInformationMessage("Veyra Lab terminal is starting the laboratory.");
    }),
    vscode.commands.registerCommand("veyra.runExperiment", async () => {
      const file = vscode.window.activeTextEditor?.document.fileName;
      if (!file) return;
      const out = await runVeyra(["run", file]);
      await showOutput("Run", out);
      vscode.window.showInformationMessage(out.split("\n").slice(0, 2).join(" · "));
    }),
    vscode.commands.registerCommand("veyra.runAllTests", async () => {
      const out = await runVeyra(["test", "examples"]);
      await showOutput("Suite", out);
      vscode.window.showInformationMessage("Veyra suite finished. See the Veyra output channel.");
    }),
    vscode.commands.registerCommand("veyra.doctor", async () => {
      try {
        const out = await runVeyra(["doctor"]);
        kernelInstalled = true;
        await showOutput("Doctor", out);
        vscode.window.showInformationMessage("Veyra laboratory is installed.");
        void refreshHealth();
      } catch {
        output.clear();
        output.appendLine("The Veyra laboratory is not installed.");
        output.appendLine("Installing the kernel and Workbench extension into this folder…");
        output.show(true);
        installKernel();
      }
    }),
    vscode.commands.registerCommand("veyra.catalog", async () => {
      const out = await runVeyra(["catalog"]);
      await showOutput("Catalog", out);
    }),
    vscode.commands.registerCommand("veyra.newExperiment", async () => {
      let payload;
      try {
        const raw = await runVeyra(["catalog", "--json"]);
        payload = JSON.parse(raw.slice(raw.indexOf("{")));
      } catch (error) {
        vscode.window.showErrorMessage(error instanceof Error ? error.message : "Catalog unavailable");
        return;
      }
      const picked = await vscode.window.showQuickPick(
        (payload.entries || []).map((entry) => ({
          label: entry.title,
          description: entry.id,
          detail: entry.group,
        })),
        { placeHolder: "Catalog model" },
      );
      if (!picked) return;
      const dest = await vscode.window.showSaveDialog({
        defaultUri: vscode.Uri.file(path.join(workspaceRoot(), `${picked.description}.veyra`)),
        filters: { Veyra: ["veyra"] },
      });
      if (!dest) return;
      await runVeyra(["init", picked.description, "--out", dest.fsPath]);
      const document = await vscode.workspace.openTextDocument(dest);
      await vscode.window.showTextDocument(document);
    }),
    vscode.languages.registerHoverProvider("veyra", {
      async provideHover(document, position) {
        const line = document.lineAt(position.line).text;
        const model = line.match(/^\s*model\s+(\S+)/);
        if (!model) return null;
        try {
          const raw = await runVeyra(["catalog", "--json"]);
          const payload = JSON.parse(raw.slice(raw.indexOf("{")));
          const entry = (payload.entries || []).find((item) => item.id === model[1] || (item.aliases || []).includes(model[1]));
          if (!entry) return new vscode.Hover(new vscode.MarkdownString(`Unknown catalog model \`${model[1]}\`.`));
          const body = [`**${entry.title}**`, entry.group, entry.summary, "", `Open with **Veyra: Open in Laboratory**.`].join("\n\n");
          return new vscode.Hover(new vscode.MarkdownString(body));
        } catch {
          return null;
        }
      },
    }),
    vscode.languages.registerHoverProvider("python", {
      async provideHover(document, position) {
        const line = document.lineAt(position.line).text;
        if (!line.includes("=") || !(line.includes("*") || line.includes("/"))) return null;
        const expr = line.split("=").slice(1).join("=").trim();
        try {
          const out = await runVeyra(["lens", expr, "--json"]);
          const parsed = JSON.parse(out.slice(out.indexOf("{")));
          const model = parsed.metrics?.find((m) => m.name === "detected model")?.value;
          const dim = parsed.metrics?.find((m) => m.name === "dimension")?.value;
          const ok = parsed.ok ? "consistent" : "inconsistent";
          const body = ["**Veyra Lens**", model ? `Detected: ${model}` : "Unrecognized expression", dim ? `Dimension: ${dim}` : "", `Integrity: ${ok}`]
            .filter(Boolean)
            .join("\n\n");
          return new vscode.Hover(new vscode.MarkdownString(body));
        } catch {
          return null;
        }
      },
    }),
    vscode.workspace.onDidSaveTextDocument((document) => {
      void refreshLens(document);
      void refreshExperiment(document);
    }),
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (!editor) return;
      void refreshLens(editor.document);
      void refreshExperiment(editor.document);
    }),
  );

  const timer = setInterval(() => {
    void refreshHealth();
  }, 8000);
  context.subscriptions.push({ dispose: () => clearInterval(timer) });

  void (async () => {
    if (!(await probeKernel())) {
      await offerDoctor();
      return;
    }
    void refreshHealth();
    if (vscode.window.activeTextEditor) {
      void refreshLens(vscode.window.activeTextEditor.document);
      void refreshExperiment(vscode.window.activeTextEditor.document);
    }
  })();
}

function deactivate() {}

module.exports = { activate, deactivate };
