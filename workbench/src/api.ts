import type { CatalogPayload, Experiment, HealthPayload, SessionPayload } from "./types";

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as { error?: string } & T;
  if (!response.ok) {
    throw new Error(payload.error || fallback);
  }
  return payload;
}

export async function loadSession(force = false): Promise<SessionPayload> {
  if (!force && window.__VEYRA_SESSION__) {
    return window.__VEYRA_SESSION__;
  }
  const response = await fetch("/api/session");
  const payload = await readJson<SessionPayload>(response, "Laboratory session unavailable");
  window.__VEYRA_SESSION__ = payload;
  return payload;
}

export async function loadCatalog(): Promise<CatalogPayload> {
  const response = await fetch("/api/catalog");
  return readJson<CatalogPayload>(response, "Catalog unavailable");
}

export async function loadHealth(): Promise<HealthPayload> {
  const response = await fetch("/api/health");
  return readJson<HealthPayload>(response, "Kernel unreachable");
}

export async function runModel(model: string, params: Record<string, number | string> = {}): Promise<Experiment> {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, ...params }),
  });
  return readJson<Experiment>(response, "Run failed");
}

export async function runSuite(): Promise<Experiment> {
  const response = await fetch("/api/suite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  return readJson<Experiment>(response, "Suite failed");
}

export async function compareRuns(a: string, b: string): Promise<Experiment> {
  const response = await fetch(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
  return readJson<Experiment>(response, "Compare failed");
}

export async function runMath(expression: string, action = "auto", variable = "x"): Promise<Experiment> {
  const response = await fetch("/api/math", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expression, action, variable }),
  });
  return readJson<Experiment>(response, "Mathematics failed");
}

export async function runLens(payload: { expression?: string; source?: string }): Promise<Experiment> {
  const response = await fetch("/api/lens", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<Experiment>(response, "Lens failed");
}

export async function runConvert(value: string, to: string, from = ""): Promise<Experiment> {
  const response = await fetch("/api/convert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value, to, from }),
  });
  return readJson<Experiment>(response, "Conversion failed");
}

export async function organizeRun(action: "pin" | "unpin" | "delete" | "rename", runId: string, title = ""): Promise<SessionPayload> {
  const response = await fetch("/api/organize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, run_id: runId, title }),
  });
  return readJson<SessionPayload>(response, "Organize failed");
}

export async function runVerify(source: string): Promise<Experiment> {
  const response = await fetch("/api/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  });
  return readJson<Experiment>(response, "Verify failed");
}

export async function runSensitivity(expression: string, variables: Record<string, number>): Promise<Experiment> {
  const response = await fetch("/api/sensitivity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expression, variables }),
  });
  return readJson<Experiment>(response, "Sensitivity failed");
}

export async function loadDataFiles(): Promise<{ name: string; relative: string; path: string }[]> {
  const response = await fetch("/api/data-files");
  const payload = await readJson<{ files?: { name: string; relative: string; path: string }[] }>(
    response,
    "Data files unavailable",
  );
  return payload.files || [];
}

export async function runMeasure(payload: {
  csv?: string;
  path?: string;
  x?: string;
  y?: string;
  x_unit?: string;
  y_unit?: string;
  fit?: string;
  overlay?: string;
}): Promise<Experiment> {
  const response = await fetch("/api/measure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<Experiment>(response, "Measurement failed");
}

export async function runFit(x: number[], y: number[], model = "linear"): Promise<Experiment> {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: "fit", x, y, fit_model: model }),
  });
  return readJson<Experiment>(response, "Fit failed");
}

export async function loadProtocol(runId: string): Promise<string> {
  const response = await fetch(`/api/protocol?run=${encodeURIComponent(runId)}`);
  const payload = await readJson<{ methods?: string }>(response, "Protocol unavailable");
  return payload.methods || "";
}

export async function runUncertainty(
  expression: string,
  variables: Record<string, [number, number]>,
): Promise<Experiment> {
  const response = await fetch("/api/uncertainty", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expression, variables }),
  });
  return readJson<Experiment>(response, "Uncertainty failed");
}

export async function runSweep(
  model: string,
  param: string,
  start: number,
  stop: number,
  steps: number,
  base: Record<string, number | string> = {},
): Promise<Experiment> {
  const response = await fetch("/api/sweep", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, param, start, stop, steps, ...base }),
  });
  return readJson<Experiment>(response, "Sweep failed");
}

export async function reproduceRun(runId: string): Promise<Experiment> {
  const response = await fetch("/api/reproduce", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run: runId }),
  });
  return readJson<Experiment>(response, "Reproduce failed");
}

export async function runGeometry(kind: string, radius: number): Promise<Experiment> {
  const body: Record<string, unknown> = { kind, radius };
  if (kind === "volume_box") body.dimensions = [radius, radius, radius];
  if (kind === "triangle") body.points = [[0, 0], [radius, 0], [0, radius]];
  const response = await fetch("/api/geometry", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJson<Experiment>(response, "Geometry failed");
}

export async function runFourier(values: number[], sampleRate = 1): Promise<Experiment> {
  const response = await fetch("/api/fourier", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values, sample_rate: sampleRate }),
  });
  return readJson<Experiment>(response, "Fourier failed");
}
