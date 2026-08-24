import type { ReactElement } from "react";
import type { PlotPayload } from "./types";

const TEAL = "#10a37f";
const MUTED = "#8e8e8e";

function bounds(plot: PlotPayload) {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const s of plot.series) {
    for (let i = 0; i < s.x.length; i += 1) {
      if (Number.isFinite(s.x[i]) && Number.isFinite(s.y[i])) {
        xs.push(s.x[i]);
        ys.push(s.y[i]);
      }
    }
  }
  if (plot.envelope) {
    for (let i = 0; i < plot.envelope.x.length; i += 1) {
      if (Number.isFinite(plot.envelope.x[i])) xs.push(plot.envelope.x[i]);
      if (Number.isFinite(plot.envelope.y_lo[i])) ys.push(plot.envelope.y_lo[i]);
      if (Number.isFinite(plot.envelope.y_hi[i])) ys.push(plot.envelope.y_hi[i]);
    }
  }
  let minX = Math.min(...xs);
  let maxX = Math.max(...xs);
  let minY = Math.min(...ys);
  let maxY = Math.max(...ys);
  if (!Number.isFinite(minX) || minX === maxX) {
    minX = 0;
    maxX = 1;
  }
  if (!Number.isFinite(minY) || minY === maxY) {
    minY = 0;
    maxY = 1;
  }
  const dataMinY = minY;
  if (plot.kind === "trajectory" && minY >= 0) minY = 0;
  const padX = (maxX - minX) * 0.04 || 1;
  const padY = (maxY - minY) * 0.1 || 1;
  minX -= padX;
  maxX += padX;
  if (minY !== 0) minY -= padY;
  maxY += padY;
  if (dataMinY >= 0) minY = Math.max(0, minY);
  return { minX, maxX, minY, maxY };
}

function formatTick(value: number): string {
  if (!Number.isFinite(value)) return "";
  const abs = Math.abs(value);
  if (abs !== 0 && (abs >= 1e4 || abs < 1e-3)) return value.toExponential(1);
  if (abs >= 100) return String(Math.round(value));
  return String(Number(value.toPrecision(3)));
}

function pointsOf(series: PlotPayload["series"][number], px: (x: number, y: number) => string) {
  const parts: string[] = [];
  for (let i = 0; i < series.x.length; i += 1) {
    if (!Number.isFinite(series.x[i]) || !Number.isFinite(series.y[i])) continue;
    parts.push(px(series.x[i], series.y[i]));
  }
  return parts.join(" ");
}

export function Plot({ plot }: { plot: PlotPayload }) {
  if (!plot.series?.length && !plot.envelope?.x?.length) {
    return <p className="text-slate text-[15px]">No figure for this model.</p>;
  }
  const width = 920;
  const height = 320;
  const padL = 64;
  const padR = 16;
  const padT = 12;
  const padB = 28;
  const { minX, maxX, minY, maxY } = bounds(plot);
  const px = (x: number, y: number) => {
    const X = padL + ((x - minX) / (maxX - minX)) * (width - padL - padR);
    const Y = height - padB - ((y - minY) / (maxY - minY)) * (height - padT - padB);
    return `${X.toFixed(1)},${Y.toFixed(1)}`;
  };

  let envelope: ReactElement | null = null;
  if (plot.envelope?.x?.length) {
    const hi = plot.envelope.x.map((x, i) => px(x, plot.envelope!.y_hi[i]));
    const lo = [...plot.envelope.x].reverse().map((x, i) => px(x, [...plot.envelope!.y_lo].reverse()[i]));
    envelope = <path d={`M ${[...hi, ...lo].join(" L ")} Z`} fill={TEAL} fillOpacity="0.12" />;
  }

  return (
    <figure className="m-0">
      <p className="text-[12px] text-slate mb-1">{plot.y_label}</p>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img" aria-label={`${plot.x_label} versus ${plot.y_label}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const y = padT + frac * (height - padT - padB);
          return <line key={frac} x1={padL} y1={y} x2={width - padR} y2={y} stroke="currentColor" className="text-[#ececec] dark:text-white/12" />;
        })}
        {envelope}
        {plot.series.slice(0, 8).map((s, i) => (
          <polyline
            key={s.id}
            fill="none"
            stroke={TEAL}
            strokeOpacity={i === 0 ? 1 : 0.4}
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={pointsOf(s, px)}
          />
        ))}
        <text x={padL - 8} y={padT + 4} textAnchor="end" fill={MUTED} fontSize="11" fontFamily="Inter, sans-serif">
          {formatTick(maxY)}
        </text>
        <text x={padL - 8} y={height - padB} textAnchor="end" fill={MUTED} fontSize="11" fontFamily="Inter, sans-serif">
          {formatTick(minY)}
        </text>
        <text x={padL} y={height - 6} fill={MUTED} fontSize="11" fontFamily="Inter, sans-serif">
          {formatTick(minX)}
        </text>
        <text x={width - padR} y={height - 6} textAnchor="end" fill={MUTED} fontSize="11" fontFamily="Inter, sans-serif">
          {formatTick(maxX)}
        </text>
      </svg>
      <p className="text-[12px] text-slate text-center mt-1">{plot.x_label}</p>
      {plot.secondary ? (
        <div className="mt-10">
          <Plot plot={plot.secondary} />
        </div>
      ) : null}
    </figure>
  );
}
