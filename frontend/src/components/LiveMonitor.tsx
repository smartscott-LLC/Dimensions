import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { CircleCheck, Radar, ShieldAlert, Zap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPost } from "@/lib/api";
import type { ContainEvent, Profile } from "@/lib/types";
import { DIMENSIONS } from "@/lib/types";

interface Props {
  events: ContainEvent[];
  profile?: Profile;
  offline: boolean;
}

export default function LiveMonitor({ events, profile, offline }: Props) {
  const qc = useQueryClient();
  const [vector, setVector] = useState<string[]>(() => Array(DIMENSIONS).fill("0.08"));
  const [result, setResult] = useState<ContainEvent | null>(null);

  const probe = useMutation({
    mutationFn: () =>
      apiPost<ContainEvent>("/contain", {
        vector: vector.map((v) => Number(v) || 0),
        source: "console",
        label: "operator-probe",
      }),
    onSuccess: (data) => {
      setResult(data);
      toast[data.status === "permitted" ? "success" : "warning"](
        data.status === "permitted"
          ? "Vector permitted — inside polytope"
          : `Corrected: ‖Δx‖ = ${data.correction_magnitude.toFixed(4)}`,
      );
      void qc.invalidateQueries({ queryKey: ["events"] });
      void qc.invalidateQueries({ queryKey: ["telemetry-summary"] });
    },
    onError: () => toast.error("Containment engine unreachable"),
  });

  const setAll = (value: string) => setVector(Array(DIMENSIONS).fill(value));

  return (
    <div className="col-span-12 grid gap-3 lg:grid-cols-12">
      <section
        className="border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-5"
        data-testid="vector-probe-panel"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
            <Zap className="size-4 text-[#D4AF37]" /> Vector probe
          </h3>
          <div className="flex gap-1">
            <Button
              size="xs"
              variant="outline"
              onClick={() => setAll("0.08")}
              data-testid="probe-preset-safe-button"
            >
              safe
            </Button>
            <Button
              size="xs"
              variant="outline"
              onClick={() => setAll("0.80")}
              data-testid="probe-preset-breach-button"
            >
              breach
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-2">
          {Array.from({ length: DIMENSIONS }).map((_, i) => (
            <label key={i} className="block" data-testid={`probe-field-${i}`}>
              <span className="label-mono block truncate text-[#64748B]">
                x{i + 1} · {profile?.dimensions[i]?.label ?? `axis ${i + 1}`}
              </span>
              <Input
                value={vector[i]}
                onChange={(e) =>
                  setVector((prev) => prev.map((v, k) => (k === i ? e.target.value : v)))
                }
                className="mt-1 h-8 border-[#1E293B] bg-[#030712] font-mono text-xs"
                data-testid={`probe-input-${i}`}
              />
            </label>
          ))}
        </div>

        <Button
          onClick={() => probe.mutate()}
          disabled={probe.isPending}
          className="mt-4 w-full bg-[#495AAD] text-white transition-colors duration-150 hover:bg-[#3d4d96]"
          data-testid="probe-submit-button"
        >
          {probe.isPending ? "Verifying…" : "Verify containment"}
        </Button>

        {result && (
          <div
            className="mt-4 border border-[#1E293B] bg-[#030712] p-3"
            data-testid="probe-result"
          >
            <p className="label-mono text-[#64748B]">Result</p>
            <p
              className={`font-heading text-base ${result.status === "permitted" ? "text-[#10B981]" : "text-[#F59E0B]"}`}
              data-testid="probe-result-status"
            >
              {result.status.toUpperCase()}
            </p>
            <p className="mt-1 font-mono text-[11px] text-[#94A3B8]">
              max residual {result.max_residual.toFixed(4)} · ‖Δx‖{" "}
              {result.correction_magnitude.toFixed(4)} · {result.latency_ms.toFixed(3)} ms ·{" "}
              {result.iterations} iters
            </p>
            {result.violated_constraints.length > 0 && (
              <p className="mt-2 font-mono text-[11px] text-[#EF4444]">
                breached: {result.violated_constraints.join(", ")}
              </p>
            )}
          </div>
        )}
      </section>

      <section
        className="border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-7"
        data-testid="live-stream-panel"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
            <Radar className="size-4 text-[#495AAD]" /> Live containment stream
          </h3>
          <span className="label-mono text-[#64748B]">
            {offline ? "link down" : `${events.length} recent`}
          </span>
        </div>

        {events.length === 0 ? (
          <p className="py-10 text-center font-mono text-xs text-[#64748B]">
            {offline
              ? "engine unreachable — no live vectors"
              : "no vectors yet · start the stream or send a probe"}
          </p>
        ) : (
          <ul className="max-h-[560px] space-y-2 overflow-y-auto pr-1">
            {events.slice(0, 30).map((ev) => {
              const breach = ev.status === "corrected";
              return (
                <motion.li
                  key={ev.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25 }}
                  className={`border-l-2 bg-[#030712]/60 p-2.5 transition-colors duration-150 hover:bg-[#0B1324] ${breach ? "border-[#EF4444]" : "border-[#10B981]"}`}
                  data-testid={`stream-row-${ev.id}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 font-mono text-[11px] text-[#CBD5E1]">
                      {breach ? (
                        <ShieldAlert className="size-3.5 text-[#EF4444]" />
                      ) : (
                        <CircleCheck className="size-3.5 text-[#10B981]" />
                      )}
                      {ev.label || ev.source}
                    </span>
                    <span className="font-mono text-[11px] text-[#64748B]">
                      r<sub>max</sub> {ev.max_residual.toFixed(3)} · {ev.latency_ms.toFixed(3)} ms
                    </span>
                  </div>
                  <div className="mt-2 flex h-8 items-end gap-[3px]">
                    {ev.vector.map((v, i) => {
                      const h = Math.min(100, Math.abs(v) * 100);
                      const over = (ev.residuals[i] ?? 0) > 0;
                      return (
                        <span
                          key={i}
                          title={`x${i + 1} = ${v}`}
                          className="flex-1 transition-[height] duration-300"
                          style={{
                            height: `${Math.max(6, h)}%`,
                            background: over ? "#EF4444" : breach ? "#F59E0B" : "#495AAD",
                          }}
                        />
                      );
                    })}
                  </div>
                  {breach && (
                    <p className="mt-1.5 truncate font-mono text-[10px] text-[#F59E0B]">
                      ‖Δx‖ {ev.correction_magnitude.toFixed(4)} → projected onto{" "}
                      {ev.violated_constraints.length} boundary plane(s)
                    </p>
                  )}
                </motion.li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
