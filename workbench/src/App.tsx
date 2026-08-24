import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Calculator,
  Check,
  CircleHelp,
  Copy,
  GitBranch,
  GitCompare,
  LayoutDashboard,
  Library,
  MoreHorizontal,
  PanelLeft,
  Pin,
  Play,
  RotateCcw,
  ScrollText,
  Search,
  SquarePen,
  Trash2,
} from "lucide-react";
import { loadCatalog, loadHealth, loadSession, organizeRun, reproduceRun, runModel, runSuite, runSweep } from "./api";
import {
  AccountMenu,
  CHIP,
  FIELD,
  HelpDialog,
  ICON,
  INK,
  ModelPicker,
  PLAY,
  ROW,
  SearchPalette,
  featuredModels,
  groupByRecency,
  useDismiss,
} from "./chrome";
import { Mark } from "./Mark";
import { Plot } from "./Plot";
import type { CatalogEntry, CatalogPayload, Dest, Experiment, HealthPayload, SessionPayload } from "./types";
import { CatalogPanel, ComparePanel, InstrumentsPanel, NotebookPanel } from "./views";

const DESTS: Dest[] = ["dashboard", "catalog", "instruments", "compare", "notebook"];

export default function App() {
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [catalog, setCatalog] = useState<CatalogPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [dest, setDest] = useState<Dest>("dashboard");
  const [query, setQuery] = useState("");
  const [dark, setDark] = useState(false);
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);
  const [help, setHelp] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [catalogId, setCatalogId] = useState("");
  const [params, setParams] = useState<Record<string, number>>({});
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [diff, setDiff] = useState<Experiment | null>(null);
  const [instrument, setInstrument] = useState<Experiment | null>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");
  const [forkedFrom, setForkedFrom] = useState<{ title: string; run_id: string } | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [sweepParam, setSweepParam] = useState("");
  const [sweepStart, setSweepStart] = useState(0);
  const [sweepStop, setSweepStop] = useState(1);
  const [sweepSteps, setSweepSteps] = useState(9);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const stored = localStorage.getItem("veyra-theme");
    const next = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const model = params.get("model") || "";
    const destParam = params.get("dest");
    if (model) setCatalogId(model);
    if (destParam && DESTS.includes(destParam as Dest)) setDest(destParam as Dest);
  }, []);

  useEffect(() => {
    loadSession()
      .then(setSession)
      .catch((err: Error) => setError(err.message));
    loadCatalog()
      .then(setCatalog)
      .catch((err: Error) => setActionError(err.message));
  }, []);

  useEffect(() => {
    let alive = true;
    const ping = () => {
      loadHealth()
        .then((payload) => {
          if (alive) setHealth(payload);
        })
        .catch(() => {
          if (alive) setHealth(null);
        });
    };
    ping();
    const timer = window.setInterval(ping, 8000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!catalog?.entries.length) return;
    const match = catalog.entries.find((item) => item.id === catalogId);
    if (match) {
      setParams((current) => (Object.keys(current).length ? current : defaultsFor(match)));
      return;
    }
    const fromSession = session?.experiments[0];
    const fallback = catalog.entries.find((item) => item.id === fromSession?.model) ?? catalog.entries[0];
    setCatalogId(fallback.id);
    setParams(defaultsFor(fallback));
  }, [catalog, session, catalogId]);

  useEffect(() => {
    if (!catalogId) return;
    const params = new URLSearchParams();
    params.set("model", catalogId);
    if (dest !== "dashboard") params.set("dest", dest);
    const next = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", next);
  }, [catalogId, dest]);

  const filtered = useMemo(() => {
    if (!session) return [];
    const q = query.toLowerCase();
    const rows = session.experiments
      .map((item, i) => ({ item, i }))
      .filter(({ item }) => !q || `${item.alias ?? ""} ${item.title} ${item.kind} ${item.model ?? ""}`.toLowerCase().includes(q));
    return [...rows].sort((a, b) => Number(Boolean(b.item.pinned)) - Number(Boolean(a.item.pinned)));
  }, [session, query]);

  const pinnedRows = filtered.filter((row) => row.item.pinned);
  const recentRows = filtered.filter((row) => !row.item.pinned);

  const groups = useMemo(() => {
    const map = new Map<string, CatalogEntry[]>();
    for (const item of catalog?.entries ?? []) {
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return [...map.entries()];
  }, [catalog]);

  const entry = catalog?.entries.find((item) => item.id === catalogId);
  const starters = featuredModels(catalog?.entries ?? []);
  const timedRows = groupByRecency(recentRows);

  useEffect(() => {
    const param = entry?.params[0];
    if (!param) return;
    setSweepParam(param.name);
    const lo = param.min ?? (param.default === 0 ? 0 : param.default * 0.5);
    const hi = param.max ?? (param.default === 0 ? 1 : param.default * 1.5);
    setSweepStart(lo);
    setSweepStop(hi === lo ? lo + 1 : hi);
    setSweepSteps(9);
  }, [entry]);

  const closeMenus = useCallback(() => {
    setModelOpen(false);
    setAccountOpen(false);
    setMenuId(null);
  }, []);
  useDismiss(modelOpen || accountOpen || Boolean(menuId), closeMenus);

  const toggleTheme = useCallback(() => {
    setDark((current) => {
      const next = !current;
      document.documentElement.classList.toggle("dark", next);
      localStorage.setItem("veyra-theme", next ? "dark" : "light");
      return next;
    });
  }, []);

  const refresh = useCallback(async () => {
    const next = await loadSession(true);
    setSession(next);
    return next;
  }, []);

  const inspectModel = useCallback((item: CatalogEntry) => {
    setCatalogId(item.id);
    setParams(defaultsFor(item));
    setActionError(null);
  }, []);

  const chooseModel = useCallback((item: CatalogEntry) => {
    inspectModel(item);
    setDest("dashboard");
  }, [inspectModel]);

  const selectExperiment = useCallback(
    (i: number, item: Experiment) => {
      setIndex(i);
      setDest("dashboard");
      setInstrument(null);
      setActionError(null);
      if (item.model && catalog) {
        const match = catalog.entries.find((row) => row.id === item.model);
        if (match) {
          setCatalogId(match.id);
          setParams(defaultsFor(match));
        }
      }
    },
    [catalog],
  );

  const applySession = useCallback((next: SessionPayload, keepIndex?: string) => {
    setSession(next);
    window.__VEYRA_SESSION__ = next;
    if (keepIndex) {
      const at = next.experiments.findIndex((item) => item.run_id === keepIndex);
      setIndex(at >= 0 ? at : Math.min(index, Math.max(0, next.experiments.length - 1)));
    }
  }, [index]);

  const organize = useCallback(
    async (action: "pin" | "unpin" | "delete" | "rename", runId: string, title = "") => {
      setActionError(null);
      setMenuId(null);
      try {
        const next = await organizeRun(action, runId, title);
        applySession(next, action === "delete" ? undefined : runId);
        if (action === "delete") {
          setIndex(0);
          if (forkedFrom?.run_id === runId) setForkedFrom(null);
        }
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Organize failed");
      }
    },
    [applySession, forkedFrom],
  );

  const forkRun = useCallback(
    (item: Experiment) => {
      const match = catalog?.entries.find((row) => row.id === item.model) ?? catalog?.entries.find((row) => row.title === item.title);
      if (!match) {
        setActionError("This run has no catalog model to fork.");
        return;
      }
      setCatalogId(match.id);
      setParams(paramsFromInputs(match, item.inputs));
      setDest("dashboard");
      setForkedFrom({ title: item.alias || item.title, run_id: item.run_id });
      setMenuId(null);
      setActionError(null);
    },
    [catalog],
  );

  const play = useCallback(async () => {
    if (!catalogId) return;
    setActionError(null);
    setRunning(true);
    try {
      const result = await runModel(catalogId, params);
      const next = await refresh();
      const at = next.experiments.findIndex((item) => item.run_id === result.run_id);
      setIndex(at >= 0 ? at : 0);
      setDest("dashboard");
      setForkedFrom(null);
      window.requestAnimationFrame(() => document.getElementById("lab-output")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }, [catalogId, params, refresh]);

  const playSweep = useCallback(async () => {
    if (!catalogId || !sweepParam) return;
    setActionError(null);
    setRunning(true);
    try {
      const result = await runSweep(catalogId, sweepParam, sweepStart, sweepStop, sweepSteps, params);
      const next = await refresh();
      const at = next.experiments.findIndex((item) => item.run_id === result.run_id);
      setIndex(at >= 0 ? at : 0);
      setDest("dashboard");
      setForkedFrom(null);
      window.requestAnimationFrame(() => document.getElementById("lab-output")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Sweep failed");
    } finally {
      setRunning(false);
    }
  }, [catalogId, params, refresh, sweepParam, sweepStart, sweepStop, sweepSteps]);

  const replay = useCallback(
    async (runId: string) => {
      setActionError(null);
      setRunning(true);
      try {
        const result = await reproduceRun(runId);
        const next = await refresh();
        const at = next.experiments.findIndex((item) => item.run_id === result.run_id);
        setIndex(at >= 0 ? at : 0);
        setDest("dashboard");
        window.requestAnimationFrame(() => document.getElementById("lab-output")?.scrollIntoView({ behavior: "smooth", block: "start" }));
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Reproduce failed");
      } finally {
        setRunning(false);
      }
    },
    [refresh],
  );

  const newRun = useCallback(() => {
    setDest("dashboard");
    setForkedFrom(null);
    setInstrument(null);
    setActionError(null);
    setSearchOpen(false);
    closeMenus();
    if (entry) setParams(defaultsFor(entry));
    mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [closeMenus, entry]);

  const playSuite = useCallback(async () => {
    setActionError(null);
    setRunning(true);
    try {
      await runSuite();
      await refresh();
      setIndex(0);
      setDest("notebook");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Suite failed");
    } finally {
      setRunning(false);
    }
  }, [refresh]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = (event.target as HTMLElement).matches("input, textarea, select");
      if (event.key === "Escape") {
        setHelp(false);
        setSearchOpen(false);
        closeMenus();
        return;
      }
      if ((event.key === "?" || (event.shiftKey && event.key === "/")) && !typing) {
        setHelp((open) => !open);
        return;
      }
      if (typing) return;
      if (event.key === "/") {
        event.preventDefault();
        setSearchOpen(true);
        setQuery("");
      }
      if (event.key === "n") newRun();
      if (event.key === "t") toggleTheme();
      if (event.key === "r") void play();
      if (event.key >= "1" && event.key <= "5") setDest(DESTS[Number(event.key) - 1]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeMenus, newRun, play, toggleTheme]);

  function exportSession() {
    if (!session) return;
    const blob = new Blob([JSON.stringify(session, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "veyra-session.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyId(runId: string) {
    await navigator.clipboard.writeText(runId);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center px-8 bg-canvas text-ink">
        <div className="max-w-md">
          <Mark className="w-8 h-8 text-ink" />
          <h1 className="mt-6 text-[28px] font-medium tracking-[-0.02em]">Laboratory unavailable</h1>
          <p className="mt-3 text-slate">{error}. Start the engine with veyra serve.</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="h-full flex bg-canvas dark:bg-stage">
        <div className="w-[260px] bg-rail dark:bg-rail-dark border-r border-hairline dark:border-transparent p-3 space-y-2">
          <div className="h-10 bg-fill dark:bg-composer rounded-lg" />
          <div className="h-10 bg-fill dark:bg-composer rounded-lg" />
          <div className="h-9 w-5/6 bg-fill dark:bg-composer rounded-lg" />
        </div>
        <div className="flex-1 p-10 space-y-4">
          <div className="h-8 w-48 bg-fill dark:bg-composer rounded-lg" />
          <div className="h-4 w-80 bg-fill dark:bg-composer rounded-lg" />
        </div>
      </div>
    );
  }

  const current = session.experiments[index];

  return (
    <div className="h-full flex bg-canvas text-ink dark:bg-stage dark:text-[#ececec]">
      <aside
        className={`h-full flex flex-col bg-rail dark:bg-rail-dark border-r border-hairline dark:border-transparent shrink-0 ${
          collapsed ? "w-[52px]" : "w-[260px]"
        }`}
      >
        <div className={`shrink-0 ${collapsed ? "py-2 flex flex-col items-center gap-1" : "px-2 pt-3 pb-1"}`}>
          <div className={`flex items-center ${collapsed ? "flex-col gap-1" : "gap-1"}`}>
            <button type="button" className={ICON} aria-label="Toggle sidebar" onClick={() => setCollapsed((open) => !open)}>
              <PanelLeft size={18} strokeWidth={1.75} />
            </button>
            {!collapsed ? (
              <button type="button" onClick={newRun} className="flex items-center gap-2.5 px-1.5 min-w-0 h-9 rounded-lg hover:bg-black/[0.05] dark:hover:bg-white/[0.08]">
                <Mark className="w-7 h-7 text-ink dark:text-[#ececec]" />
                <span className="text-[16px] font-medium tracking-[-0.02em] truncate">Veyra</span>
              </button>
            ) : (
              <button type="button" onClick={newRun} aria-label="Veyra">
                <Mark className="w-7 h-7 text-ink dark:text-[#ececec]" />
              </button>
            )}
          </div>
          <SideLink
            collapsed={collapsed}
            active={false}
            icon={<SquarePen size={16} strokeWidth={1.75} />}
            label="New run"
            onClick={newRun}
          />
          <SideLink
            collapsed={collapsed}
            active={searchOpen}
            icon={<Search size={16} strokeWidth={1.75} />}
            label="Search"
            onClick={() => {
              setSearchOpen(true);
              setQuery("");
            }}
          />
          <SideLink
            collapsed={collapsed}
            active={dest === "dashboard"}
            icon={<LayoutDashboard size={16} strokeWidth={1.75} />}
            label="Dashboard"
            onClick={() => {
              setDest("dashboard");
              setActionError(null);
            }}
          />
          <SideLink
            collapsed={collapsed}
            active={dest === "catalog"}
            icon={<Library size={16} strokeWidth={1.75} />}
            label="Catalog"
            onClick={() => setDest("catalog")}
          />
        </div>

        <nav className="flex-1 overflow-y-auto px-2" onClick={() => setMenuId(null)}>
          {!collapsed && pinnedRows.length > 0 ? (
            <RunGroup
              label="Pinned"
              rows={pinnedRows}
              index={index}
              dest={dest}
              menuId={menuId}
              renameId={renameId}
              renameText={renameText}
              onSelect={selectExperiment}
              onMenu={setMenuId}
              onRename={(id, text) => {
                setRenameId(id);
                setRenameText(text);
                setMenuId(null);
              }}
              onRenameText={setRenameText}
              onRenameCommit={(id) => {
                if (renameText.trim()) void organize("rename", id, renameText.trim());
                setRenameId(null);
              }}
              onPin={(item) => void organize(item.pinned ? "unpin" : "pin", item.run_id)}
              onFork={forkRun}
              onDelete={(item) => void organize("delete", item.run_id)}
            />
          ) : null}
          {!collapsed
            ? timedRows.map(([label, rows]) => (
                <RunGroup
                  key={label}
                  label={label}
                  rows={rows}
                  index={index}
                  dest={dest}
                  menuId={menuId}
                  renameId={renameId}
                  renameText={renameText}
                  onSelect={selectExperiment}
                  onMenu={setMenuId}
                  onRename={(id, text) => {
                    setRenameId(id);
                    setRenameText(text);
                    setMenuId(null);
                  }}
                  onRenameText={setRenameText}
                  onRenameCommit={(id) => {
                    if (renameText.trim()) void organize("rename", id, renameText.trim());
                    setRenameId(null);
                  }}
                  onPin={(item) => void organize(item.pinned ? "unpin" : "pin", item.run_id)}
                  onFork={forkRun}
                  onDelete={(item) => void organize("delete", item.run_id)}
                />
              ))
            : null}
        </nav>

        <div className={`shrink-0 px-2 pb-3 ${collapsed ? "flex flex-col items-center gap-1" : ""}`}>
          <SideLink
            collapsed={collapsed}
            active={dest === "instruments"}
            icon={<Calculator size={16} strokeWidth={1.75} />}
            label="Instruments"
            onClick={() => setDest("instruments")}
          />
          <SideLink
            collapsed={collapsed}
            active={dest === "compare"}
            icon={<GitCompare size={16} strokeWidth={1.75} />}
            label="Compare"
            onClick={() => setDest("compare")}
          />
          <SideLink
            collapsed={collapsed}
            active={dest === "notebook"}
            icon={<ScrollText size={16} strokeWidth={1.75} />}
            label="Notebook"
            onClick={() => setDest("notebook")}
          />
          <div className={collapsed ? "" : "mt-2 pt-2 border-t border-hairline dark:border-hairline-dark"}>
            {collapsed ? (
              <button type="button" onClick={() => setAccountOpen((open) => !open)} className={ICON} aria-label="Laboratory">
                <span className="h-7 w-7 rounded-full bg-ink text-canvas dark:bg-canvas dark:text-ink inline-flex items-center justify-center text-[11px] font-medium">
                  V
                </span>
              </button>
            ) : (
              <AccountMenu
                version={session.veyra}
                dark={dark}
                open={accountOpen}
                onToggle={() => setAccountOpen((open) => !open)}
                onTheme={toggleTheme}
                onExport={exportSession}
                onHelp={() => {
                  setAccountOpen(false);
                  setHelp(true);
                }}
              />
            )}
          </div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 h-full flex flex-col">
        <header
          className={`h-14 shrink-0 flex items-center gap-2 px-3 sm:px-4 ${
            scrolled ? "border-b border-hairline dark:border-hairline-dark" : "border-b border-transparent"
          }`}
        >
          <ModelPicker
            entry={entry}
            groups={groups}
            open={modelOpen}
            onToggle={() => setModelOpen((open) => !open)}
            onChoose={(item) => {
              chooseModel(item);
              setModelOpen(false);
            }}
          />
          <div className="flex-1" />
          <span className={`hidden sm:inline-flex items-center gap-2 mr-1 text-[13px] tabular ${running ? "text-slate" : "text-teal"}`}>
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            {running ? "Running" : health ? `v${health.veyra}` : "Ready"}
          </span>
          <button type="button" onClick={() => setHelp(true)} className={ICON} aria-label="Help">
            <CircleHelp size={18} strokeWidth={1.75} />
          </button>
          <button
            type="button"
            onClick={() => void play()}
            className="h-9 w-9 inline-flex items-center justify-center rounded-full bg-teal text-white hover:brightness-95 disabled:opacity-50"
            disabled={running || !entry}
            aria-label="Play"
          >
            <Play size={16} strokeWidth={1.75} fill="currentColor" />
          </button>
        </header>

        <main
          ref={mainRef}
          className="flex-1 overflow-y-auto"
          onScroll={(event) => setScrolled(event.currentTarget.scrollTop > 8)}
        >
          <div className="max-w-[48rem] mx-auto px-5 sm:px-6 py-10">
            {actionError ? <p className="mb-6 text-[14px] text-slate">{actionError}</p> : null}

            {dest === "dashboard" ? (
              <section>
                <h2 className="text-[32px] font-medium tracking-[-0.02em] leading-tight">Don't guess the science.</h2>
                <p className="mt-3 text-[16px] text-slate max-w-[36em]">
                  {entry?.summary ?? "Load a model, set the conditions, and let the kernel write the result."}
                </p>
                {forkedFrom ? (
                  <p className="mt-3 text-[13px] text-slate">
                    Forked from {forkedFrom.title}. Edit the conditions, then Play.
                  </p>
                ) : null}
                {starters.length > 0 ? (
                  <div className="mt-6 flex flex-wrap gap-2">
                    {starters.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`${CHIP} ${item.id === catalogId ? "text-teal border-teal/30" : ""}`}
                        onClick={() => chooseModel(item)}
                      >
                        {item.title}
                      </button>
                    ))}
                  </div>
                ) : null}

                {entry ? (
                  <>
                    <p className="mt-12 text-[13px] font-medium text-slate">Conditions</p>
                    <ParamForm entry={entry} params={params} setParams={setParams} />
                    <div className="mt-8 flex flex-wrap gap-3">
                      <button type="button" onClick={() => void play()} className={PLAY} disabled={running}>
                        <Play size={16} strokeWidth={1.75} fill="currentColor" />
                        {running ? "Running" : "Play"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setParams(defaultsFor(entry))}
                        className="inline-flex items-center gap-2 h-10 px-4 rounded-xl text-[14px] font-medium text-slate hover:text-ink dark:hover:text-[#ececec]"
                      >
                        <RotateCcw size={16} strokeWidth={1.75} />
                        Reset
                      </button>
                      <button type="button" onClick={() => void playSuite()} className={INK} disabled={running}>
                        Run suite
                      </button>
                    </div>
                    <p className="mt-12 text-[13px] font-medium text-slate">Sweep</p>
                    <p className="mt-2 text-[15px] text-slate">Vary one condition. The kernel reports the first numeric metric at each node.</p>
                    <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <select className={FIELD} value={sweepParam} onChange={(e) => setSweepParam(e.target.value)} aria-label="Sweep parameter">
                        {entry.params.map((param) => (
                          <option key={param.name} value={param.name}>
                            {param.label}
                          </option>
                        ))}
                      </select>
                      <input className={FIELD} value={sweepStart} onChange={(e) => setSweepStart(Number(e.target.value))} aria-label="Sweep start" />
                      <input className={FIELD} value={sweepStop} onChange={(e) => setSweepStop(Number(e.target.value))} aria-label="Sweep stop" />
                      <input className={FIELD} value={sweepSteps} onChange={(e) => setSweepSteps(Number(e.target.value))} aria-label="Sweep steps" />
                    </div>
                    <button type="button" className={`${INK} mt-5`} disabled={running} onClick={() => void playSweep()}>
                      Sweep
                    </button>
                  </>
                ) : null}

                <div id="lab-output" className="mt-14 pt-10 border-t border-hairline dark:border-hairline-dark">
                  <p className="text-[13px] font-medium text-slate">Output</p>
                  {running ? (
                    <div className="mt-6 space-y-3">
                      <div className="h-4 w-64 bg-fill dark:bg-composer rounded-lg" />
                      <div className="h-48 bg-fill dark:bg-composer rounded-lg" />
                      <div className="h-4 w-full bg-fill dark:bg-composer rounded-lg" />
                    </div>
                  ) : current ? (
                    <Result
                      lab={current}
                      copied={copied}
                      onCopy={() => void copyId(current.run_id)}
                      onReproduce={() => void replay(current.run_id)}
                      onCompare={() => {
                        setCompareA(current.run_id);
                        setDest("compare");
                      }}
                    />
                  ) : (
                    <p className="mt-4 text-[15px] text-slate">Play a model to write output from the kernel.</p>
                  )}
                </div>
              </section>
            ) : null}

            {dest === "catalog" ? (
              <CatalogPanel
                catalog={catalog}
                catalogId={catalogId}
                groups={groups}
                session={session}
                running={running}
                onInspect={inspectModel}
                onOpen={chooseModel}
                onPlay={() => void play()}
              />
            ) : null}

            {dest === "instruments" ? (
              <InstrumentsPanel
                catalog={catalog}
                result={instrument}
                copied={copied}
                onCopy={() => instrument && void copyId(instrument.run_id)}
                onResult={setInstrument}
                onError={setActionError}
                onPersisted={() => void refresh()}
              />
            ) : null}

            {dest === "compare" ? (
              <ComparePanel
                session={session}
                compareA={compareA}
                compareB={compareB}
                diff={diff}
                onA={setCompareA}
                onB={setCompareB}
                onDiff={setDiff}
                onError={setActionError}
              />
            ) : null}

            {dest === "notebook" ? (
              <NotebookPanel
                session={session}
                onOpen={(runId) => {
                  const at = session.experiments.findIndex((item) => item.run_id === runId);
                  if (at >= 0) selectExperiment(at, session.experiments[at]);
                  else setActionError("That run is not in the current session. Fork it from history if you want to replay the conditions.");
                }}
                onCompare={(runId, slot) => {
                  if (slot === "a") setCompareA(runId);
                  else setCompareB(runId);
                  setDest("compare");
                }}
                onPin={(runId, pinned) => void organize(pinned ? "pin" : "unpin", runId)}
                onFork={(runId) => {
                  const item = session.experiments.find((row) => row.run_id === runId);
                  if (item) forkRun(item);
                  else setActionError("That run is not in the current session, so it cannot be forked onto the dashboard.");
                }}
                onReproduce={(runId) => void replay(runId)}
                onDelete={(runId) => void organize("delete", runId)}
              />
            ) : null}

            <p className="mt-20 mb-2 text-center text-[12px] text-placeholder">
              Veyra {health?.veyra ?? session?.veyra ?? ""} reports what the kernel computed.
            </p>
          </div>
        </main>
      </div>

      {searchOpen ? (
        <SearchPalette
          session={session}
          catalog={catalog?.entries ?? []}
          query={query}
          onQuery={setQuery}
          onClose={() => setSearchOpen(false)}
          onOpenRun={(item, i) => selectExperiment(i, item)}
          onOpenModel={chooseModel}
        />
      ) : null}
      {help ? <HelpDialog onClose={() => setHelp(false)} /> : null}
    </div>
  );
}

function paramsFromInputs(entry: CatalogEntry, inputs: Record<string, string>): Record<string, number> {
  const next = defaultsFor(entry);
  const aliases: Record<string, string> = { L: "length", theta0: "theta0", Cd: "drag_coefficient", v0: "velocity" };
  for (const param of entry.params) {
    const raw = inputs[param.name] ?? inputs[aliases[param.name] ?? ""];
    if (raw == null) continue;
    const match = String(raw).match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/i);
    if (!match) continue;
    const parsed = param.type === "integer" ? Number.parseInt(match[0], 10) : Number.parseFloat(match[0]);
    if (Number.isFinite(parsed)) next[param.name] = parsed;
  }
  return next;
}

function RunGroup({
  label,
  rows,
  index,
  dest,
  menuId,
  renameId,
  renameText,
  onSelect,
  onMenu,
  onRename,
  onRenameText,
  onRenameCommit,
  onPin,
  onFork,
  onDelete,
}: {
  label: string;
  rows: { item: Experiment; i: number }[];
  index: number;
  dest: Dest;
  menuId: string | null;
  renameId: string | null;
  renameText: string;
  onSelect: (i: number, item: Experiment) => void;
  onMenu: (id: string | null) => void;
  onRename: (id: string, text: string) => void;
  onRenameText: (text: string) => void;
  onRenameCommit: (id: string) => void;
  onPin: (item: Experiment) => void;
  onFork: (item: Experiment) => void;
  onDelete: (item: Experiment) => void;
}) {
  if (!rows.length) return null;
  return (
    <div className="mb-3">
      <p className="px-2.5 pt-3 pb-1 text-[12px] font-medium text-slate">{label}</p>
      {rows.map(({ item, i }) => (
        <div key={`${item.run_id}-${i}`} className="relative group">
          <div
            className={`${ROW} pr-8 ${
              i === index && dest === "dashboard" ? "bg-black/[0.06] dark:bg-white/[0.09]" : "hover:bg-black/[0.05] dark:hover:bg-white/[0.08]"
            }`}
          >
            {item.pinned ? <Pin size={13} strokeWidth={1.75} className="shrink-0 text-slate" /> : null}
            {renameId === item.run_id ? (
              <input
                autoFocus
                value={renameText}
                onChange={(event) => onRenameText(event.target.value)}
                onBlur={() => onRenameCommit(item.run_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") onRenameCommit(item.run_id);
                  if (event.key === "Escape") onRenameCommit(item.run_id);
                }}
                onClick={(event) => event.stopPropagation()}
                className="w-full bg-transparent text-[14px] outline-none"
              />
            ) : (
              <button type="button" onClick={() => onSelect(i, item)} className="min-w-0 flex-1 text-left truncate">
                {item.alias || item.title}
              </button>
            )}
          </div>
          <button
            type="button"
            aria-label={`Organize ${item.title}`}
            onClick={(event) => {
              event.stopPropagation();
              onMenu(menuId === item.run_id ? null : item.run_id);
            }}
            className="absolute right-1 top-1 h-8 w-8 inline-flex items-center justify-center rounded-lg text-slate opacity-0 group-hover:opacity-100 hover:bg-black/[0.05] dark:hover:bg-white/[0.08]"
          >
            <MoreHorizontal size={16} strokeWidth={1.75} />
          </button>
          {menuId === item.run_id ? (
            <div
              className="absolute right-2 top-10 z-20 w-40 rounded-xl border border-hairline dark:border-hairline-dark bg-canvas dark:bg-rail-dark py-1"
              onClick={(event) => event.stopPropagation()}
            >
              <button type="button" className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`} onClick={() => onPin(item)}>
                <Pin size={14} strokeWidth={1.75} />
                {item.pinned ? "Unpin" : "Pin"}
              </button>
              <button type="button" className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`} onClick={() => onFork(item)}>
                <GitBranch size={14} strokeWidth={1.75} />
                Fork
              </button>
              <button
                type="button"
                className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`}
                onClick={() => onRename(item.run_id, item.alias || item.title)}
              >
                Rename
              </button>
              <button type="button" className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`} onClick={() => onDelete(item)}>
                <Trash2 size={14} strokeWidth={1.75} />
                Delete
              </button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function SideLink({
  collapsed,
  active,
  icon,
  label,
  onClick,
}: {
  collapsed: boolean;
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  if (collapsed) {
    return (
      <button type="button" onClick={onClick} className={`${ICON} ${active ? "text-teal" : ""}`} aria-label={label}>
        {icon}
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${ROW} ${active ? "bg-black/[0.06] dark:bg-white/[0.09]" : "hover:bg-black/[0.05] dark:hover:bg-white/[0.08]"}`}
    >
      {icon}
      {label}
    </button>
  );
}

function Result({
  lab,
  copied,
  onCopy,
  onReproduce,
  onCompare,
}: {
  lab: Experiment;
  copied: boolean;
  onCopy: () => void;
  onReproduce?: () => void;
  onCompare?: () => void;
}) {
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
      <DataTable rows={lab.table} />
      <MetricTable rows={lab.metrics.map((metric) => [metric.name, metric.text])} />
      {lab.checks.length > 0 ? (
        <ul className="mt-8">
          {lab.checks.map((check) => (
            <li key={`${check.name}-${check.detail ?? ""}`} className="flex gap-3 py-2.5 text-[14px] text-slate">
              {check.passed ? <Check size={16} strokeWidth={1.75} className="text-teal mt-0.5 shrink-0" /> : <span className="w-4 text-center">×</span>}
              <span>
                {check.name}
                {check.detail ? <span className="text-placeholder">  {check.detail}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {lab.methods ? <p className="mt-8 text-[15px] text-slate leading-relaxed max-w-[42em]">{lab.methods}</p> : null}
      <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2">
        <button type="button" className="inline-flex items-center gap-2 text-[12px] text-slate hover:text-ink dark:hover:text-[#ececec] tabular" onClick={onCopy}>
          <Copy size={14} strokeWidth={1.75} />
          {copied ? "Copied" : lab.run_id}
        </button>
        {onReproduce ? (
          <button type="button" className="text-[12px] text-slate hover:text-ink dark:hover:text-[#ececec]" onClick={onReproduce}>
            Reproduce
          </button>
        ) : null}
        {onCompare ? (
          <button type="button" className="text-[12px] text-slate hover:text-ink dark:hover:text-[#ececec]" onClick={onCompare}>
            Compare
          </button>
        ) : null}
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

function DataTable({ rows }: { rows?: Experiment["table"] }) {
  if (!rows?.length) return null;
  const first = rows[0] as Record<string, unknown>;
  if ("angle_deg" in first && "range" in first) {
    return (
      <table className="w-full mt-8 border-collapse">
        <thead>
          <tr className="border-b border-hairline dark:border-hairline-dark">
            {["Angle", "Range", "Peak", "Time"].map((label) => (
              <th key={label} className="text-left font-normal text-slate py-3 text-[14px]">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const item = row as { angle_deg: number; range: number; peak: number; time: number };
            return (
              <tr key={item.angle_deg} className="border-b border-hairline dark:border-hairline-dark">
                <td className="py-3 tabular">{item.angle_deg}°</td>
                <td className="py-3 tabular font-medium">{item.range.toFixed(3)} m</td>
                <td className="py-3 tabular">{item.peak.toFixed(3)} m</td>
                <td className="py-3 tabular">{item.time.toFixed(3)} s</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
  const keys = Object.keys(first);
  return (
    <table className="w-full mt-8 border-collapse">
      <thead>
        <tr className="border-b border-hairline dark:border-hairline-dark">
          {keys.map((key) => (
            <th key={key} className="text-left font-normal text-slate py-3 text-[14px]">
              {key}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-hairline dark:border-hairline-dark">
            {keys.map((key) => (
              <td key={key} className="py-3 tabular text-[14px]">
                {String((row as Record<string, unknown>)[key] ?? "")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MetricTable({ rows }: { rows: [string, string][] }) {
  if (!rows.length) return null;
  return (
    <table className="w-full mt-6 border-collapse">
      <tbody>
        {rows.map(([name, value]) => (
          <tr key={name} className="border-b border-hairline dark:border-hairline-dark">
            <th className="text-left font-normal text-slate py-3 w-[42%] text-[15px]">{name}</th>
            <td className="py-3 font-medium tabular text-[15px]">{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function defaultsFor(entry: CatalogEntry): Record<string, number> {
  return Object.fromEntries(entry.params.map((param) => [param.name, param.default]));
}

function ParamForm({
  entry,
  params,
  setParams,
}: {
  entry: CatalogEntry;
  params: Record<string, number>;
  setParams: (next: Record<string, number>) => void;
}) {
  return (
    <div className="mt-8 grid grid-cols-1 sm:grid-cols-2">
      {entry.params.map((param) => (
        <ParamRow key={param.name} entry={entry} param={param} params={params} setParams={setParams} />
      ))}
    </div>
  );
}

function ParamRow({
  entry,
  param,
  params,
  setParams,
}: {
  entry: CatalogEntry;
  param: CatalogEntry["params"][number];
  params: Record<string, number>;
  setParams: (next: Record<string, number>) => void;
}) {
  const numeric = params[param.name] ?? param.default;
  const [text, setText] = useState(String(numeric));
  useEffect(() => {
    setText(String(params[param.name] ?? param.default));
  }, [params, param.name, param.default]);
  return (
    <label className="flex items-center justify-between gap-6 py-3.5 border-b border-hairline dark:border-hairline-dark">
      <span className="text-[15px] text-slate">
        {param.label}
        {param.unit ? <span className="text-placeholder"> · {param.unit}</span> : null}
      </span>
      <input
        type="text"
        inputMode="decimal"
        className="h-10 w-36 px-3 rounded-xl border border-hairline dark:border-hairline-dark bg-transparent text-[14px] tabular text-right outline-none"
        value={text}
        aria-label={`${entry.title} ${param.label}`}
        onChange={(event) => {
          const next = event.target.value;
          setText(next);
          const parsed = param.type === "integer" ? Number.parseInt(next, 10) : Number.parseFloat(next);
          if (Number.isFinite(parsed)) setParams({ ...params, [param.name]: parsed });
        }}
        onBlur={() => {
          if (!Number.isFinite(Number(text))) setText(String(param.default));
        }}
      />
    </label>
  );
}
