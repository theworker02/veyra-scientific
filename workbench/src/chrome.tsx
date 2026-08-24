import { useEffect, useRef, type ReactNode } from "react";
import { ChevronDown, Download, Moon, Search, Sun } from "lucide-react";
import type { CatalogEntry, Experiment, SessionPayload } from "./types";

export const ICON =
  "h-9 w-9 inline-flex items-center justify-center rounded-lg text-slate hover:bg-black/[0.05] dark:hover:bg-white/[0.08]";
export const ROW = "w-full flex items-center gap-2 h-10 px-2.5 rounded-lg text-[14px] text-left";
export const PLAY =
  "inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-teal text-white text-[14px] font-medium hover:brightness-95 disabled:opacity-50";
export const INK =
  "inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-ink text-canvas dark:bg-canvas dark:text-ink text-[14px] font-medium disabled:opacity-40";
export const FIELD =
  "h-11 w-full px-3.5 rounded-xl border border-hairline dark:border-hairline-dark bg-transparent text-[15px] outline-none placeholder:text-placeholder";
export const CHIP =
  "inline-flex items-center h-9 px-3.5 rounded-full border border-hairline dark:border-hairline-dark text-[13px] font-medium text-slate hover:text-ink dark:hover:text-[#ececec] hover:bg-black/[0.03] dark:hover:bg-white/[0.05]";

export function Overlay({
  children,
  onClose,
  wide,
}: {
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center px-4 pt-[12vh]" onClick={onClose}>
      <div className="absolute inset-0 bg-ink/40 dark:bg-black/50" />
      <div
        className={`relative w-full ${wide ? "max-w-xl" : "max-w-md"} bg-canvas dark:bg-stage rounded-2xl border border-hairline dark:border-hairline-dark overflow-hidden`}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

export function SearchPalette({
  session,
  catalog,
  query,
  onQuery,
  onClose,
  onOpenRun,
  onOpenModel,
}: {
  session: SessionPayload;
  catalog: CatalogEntry[];
  query: string;
  onQuery: (value: string) => void;
  onClose: () => void;
  onOpenRun: (item: Experiment, index: number) => void;
  onOpenModel: (item: CatalogEntry) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const q = query.toLowerCase();
  const runs = session.experiments.filter(
    (item) => !q || `${item.alias ?? ""} ${item.title} ${item.kind} ${item.run_id}`.toLowerCase().includes(q),
  );
  const models = catalog.filter(
    (item) => !q || `${item.title} ${item.summary} ${item.id} ${(item.aliases ?? []).join(" ")}`.toLowerCase().includes(q),
  );

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <Overlay onClose={onClose} wide>
      <label className="flex items-center gap-3 h-14 px-4 border-b border-hairline dark:border-hairline-dark">
        <Search size={18} strokeWidth={1.75} className="text-placeholder shrink-0" />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search runs and models"
          className="w-full bg-transparent text-[16px] placeholder:text-placeholder outline-none"
        />
      </label>
      <div className="max-h-[min(28rem,56vh)] overflow-y-auto py-2">
        <p className="px-4 pt-2 pb-1 text-[12px] font-medium text-slate">Runs</p>
        {runs.length === 0 ? (
          <p className="px-4 py-2 text-[14px] text-placeholder">No matching runs.</p>
        ) : (
          runs.slice(0, 8).map((item, i) => (
            <button
              key={item.run_id}
              type="button"
              className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`}
              onClick={() => {
                onOpenRun(item, session.experiments.indexOf(item) >= 0 ? session.experiments.indexOf(item) : i);
                onClose();
              }}
            >
              <span className="truncate">{item.alias || item.title}</span>
              <span className="ml-auto text-[12px] text-placeholder tabular">{item.run_id}</span>
            </button>
          ))
        )}
        <p className="px-4 pt-4 pb-1 text-[12px] font-medium text-slate">Models</p>
        {models.length === 0 ? (
          <p className="px-4 py-2 text-[14px] text-placeholder">No matching models.</p>
        ) : (
          models.slice(0, 8).map((item) => (
            <button
              key={item.id}
              type="button"
              className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`}
              onClick={() => {
                onOpenModel(item);
                onClose();
              }}
            >
              <span className="truncate">{item.title}</span>
              <span className="ml-auto text-[12px] text-placeholder">{item.group}</span>
            </button>
          ))
        )}
      </div>
    </Overlay>
  );
}

export function ModelPicker({
  entry,
  groups,
  open,
  onToggle,
  onChoose,
}: {
  entry?: CatalogEntry;
  groups: [string, CatalogEntry[]][];
  open: boolean;
  onToggle: () => void;
  onChoose: (item: CatalogEntry) => void;
}) {
  return (
    <div className="relative" onClick={(event) => event.stopPropagation()}>
      <button
        type="button"
        onClick={onToggle}
        className="inline-flex items-center gap-1.5 h-9 px-2 -ml-2 rounded-lg text-[16px] font-medium tracking-[-0.02em] hover:bg-black/[0.05] dark:hover:bg-white/[0.08]"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate max-w-[14rem] sm:max-w-[22rem]">{entry?.title ?? "Veyra"}</span>
        <ChevronDown size={16} strokeWidth={1.75} className="text-slate shrink-0" />
      </button>
      {open ? (
        <div className="absolute left-0 top-11 z-30 w-[min(20rem,calc(100vw-2rem))] max-h-[min(24rem,60vh)] overflow-y-auto rounded-xl border border-hairline dark:border-hairline-dark bg-canvas dark:bg-rail-dark py-1">
          {groups.map(([name, items]) => (
            <div key={name}>
              <p className="px-3 pt-2.5 pb-1 text-[12px] font-medium text-slate">{name}</p>
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`${ROW} ${item.id === entry?.id ? "text-teal" : "hover:bg-black/[0.05] dark:hover:bg-white/[0.08]"}`}
                  onClick={() => onChoose(item)}
                >
                  {item.title}
                </button>
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function AccountMenu({
  version,
  dark,
  open,
  onToggle,
  onTheme,
  onExport,
  onHelp,
}: {
  version: string;
  dark: boolean;
  open: boolean;
  onToggle: () => void;
  onTheme: () => void;
  onExport: () => void;
  onHelp: () => void;
}) {
  return (
    <div className="relative" onClick={(event) => event.stopPropagation()}>
      <button
        type="button"
        onClick={onToggle}
        className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="h-7 w-7 rounded-full bg-ink text-canvas dark:bg-canvas dark:text-ink inline-flex items-center justify-center text-[11px] font-medium shrink-0">
          V
        </span>
        <span className="min-w-0 flex-1 text-left">
          <span className="block truncate text-[14px] font-medium leading-tight">Laboratory</span>
          <span className="block text-[11px] text-placeholder tabular leading-tight">v{version}</span>
        </span>
      </button>
      {open ? (
        <div className="absolute left-2 right-2 bottom-12 z-30 rounded-xl border border-hairline dark:border-hairline-dark bg-canvas dark:bg-rail-dark py-1">
          <button type="button" className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`} onClick={onTheme}>
            {dark ? <Sun size={16} strokeWidth={1.75} /> : <Moon size={16} strokeWidth={1.75} />}
            {dark ? "Light" : "Dark"}
          </button>
          <button type="button" className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`} onClick={onExport}>
            <Download size={16} strokeWidth={1.75} />
            Export session
          </button>
          <button type="button" className={`${ROW} hover:bg-black/[0.05] dark:hover:bg-white/[0.08]`} onClick={onHelp}>
            Keyboard
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function HelpDialog({ onClose }: { onClose: () => void }) {
  return (
    <Overlay onClose={onClose}>
      <div className="px-6 py-6">
        <p className="text-[12px] font-medium text-slate">Keyboard</p>
        <ul className="mt-4 space-y-2.5 text-[15px] text-graphite dark:text-slate">
          <li className="flex justify-between gap-6">
            <span>Play</span>
            <span className="tabular text-placeholder">R</span>
          </li>
          <li className="flex justify-between gap-6">
            <span>Search</span>
            <span className="tabular text-placeholder">/</span>
          </li>
          <li className="flex justify-between gap-6">
            <span>New run</span>
            <span className="tabular text-placeholder">N</span>
          </li>
          <li className="flex justify-between gap-6">
            <span>Theme</span>
            <span className="tabular text-placeholder">T</span>
          </li>
          <li className="flex justify-between gap-6">
            <span>Dashboard … Notebook</span>
            <span className="tabular text-placeholder">1–5</span>
          </li>
          <li className="flex justify-between gap-6">
            <span>Close</span>
            <span className="tabular text-placeholder">Esc</span>
          </li>
        </ul>
      </div>
    </Overlay>
  );
}

export function recencyLabel(value?: string): string {
  if (!value) return "Earlier";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return "Earlier";
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const today = start.getTime();
  if (time >= today) return "Today";
  if (time >= today - 86_400_000) return "Yesterday";
  if (time >= today - 7 * 86_400_000) return "Previous 7 days";
  return "Earlier";
}

export function groupByRecency(rows: { item: Experiment; i: number }[]): [string, { item: Experiment; i: number }[]][] {
  const buckets = new Map<string, { item: Experiment; i: number }[]>();
  for (const row of rows) {
    const label = recencyLabel(row.item.created_at);
    const list = buckets.get(label) ?? [];
    list.push(row);
    buckets.set(label, list);
  }
  return ["Today", "Yesterday", "Previous 7 days", "Earlier"]
    .filter((label) => (buckets.get(label) ?? []).length)
    .map((label) => [label, buckets.get(label) ?? []]);
}

export function featuredModels(entries: CatalogEntry[]): CatalogEntry[] {
  const prefer = ["projectile", "shm", "doppler", "circular", "lc", "lens"];
  const picked: CatalogEntry[] = [];
  for (const id of prefer) {
    const match = entries.find((item) => item.id === id);
    if (match) picked.push(match);
  }
  if (picked.length >= 4) return picked;
  return entries.slice(0, 6);
}

export function useDismiss(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const close = () => onClose();
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [open, onClose]);
}

