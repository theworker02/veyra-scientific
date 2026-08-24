import { useEffect, useMemo, useState } from "react";
import { Play } from "lucide-react";
import { compareRuns, loadDataFiles, loadProtocol, runConvert, runFit, runFourier, runGeometry, runLens, runMath, runMeasure, runSensitivity, runVerify, runUncertainty } from "./api";
import { CHIP, INK, PLAY } from "./chrome";
import { Plot } from "./Plot";
import type { CatalogEntry, CatalogPayload, Experiment, HistoryRow, SessionPayload } from "./types";

const FIELD =
  "h-11 w-full px-3.5 rounded-xl border border-hairline dark:border-hairline-dark bg-transparent text-[15px] outline-none placeholder:text-placeholder";
const MATH_ACTIONS = ["auto", "solve", "simplify", "differentiate", "integrate", "evaluate"] as const;
const FIT_MODELS = ["linear", "quadratic", "exponential"] as const;
const GEO_KINDS = [
  { id: "area_circle", label: "Circle area" },
  { id: "volume_sphere", label: "Sphere volume" },
  { id: "volume_box", label: "Cube volume" },
  { id: "triangle", label: "Right triangle" },
] as const;

export function CatalogPanel({
  catalog,
  catalogId,
  groups,
  session,
  running,
  onInspect,
  onOpen,
  onPlay,
}: {
  catalog: { count: number; entries: CatalogEntry[] } | null;
  catalogId: string;
  groups: [string, CatalogEntry[]][];
  session: SessionPayload;
  running: boolean;
  onInspect: (item: CatalogEntry) => void;
  onOpen: (item: CatalogEntry) => void;
  onPlay: () => void;
}) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("All");
  const entry = catalog?.entries.find((item) => item.id === catalogId);
  const last = session.experiments.find((item) => item.model === catalogId);
  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return groups
      .filter(([name]) => group === "All" || name === group)
      .map(([name, items]) => [
        name,
        items.filter(
          (item) =>
            !q ||
            `${item.title} ${item.summary} ${item.id} ${(item.aliases ?? []).join(" ")}`.toLowerCase().includes(q),
        ),
      ])
      .filter(([, items]) => (items as CatalogEntry[]).length) as [string, CatalogEntry[]][];
  }, [groups, group, query]);
  const shown = filtered.reduce((sum, [, items]) => sum + items.length, 0);

  return (
    <section>
      <h2 className="text-[32px] font-medium tracking-[-0.02em] leading-tight">Catalog</h2>
      <p className="mt-3 text-[16px] text-slate">
        {catalog ? `${catalog.count} models in the kernel. ${shown} shown.` : "Loading catalog."}
      </p>
      <input className={`${FIELD} mt-8`} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search models" />
      <div className="mt-4 flex flex-wrap gap-2">
        {["All", ...groups.map(([name]) => name)].map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setGroup(name)}
            className={`${CHIP} ${group === name ? "text-teal border-teal/30" : ""}`}
          >
            {name}
            {name !== "All" ? <span className="text-placeholder">  {groups.find(([g]) => g === name)?.[1].length}</span> : null}
          </button>
        ))}
      </div>
      <div className="mt-10 space-y-8">
        {filtered.map(([name, items]) => (
          <div key={name}>
            <p className="text-[13px] font-medium text-slate">{name}</p>
            <ul className="mt-3">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onInspect(item)}
                    className={`w-full text-left py-3.5 border-b border-hairline dark:border-hairline-dark ${
                      item.id === catalogId ? "text-teal" : ""
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-4">
                      <span className="text-[15px] font-medium">{item.title}</span>
                      <span className="text-[12px] text-placeholder tabular">{item.params.length} inputs</span>
                    </div>
                    <div className="text-[13px] text-slate mt-0.5">{item.summary}</div>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {entry ? (
        <div className="mt-14 pt-10 border-t border-hairline dark:border-hairline-dark">
          <p className="text-[13px] font-medium text-slate">Selected</p>
          <h3 className="mt-2 text-[22px] font-medium tracking-[-0.02em]">{entry.title}</h3>
          <p className="mt-3 text-[15px] text-slate max-w-[40em]">{entry.summary}</p>
          <p className="mt-4 text-[13px] text-slate">
            Conditions: {entry.params.map((param) => `${param.label}${param.unit ? ` (${param.unit})` : ""}`).join(" · ")}
          </p>
          {entry.aliases?.length ? <p className="mt-2 text-[13px] text-placeholder">Also: {entry.aliases.join(", ")}</p> : null}
          {last ? (
            <p className="mt-3 text-[13px] text-slate">
              Last run in this session · {last.integrityLabel} · {last.run_id}
            </p>
          ) : (
            <p className="mt-3 text-[13px] text-slate">No run of this model in the current session.</p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" className={PLAY} disabled={running} onClick={() => void onPlay()}>
              <Play size={16} strokeWidth={1.75} fill="currentColor" />
              Play
            </button>
            <button type="button" className={INK} onClick={() => onOpen(entry)}>
              Open on dashboard
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function InstrumentsPanel({
  catalog,
  onResult,
  onError,
  result,
  copied,
  onCopy,
  onPersisted,
}: {
  catalog: CatalogPayload | null;
  onResult: (item: Experiment) => void;
  onError: (message: string | null) => void;
  result: Experiment | null;
  copied: boolean;
  onCopy: () => void;
  onPersisted?: () => void;
}) {
  const [mathExpr, setMathExpr] = useState("x^3 - 6*x^2 + 11*x - 6 = 0");
  const [mathAction, setMathAction] = useState("auto");
  const [mathVar, setMathVar] = useState("x");
  const [lensSrc, setLensSrc] = useState("F = G*(m1+m2)/r**2");
  const [convertValue, setConvertValue] = useState("38 m/s");
  const [convertTo, setConvertTo] = useState("km/h");
  const [convertFrom, setConvertFrom] = useState("");
  const [uncExpr, setUncExpr] = useState("0.5 * m * v**2");
  const [uncVars, setUncVars] = useState("m=1±0.02, v=38±0.3");
  const [sensExpr, setSensExpr] = useState("0.5 * m * v**2");
  const [sensVars, setSensVars] = useState("m=1, v=38");
  const [verifySrc, setVerifySrc] = useState("G = 6.67430e-11\nm1 = 5.972e24\nm2 = 7.348e22\nr = 3.844e8\nF = G * ((m1 + m2) / r**2)");
  const [fitX, setFitX] = useState("0, 1, 2, 3, 4");
  const [fitY, setFitY] = useState("0.1, 2.0, 3.9, 6.2, 8.1");
  const [fitModel, setFitModel] = useState("linear");
  const [geoKind, setGeoKind] = useState("area_circle");
  const [geoRadius, setGeoRadius] = useState("2");
  const [fftValues, setFftValues] = useState("0, 1, 0, -1, 0, 1, 0, -1");
  const [fftRate, setFftRate] = useState("8");
  const [csvName, setCsvName] = useState("");
  const [csvText, setCsvText] = useState("x,y\n0,0.10\n1,2.05\n2,3.90\n3,6.10\n4,8.00\n");
  const [measX, setMeasX] = useState("x");
  const [measY, setMeasY] = useState("y");
  const [measXUnit, setMeasXUnit] = useState("s");
  const [measYUnit, setMeasYUnit] = useState("m");
  const [measFit, setMeasFit] = useState("linear");
  const [measOverlay, setMeasOverlay] = useState("");
  const [csvPath, setCsvPath] = useState("");
  const [labFiles, setLabFiles] = useState<{ name: string; relative: string; path: string }[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void loadDataFiles()
      .then(setLabFiles)
      .catch(() => setLabFiles([]));
  }, []);

  async function run(task: () => Promise<Experiment>) {
    onError(null);
    setBusy(true);
    try {
      onResult(await task());
      onPersisted?.();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Instrument failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2 className="text-[32px] font-medium tracking-[-0.02em] leading-tight">Instruments</h2>
      <p className="mt-3 text-[16px] text-slate">The same kernel as the CLI: algebra, Lens, units, measured data, uncertainty, and Fourier.</p>
      <nav className="mt-6 flex flex-wrap gap-2">
        {["Mathematics", "Lens", "Convert", "Measurement", "Uncertainty", "Sensitivity", "Verify", "Geometry", "Fourier"].map((label) => (
          <a key={label} href={`#instrument-${label.toLowerCase()}`} className={CHIP}>
            {label}
          </a>
        ))}
      </nav>

      <div id="instrument-mathematics" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Mathematics</p>
        <p className="mt-2 text-[15px] text-slate">Solve, simplify, differentiate, integrate, or evaluate.</p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
          {[
            ["Cubic", "x^3 - 6*x^2 + 11*x - 6 = 0"],
            ["Derivative", "diff(sin(x), x)"],
            ["Integral", "integrate(x**2, x)"],
          ].map(([label, value]) => (
            <button key={label} type="button" className="text-slate hover:text-ink dark:hover:text-[#ececec]" onClick={() => setMathExpr(value)}>
              {label}
            </button>
          ))}
        </div>
        <textarea className={`${FIELD} mt-4 h-24 py-3`} value={mathExpr} onChange={(e) => setMathExpr(e.target.value)} />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {MATH_ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              onClick={() => setMathAction(action)}
              className={`h-8 px-3 rounded-lg text-[13px] font-medium ${mathAction === action ? "text-teal" : "text-slate hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"}`}
            >
              {action}
            </button>
          ))}
          <input className={`${FIELD} !h-8 !w-24`} value={mathVar} onChange={(e) => setMathVar(e.target.value)} aria-label="Variable" />
        </div>
        <button type="button" className={`${INK} mt-5`} disabled={busy} onClick={() => void run(() => runMath(mathExpr, mathAction, mathVar))}>
          Compute
        </button>
      </div>

      <div id="instrument-lens" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Lens</p>
        <p className="mt-2 text-[15px] text-slate">Inspect an equation or a fragment of source for model identity and consistency.</p>
        <textarea className={`${FIELD} mt-4 h-24 py-3`} value={lensSrc} onChange={(e) => setLensSrc(e.target.value)} />
        <button
          type="button"
          className={`${INK} mt-5`}
          disabled={busy}
          onClick={() =>
            void run(() =>
              lensSrc.includes("=") || lensSrc.includes("\n") ? runLens({ source: lensSrc }) : runLens({ expression: lensSrc }),
            )
          }
        >
          Inspect
        </button>
      </div>

      <div id="instrument-convert" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Convert</p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
          {[
            ["38 m/s → km/h", "38 m/s", "km/h", ""],
            ["373.15 K → °C", "373.15 K", "degC", ""],
            ["1 atm → Pa", "1 atm", "Pa", ""],
          ].map(([label, value, to, from]) => (
            <button
              key={label}
              type="button"
              className="text-slate hover:text-ink dark:hover:text-[#ececec]"
              onClick={() => {
                setConvertValue(value);
                setConvertTo(to);
                setConvertFrom(from);
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <input className={FIELD} value={convertValue} onChange={(e) => setConvertValue(e.target.value)} placeholder="quantity" />
          <input className={FIELD} value={convertFrom} onChange={(e) => setConvertFrom(e.target.value)} placeholder="from (optional)" />
          <input className={FIELD} value={convertTo} onChange={(e) => setConvertTo(e.target.value)} placeholder="to unit" />
        </div>
        <button type="button" className={`${INK} mt-5`} disabled={busy} onClick={() => void run(() => runConvert(convertValue, convertTo, convertFrom))}>
          Convert
        </button>
      </div>

      <div id="instrument-uncertainty" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Uncertainty</p>
        <p className="mt-2 text-[15px] text-slate">Monte Carlo propagation. Variables as name=value±sigma.</p>
        <input className={`${FIELD} mt-4`} value={uncExpr} onChange={(e) => setUncExpr(e.target.value)} />
        <input className={`${FIELD} mt-3`} value={uncVars} onChange={(e) => setUncVars(e.target.value)} />
        <button
          type="button"
          className={`${INK} mt-5`}
          disabled={busy}
          onClick={() => void run(() => runUncertainty(uncExpr, parseUncertain(uncVars)))}
        >
          Propagate
        </button>
      </div>

      <div id="instrument-sensitivity" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Sensitivity</p>
        <p className="mt-2 text-[15px] text-slate">Local derivatives and elasticities. Variables as name=value.</p>
        <input className={`${FIELD} mt-4`} value={sensExpr} onChange={(e) => setSensExpr(e.target.value)} />
        <input className={`${FIELD} mt-3`} value={sensVars} onChange={(e) => setSensVars(e.target.value)} />
        <button
          type="button"
          className={`${INK} mt-5`}
          disabled={busy}
          onClick={() => void run(() => runSensitivity(sensExpr, parseScalars(sensVars)))}
        >
          Differentiate
        </button>
      </div>

      <div id="instrument-verify" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Verify</p>
        <p className="mt-2 text-[15px] text-slate">Proof over source: Lens, dimensions, and stability where they apply.</p>
        <textarea className={`${FIELD} mt-4 h-32 py-3 font-[inherit]`} value={verifySrc} onChange={(e) => setVerifySrc(e.target.value)} />
        <button type="button" className={`${INK} mt-5`} disabled={busy} onClick={() => void run(() => runVerify(verifySrc))}>
          Verify
        </button>
      </div>

      <div id="instrument-measurement" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Measurement</p>
        <p className="mt-2 text-[15px] text-slate">
          Load a CSV from the laboratory folder, your computer, or paste. Fit a curve, overlay a catalog
          model, or both. Overlay uses the model source series, not the downsampled plot. Residual and units
          come from the kernel.
        </p>
        {labFiles.length > 0 ? (
          <select
            className={`${FIELD} mt-4`}
            value={csvPath}
            onChange={(event) => {
              const relative = event.target.value;
              setCsvPath(relative);
              const match = labFiles.find((item) => item.relative === relative);
              if (match) setCsvName(match.name);
            }}
            aria-label="Laboratory CSV"
          >
            <option value="">Laboratory CSV…</option>
            {labFiles.map((item) => (
              <option key={item.relative} value={item.relative}>
                {item.relative}
              </option>
            ))}
          </select>
        ) : null}
        <input
          className={`${FIELD} mt-3`}
          value={csvPath}
          onChange={(event) => setCsvPath(event.target.value)}
          placeholder="path under the laboratory, e.g. examples/data/cooling.csv"
          aria-label="CSV path"
        />
        <label className="mt-4 inline-flex items-center gap-2 text-[13px] text-slate">
          <input
            type="file"
            accept=".csv,text/csv,text/plain"
            className="text-[13px]"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              setCsvName(file.name);
              void file.text().then(setCsvText);
            }}
          />
          {csvName ? <span className="text-placeholder">{csvName}</span> : <span>Choose a CSV</span>}
        </label>
        <textarea
          className={`${FIELD} mt-4 h-28 py-3 font-[inherit]`}
          value={csvText}
          onChange={(e) => setCsvText(e.target.value)}
          placeholder="t,T"
        />
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <input className={FIELD} value={measX} onChange={(e) => setMeasX(e.target.value)} placeholder="x column" />
          <input className={FIELD} value={measY} onChange={(e) => setMeasY(e.target.value)} placeholder="y column" />
          <input className={FIELD} value={measXUnit} onChange={(e) => setMeasXUnit(e.target.value)} placeholder="x unit" />
          <input className={FIELD} value={measYUnit} onChange={(e) => setMeasYUnit(e.target.value)} placeholder="y unit" />
        </div>
        <div className="mt-3 flex flex-wrap gap-1">
          {["linear", "quadratic", "exponential", "none"].map((model) => (
            <button
              key={model}
              type="button"
              onClick={() => setMeasFit(model)}
              className={`h-8 px-3 rounded-lg text-[13px] font-medium ${measFit === model ? "text-teal" : "text-slate hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"}`}
            >
              {model}
            </button>
          ))}
        </div>
        <select
          className={`${FIELD} mt-3`}
          value={measOverlay}
          onChange={(e) => setMeasOverlay(e.target.value)}
          aria-label="Overlay model"
        >
          <option value="">No overlay</option>
          {(catalog?.entries ?? []).map((entry) => (
            <option key={entry.id} value={entry.id}>
              {entry.title}
            </option>
          ))}
        </select>
        <button
          type="button"
          className={`${INK} mt-5`}
          disabled={busy}
          onClick={() =>
            void run(() =>
              runMeasure({
                csv: csvPath ? "" : csvText,
                path: csvPath || undefined,
                x: measX,
                y: measY,
                x_unit: measXUnit,
                y_unit: measYUnit,
                fit: measFit,
                overlay: measOverlay,
              }),
            )
          }
        >
          Analyze
        </button>
        <p className="mt-8 text-[13px] font-medium text-slate">Or paste columns</p>
        <p className="mt-2 text-[15px] text-slate">Least squares without a file.</p>
        <div className="mt-3 flex flex-wrap gap-1">
          {FIT_MODELS.map((model) => (
            <button
              key={model}
              type="button"
              onClick={() => setFitModel(model)}
              className={`h-8 px-3 rounded-lg text-[13px] font-medium ${fitModel === model ? "text-teal" : "text-slate hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"}`}
            >
              {model}
            </button>
          ))}
        </div>
        <input className={`${FIELD} mt-4`} value={fitX} onChange={(e) => setFitX(e.target.value)} placeholder="x" />
        <input className={`${FIELD} mt-3`} value={fitY} onChange={(e) => setFitY(e.target.value)} placeholder="y" />
        <button
          type="button"
          className={`${INK} mt-5`}
          disabled={busy}
          onClick={() => void run(() => runFit(parseList(fitX), parseList(fitY), fitModel))}
        >
          Fit
        </button>
      </div>

      <div id="instrument-geometry" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Geometry</p>
        <p className="mt-2 text-[15px] text-slate">Closed-form measure. Circle area and sphere volume from a radius.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {GEO_KINDS.map((kind) => (
            <button
              key={kind.id}
              type="button"
              onClick={() => setGeoKind(kind.id)}
              className={`${CHIP} ${geoKind === kind.id ? "text-teal border-teal/30" : ""}`}
            >
              {kind.label}
            </button>
          ))}
        </div>
        <input className={`${FIELD} mt-4`} value={geoRadius} onChange={(e) => setGeoRadius(e.target.value)} placeholder="length" />
        <button
          type="button"
          className={`${INK} mt-5`}
          disabled={busy}
          onClick={() => void run(() => runGeometry(geoKind, Number.parseFloat(geoRadius)))}
        >
          Measure
        </button>
      </div>

      <div id="instrument-fourier" className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
        <p className="text-[13px] font-medium text-slate">Fourier</p>
        <p className="mt-2 text-[15px] text-slate">Discrete FFT. Paste samples and a sample rate.</p>
        <input className={`${FIELD} mt-4`} value={fftValues} onChange={(e) => setFftValues(e.target.value)} placeholder="samples" />
        <input className={`${FIELD} mt-3`} value={fftRate} onChange={(e) => setFftRate(e.target.value)} placeholder="sample rate" />
        <button
          type="button"
          className={`${INK} mt-5`}
          disabled={busy}
          onClick={() => void run(() => runFourier(parseList(fftValues), Number.parseFloat(fftRate) || 1))}
        >
          Transform
        </button>
      </div>

      {result ? (
        <div className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
          <p className="text-[13px] font-medium text-slate">Output</p>
          <InstrumentResult lab={result} copied={copied} onCopy={onCopy} />
        </div>
      ) : null}
    </section>
  );
}

export function ComparePanel({
  session,
  compareA,
  compareB,
  diff,
  onA,
  onB,
  onDiff,
  onError,
}: {
  session: SessionPayload;
  compareA: string;
  compareB: string;
  diff: Experiment | null;
  onA: (id: string) => void;
  onB: (id: string) => void;
  onDiff: (item: Experiment | null) => void;
  onError: (message: string | null) => void;
}) {
  const options = useMemo(() => compareOptions(session), [session]);
  const runA = session.experiments.find((item) => item.run_id === compareA);
  const runB = session.experiments.find((item) => item.run_id === compareB);

  return (
    <section>
      <h2 className="text-[32px] font-medium tracking-[-0.02em] leading-tight">Compare</h2>
      <p className="mt-3 text-[16px] text-slate">Diff two fingerprints. Metrics, checks, and declared conditions sit side by side.</p>
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="block">
          <span className="text-[13px] text-slate">Run A</span>
          <select className={`${FIELD} mt-2`} value={compareA} onChange={(e) => onA(e.target.value)}>
            <option value="">Select</option>
            {options.map((row) => (
              <option key={`a-${row.id}`} value={row.id}>
                {row.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[13px] text-slate">Run B</span>
          <select className={`${FIELD} mt-2`} value={compareB} onChange={(e) => onB(e.target.value)}>
            <option value="">Select</option>
            {options.map((row) => (
              <option key={`b-${row.id}`} value={row.id}>
                {row.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={!compareA || !compareB}
          className={INK}
          onClick={async () => {
            onError(null);
            try {
              onDiff(await compareRuns(compareA, compareB));
            } catch (err) {
              onError(err instanceof Error ? err.message : "Compare failed");
            }
          }}
        >
          Diff
        </button>
        <button
          type="button"
          className="h-10 px-4 rounded-xl text-[14px] font-medium text-slate hover:text-ink dark:hover:text-[#ececec]"
          onClick={() => {
            onA(compareB);
            onB(compareA);
          }}
        >
          Swap
        </button>
        <button
          type="button"
          className="h-10 px-4 rounded-xl text-[14px] font-medium text-slate hover:text-ink dark:hover:text-[#ececec]"
          disabled={session.experiments.length < 2}
          onClick={() => {
            onA(session.experiments[0]?.run_id ?? "");
            onB(session.experiments[1]?.run_id ?? "");
          }}
        >
          Latest two
        </button>
      </div>
      <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-10">
        <RunSummary label="A" run={runA} />
        <RunSummary label="B" run={runB} />
      </div>
      {diff ? (
        <div className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
          <p className="text-[13px] font-medium text-slate">Delta</p>
          <h3 className="mt-2 text-[20px] font-medium tracking-[-0.02em]">{diff.title}</h3>
          <p className="mt-1 text-[14px] text-slate">{diff.integrityLabel}</p>
          <MetricRows rows={diff.metrics.map((metric) => [metric.name, metric.text])} />
          {diff.checks.length > 0 ? (
            <ul className="mt-6">
              {diff.checks.map((check) => (
                <li key={`${check.name}-${check.detail ?? ""}`} className="py-2.5 text-[14px] text-slate border-b border-hairline dark:border-hairline-dark">
                  {check.passed ? "Pass" : "Fail"} · {check.name}
                  {check.detail ? <span className="text-placeholder">  {check.detail}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function NotebookPanel({
  session,
  onOpen,
  onCompare,
  onPin,
  onFork,
  onReproduce,
  onDelete,
}: {
  session: SessionPayload;
  onOpen: (runId: string) => void;
  onCompare: (runId: string, slot: "a" | "b") => void;
  onPin: (runId: string, pinned: boolean) => void;
  onFork: (runId: string) => void;
  onReproduce: (runId: string) => void;
  onDelete: (runId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "pass" | "fail">("all");
  const [protocol, setProtocol] = useState("");
  const [protocolId, setProtocolId] = useState("");
  const rows = useMemo(() => {
    const q = query.toLowerCase();
    return session.history.filter((row) => {
      if (filter === "pass" && !row.ok) return false;
      if (filter === "fail" && row.ok) return false;
      return !q || `${row.title} ${row.kind} ${row.run_id}`.toLowerCase().includes(q);
    });
  }, [session.history, query, filter]);
  const passed = session.history.filter((row) => row.ok).length;

  return (
    <section>
      <h2 className="text-[32px] font-medium tracking-[-0.02em] leading-tight">Notebook</h2>
      <p className="mt-3 text-[16px] text-slate">
        {session.history.length} fingerprinted runs · {passed} passed · {session.history.length - passed} failed
      </p>
      <input className={`${FIELD} mt-8`} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search the notebook" />
      <div className="mt-4 flex flex-wrap gap-1">
        {(["all", "pass", "fail"] as const).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setFilter(id)}
            className={`${CHIP} ${filter === id ? "text-teal border-teal/30" : ""}`}
          >
            {id}
          </button>
        ))}
      </div>
      <table className="w-full mt-8 border-collapse">
        <thead>
          <tr className="border-b border-hairline dark:border-hairline-dark">
            <th className="text-left font-normal text-slate py-3 text-[14px]">Run</th>
            <th className="text-left font-normal text-slate py-3 text-[14px]">Experiment</th>
            <th className="text-left font-normal text-slate py-3 text-[14px]">Kind</th>
            <th className="text-left font-normal text-slate py-3 text-[14px]">Integrity</th>
            <th className="text-left font-normal text-slate py-3 text-[14px]">When</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="py-3 text-slate" colSpan={5}>
                No runs match.
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.run_id} className="border-b border-hairline dark:border-hairline-dark align-top">
                <td className="py-3 tabular text-[13px]">{row.run_id}</td>
                <td className="py-3">
                  <button type="button" className="font-medium hover:text-teal" onClick={() => row.run_id && onOpen(row.run_id)}>
                    {row.title}
                  </button>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-slate">
                    <button type="button" onClick={() => row.run_id && onOpen(row.run_id)}>
                      Open
                    </button>
                    <button type="button" onClick={() => row.run_id && onCompare(row.run_id, "a")}>
                      Compare A
                    </button>
                    <button type="button" onClick={() => row.run_id && onCompare(row.run_id, "b")}>
                      Compare B
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        if (!row.run_id) return;
                        setProtocolId(row.run_id);
                        setProtocol(await loadProtocol(row.run_id));
                      }}
                    >
                      Methods
                    </button>
                    <a
                      className="text-slate hover:text-ink dark:hover:text-[#ececec]"
                      href={row.run_id ? `/api/methods.html?run=${encodeURIComponent(row.run_id)}` : undefined}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Methods page
                    </a>
                    <button type="button" onClick={() => row.run_id && onPin(row.run_id, !session.pinned?.includes(row.run_id))}>
                      {session.pinned?.includes(row.run_id ?? "") ? "Unpin" : "Pin"}
                    </button>
                    <button type="button" onClick={() => row.run_id && onFork(row.run_id)}>
                      Fork
                    </button>
                    <button type="button" onClick={() => row.run_id && onReproduce(row.run_id)}>
                      Reproduce
                    </button>
                    <button type="button" onClick={() => row.run_id && onDelete(row.run_id)}>
                      Delete
                    </button>
                  </div>
                </td>
                <td className="py-3 text-[13px] text-slate">{row.kind}</td>
                <td className="py-3 text-slate">{row.ok ? "Pass" : "Fail"}</td>
                <td className="py-3 text-[13px] text-slate tabular">{formatWhen(row.created_at)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {protocol ? (
        <div className="mt-12 pt-10 border-t border-hairline dark:border-hairline-dark">
          <p className="text-[13px] font-medium text-slate">Methods · {protocolId}</p>
          <p className="mt-4 text-[15px] text-slate max-w-[42em] leading-relaxed">{protocol}</p>
        </div>
      ) : null}
    </section>
  );
}

export function InstrumentResult({ lab, copied, onCopy }: { lab: Experiment; copied: boolean; onCopy: () => void }) {
  return (
    <div className="mt-6">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-[20px] font-medium tracking-[-0.02em]">{lab.title}</h3>
        <span className={`text-[13px] font-medium ${lab.ok ? "text-teal" : "text-slate"}`}>{lab.integrityLabel}</span>
      </div>
      <p className="mt-1 text-[14px] text-slate">
        {lab.kind} · {lab.solver}
      </p>
      {lab.plot ? (
        <div className="mt-6">
          <Plot plot={lab.plot} />
        </div>
      ) : null}
      {lab.hits && lab.hits.length > 0 ? (
        <ul className="mt-6">
          {lab.hits.map((hit, i) => (
            <li key={`${hit.expression ?? hit.lhs ?? i}`} className="py-2.5 text-[14px] text-slate border-b border-hairline dark:border-hairline-dark">
              {hit.ok === false ? "Fail" : "Hit"} · {hit.lhs || hit.expression || hit.model || "expression"}
              {hit.message ? <span className="text-placeholder">  {hit.message}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <MetricRows rows={lab.metrics.map((metric) => [metric.name, metric.text])} />
      {lab.checks.length > 0 ? (
        <ul className="mt-6">
          {lab.checks.map((check) => (
            <li key={`${check.name}-${check.detail ?? ""}`} className="py-2.5 text-[14px] text-slate border-b border-hairline dark:border-hairline-dark">
              {check.passed ? "Pass" : "Fail"} · {check.name}
              {check.detail ? <span className="text-placeholder">  {check.detail}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2">
        <button type="button" className="text-[12px] text-slate hover:text-ink dark:hover:text-[#ececec] tabular" onClick={onCopy}>
          {copied ? "Copied" : lab.run_id}
        </button>
        <a
          className="text-[12px] text-slate hover:text-ink dark:hover:text-[#ececec]"
          href={`/api/methods.html?run=${encodeURIComponent(lab.run_id)}`}
          target="_blank"
          rel="noreferrer"
        >
          Methods page
        </a>
      </div>
    </div>
  );
}

function RunSummary({ label, run }: { label: string; run?: Experiment }) {
  if (!run) {
    return (
      <div>
        <p className="text-[13px] font-medium text-slate">Run {label}</p>
        <p className="mt-3 text-[15px] text-slate">Select a run to preview it here.</p>
      </div>
    );
  }
  return (
    <div>
      <p className="text-[13px] font-medium text-slate">Run {label}</p>
      <h3 className="mt-2 text-[18px] font-medium tracking-[-0.02em]">{run.alias || run.title}</h3>
      <p className="mt-1 text-[13px] text-slate">
        {run.integrityLabel} · {run.kind}
      </p>
      <MetricRows
        rows={[
          ...Object.entries(run.inputs).slice(0, 4).map(([name, value]) => [name, value] as [string, string]),
          ...run.metrics.slice(0, 6).map((metric) => [metric.name, metric.text] as [string, string]),
        ]}
      />
    </div>
  );
}

function MetricRows({ rows }: { rows: [string, string][] }) {
  if (!rows.length) return null;
  return (
    <table className="w-full mt-4 border-collapse">
      <tbody>
        {rows.map(([name, value]) => (
          <tr key={name} className="border-b border-hairline dark:border-hairline-dark">
            <th className="text-left font-normal text-slate py-2.5 w-[46%] text-[14px]">{name}</th>
            <td className="py-2.5 font-medium tabular text-[14px]">{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function compareOptions(session: SessionPayload): { id: string; label: string }[] {
  const seen = new Set<string>();
  const rows: { id: string; label: string }[] = [];
  for (const item of session.experiments) {
    if (!item.run_id || seen.has(item.run_id)) continue;
    seen.add(item.run_id);
    rows.push({ id: item.run_id, label: `${item.alias || item.title} · ${item.run_id}` });
  }
  for (const row of session.history as HistoryRow[]) {
    if (!row.run_id || seen.has(row.run_id)) continue;
    seen.add(row.run_id);
    rows.push({ id: row.run_id, label: `${row.title} · ${row.run_id}` });
  }
  return rows;
}

function parseList(raw: string): number[] {
  const values = raw
    .split(/[\s,;]+/)
    .map((part) => Number.parseFloat(part))
    .filter((value) => Number.isFinite(value));
  if (values.length < 2) throw new Error("Need at least two numeric points");
  return values;
}

function parseScalars(raw: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const part of raw.split(/[,;]+/)) {
    const match = part.trim().match(/^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/i);
    if (match) out[match[1]] = Number.parseFloat(match[2]);
  }
  if (!Object.keys(out).length) throw new Error("Variables must look like m=1, v=38");
  return out;
}

function parseUncertain(raw: string): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {};
  for (const part of raw.split(/[,;]+/)) {
    const match = part.trim().match(/^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*(?:±|\+\/-|\+-)\s*(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/i);
    if (match) out[match[1]] = [Number.parseFloat(match[2]), Number.parseFloat(match[3])];
  }
  if (!Object.keys(out).length) throw new Error("Variables must look like m=1±0.02, v=38±0.3");
  return out;
}

function formatWhen(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
