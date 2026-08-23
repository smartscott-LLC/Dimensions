import type { LucideIcon } from "lucide-react";
import { Crosshair, Gauge, ShieldAlert, Sigma, Timer } from "lucide-react";
import type { TelemetrySummary } from "@/lib/types";

interface Props {
  summary?: TelemetrySummary;
  offline: boolean;
}

interface Tile {
  key: string;
  label: string;
  value: string;
  sub: string;
  icon: LucideIcon;
  tone: string;
}

export default function KpiBar({ summary, offline }: Props) {
  const dash = offline || !summary;
  const tiles: Tile[] = [
    {
      key: "verifications",
      label: "Verifications",
      value: dash ? "—" : summary.total_events.toLocaleString(),
      sub: dash ? "awaiting engine" : `${summary.permitted.toLocaleString()} permitted`,
      icon: Sigma,
      tone: "#495AAD",
    },
    {
      key: "violation-rate",
      label: "Violation rate",
      value: dash ? "—" : `${summary.violation_rate}%`,
      sub: dash ? "awaiting engine" : `${summary.corrected.toLocaleString()} corrected`,
      icon: ShieldAlert,
      tone: "#EF4444",
    },
    {
      key: "mean-correction",
      label: "Mean ‖Δx‖",
      value: dash ? "—" : summary.mean_correction.toFixed(4),
      sub: dash ? "awaiting engine" : `max ${summary.max_correction.toFixed(3)}`,
      icon: Crosshair,
      tone: "#D4AF37",
    },
    {
      key: "p99-latency",
      label: "p99 latency",
      value: dash ? "—" : `${summary.p99_latency_ms.toFixed(3)} ms`,
      sub: dash ? "awaiting engine" : `p50 ${summary.p50_latency_ms.toFixed(3)} ms`,
      icon: Timer,
      tone: "#10B981",
    },
    {
      key: "throughput",
      label: "Throughput",
      value: dash ? "—" : `${summary.throughput_per_min.toFixed(1)}/min`,
      sub: dash ? "awaiting engine" : "trailing 10 min",
      icon: Gauge,
      tone: "#514B23",
    },
  ];

  return (
    <div
      className="col-span-12 grid grid-cols-2 gap-3 md:grid-cols-5"
      data-testid="kpi-bar"
    >
      {tiles.map((tile) => (
        <div
          key={tile.key}
          data-testid={`kpi-${tile.key}`}
          className="group relative overflow-hidden border border-[#1E293B] bg-[#090F1E] p-4 transition-colors duration-200 hover:border-[#D4AF37]/50"
        >
          <div
            className="absolute inset-x-0 top-0 h-px opacity-60"
            style={{ background: tile.tone }}
          />
          <div className="flex items-start justify-between">
            <p className="label-mono text-[#94A3B8]">{tile.label}</p>
            <tile.icon className="size-4 shrink-0 transition-transform duration-200 group-hover:scale-110" style={{ color: tile.tone }} />
          </div>
          <p
            className="mt-3 font-heading text-2xl text-[#F8FAFC]"
            data-testid={`kpi-${tile.key}-value`}
          >
            {tile.value}
          </p>
          <p className="mt-1 font-mono text-[11px] text-[#64748B]">{tile.sub}</p>
        </div>
      ))}
    </div>
  );
}
