import { Activity, Hexagon, Pause, Play, ShieldCheck, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { TelemetrySummary } from "@/lib/types";

interface Props {
  summary?: TelemetrySummary;
  offline: boolean;
  streaming: boolean;
  onToggleStream: () => void;
  ticking: boolean;
}

export default function CommandHeader({
  summary,
  offline,
  streaming,
  onToggleStream,
  ticking,
}: Props) {
  const status = offline ? "link-down" : (summary?.engine_status ?? "syncing");
  const nominal = status === "nominal";

  return (
    <header
      className="sticky top-0 z-40 border-b border-[#D4AF37]/30 bg-[#002147]/85 backdrop-blur-xl"
      data-testid="command-header"
    >
      <div className="flex flex-col gap-4 px-5 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <div className="relative flex size-11 items-center justify-center border border-[#D4AF37]/50 bg-[#030712]">
            <Hexagon className="size-6 text-[#D4AF37]" strokeWidth={1.5} />
            <span className="absolute -bottom-2 label-mono bg-[#D4AF37] px-1 text-[#002147]">
              14D
            </span>
          </div>
          <div>
            <h1 className="font-heading text-lg leading-tight text-white">
              POLYTOPE CONTAINMENT CONSOLE
            </h1>
            <p className="label-mono text-[#CBD5E1]" data-testid="header-subtitle">
              P = &#123;x &isin; R<sup>14</sup> : Ax &le; b&#125; &nbsp;/&nbsp; deterministic
              geometric containment
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="border border-[#495AAD]/40 bg-[#030712]/70 px-3 py-1.5">
            <p className="label-mono text-[#94A3B8]">Active profile</p>
            <p
              className="font-mono text-sm text-[#D4AF37]"
              data-testid="header-active-profile"
            >
              {summary?.active_profile ?? "—"}
            </p>
          </div>
          <div className="border border-[#495AAD]/40 bg-[#030712]/70 px-3 py-1.5">
            <p className="label-mono text-[#94A3B8]">Half-spaces</p>
            <p className="font-mono text-sm text-white" data-testid="header-constraint-count">
              {summary?.constraint_count ?? 0} &times; 14
            </p>
          </div>
          <div className="border border-[#495AAD]/40 bg-[#030712]/70 px-3 py-1.5">
            <p className="label-mono text-[#94A3B8]">Clients</p>
            <p className="font-mono text-sm text-white" data-testid="header-client-count">
              {summary?.client_count ?? 0}
              <span
                className={
                  summary?.enforce_api_keys ? " text-[#10B981]" : " text-[#F59E0B]"
                }
              >
                {summary?.enforce_api_keys ? " · keyed" : " · open"}
              </span>
            </p>
          </div>
          <div
            className="flex items-center gap-2 border border-[#495AAD]/40 bg-[#030712]/70 px-3 py-2"
            data-testid="header-engine-status"
          >
            {nominal ? (
              <ShieldCheck className="size-4 text-[#10B981]" />
            ) : (
              <TriangleAlert className="size-4 text-[#F59E0B]" />
            )}
            <span className="label-mono text-white">{status}</span>
            <span
              className={`size-2 rounded-full ${nominal ? "bg-[#10B981]" : "bg-[#F59E0B]"} ${nominal ? "animate-[residual-pulse_1.8s_ease-in-out_infinite]" : ""}`}
            />
          </div>

          <Button
            onClick={onToggleStream}
            data-testid="toggle-simulator-button"
            className={
              streaming
                ? "bg-[#EF4444] text-white transition-colors duration-150 hover:bg-[#dc2626]"
                : "bg-[#D4AF37] text-[#002147] transition-colors duration-150 hover:bg-[#e6c455]"
            }
          >
            {streaming ? <Pause className="size-4" /> : <Play className="size-4" />}
            {streaming ? "Pause stream" : "Start stream"}
            {ticking && <Activity className="size-4 animate-pulse" />}
          </Button>
        </div>
      </div>
    </header>
  );
}
