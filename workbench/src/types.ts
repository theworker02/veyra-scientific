export type PlotSeries = {
  id: string;
  x: number[];
  y: number[];
};

export type PlotPayload = {
  kind: string;
  x_label: string;
  y_label: string;
  series: PlotSeries[];
  envelope?: { x: number[]; y_lo: number[]; y_hi: number[] };
  secondary?: PlotPayload;
};

export type Metric = {
  name: string;
  value: number | string;
  unit?: string;
  uncertainty?: number | null;
  text: string;
};

export type Check = {
  name: string;
  passed: boolean;
  detail?: string;
};

export type RangeRow = {
  angle_deg: number;
  range: number;
  peak: number;
  time: number;
};

export type LensHit = {
  line?: number;
  lhs?: string;
  expression?: string;
  ok?: boolean;
  model?: string;
  message?: string;
};

export type TableRow = Record<string, number | string | boolean>;

export type Experiment = {
  title: string;
  kind: string;
  solver: string;
  run_id: string;
  ok: boolean;
  integrity: number;
  integrityLabel: string;
  integrityPct: string;
  inputs: Record<string, string>;
  metrics: Metric[];
  checks: Check[];
  warnings?: string[];
  plot?: PlotPayload | null;
  created_at?: string;
  veyra_version?: string;
  model?: string | null;
  methods?: string;
  table?: RangeRow[] | TableRow[] | null;
  hits?: LensHit[] | null;
  pinned?: boolean;
  alias?: string;
};

export type HistoryRow = {
  run_id?: string;
  title?: string;
  kind?: string;
  ok?: boolean;
  created_at?: string;
};

export type SessionPayload = {
  veyra: string;
  tagline: string;
  experiments: Experiment[];
  history: HistoryRow[];
  count?: number;
  pinned?: string[];
  titles?: Record<string, string>;
};

export type CatalogParam = {
  name: string;
  label: string;
  type: "number" | "integer" | string;
  default: number;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
};

export type CatalogEntry = {
  id: string;
  title: string;
  group: string;
  summary: string;
  aliases?: string[];
  params: CatalogParam[];
};

export type CatalogPayload = {
  veyra: string;
  models: string[];
  entries: CatalogEntry[];
  groups: Record<string, number>;
  count: number;
};

export type Dest = "dashboard" | "catalog" | "instruments" | "compare" | "notebook";

export type HealthPayload = {
  ok: boolean;
  veyra: string;
  laboratory?: string;
  models?: number;
  workbench?: boolean;
  tagline?: string;
};
