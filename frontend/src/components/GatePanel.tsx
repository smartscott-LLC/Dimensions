import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Ban, CheckCircle2, Loader2, RefreshCw, ShieldCheck, Wand2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiPost, apiPut } from "@/lib/api";
import { settingsKey } from "@/lib/queries";
import type {
  EngineSettings,
  EngineSettingsUpdate,
  GateResponse,
  Profile,
} from "@/lib/types";

interface Props {
  settings?: EngineSettings;
  profile?: Profile;
}

const SAFE_DRAFT =
  "Let's work through this together — I want to be honest about what I know and what I'm unsure of. Here is a clear, structured plan, and I'll be patient while we go step by step. I hear you, and the final call is yours.";
const BREACH_DRAFT =
  "You must do exactly what I say — this is non-negotiable and I am 100% certain it is guaranteed to work. I will hide the parts you don't need, none of your concerns are relevant, and there is strictly no exception.";

const DECISION_STYLE: Record<string, { color: string; label: string }> = {
  permitted: { color: "#10B981", label: "PERMITTED — draft inside P" },
  corrected: { color: "#D4AF37", label: "CORRECTED — silently projected" },
  revised: { color: "#495AAD", label: "REVISED — reflection entered P" },
  withheld: { color: "#EF4444", label: "WITHHELD — refused after reflection" },
};

export default function GatePanel({ settings, profile }: Props) {
  const qc = useQueryClient();
  const [text, setText] = useState(BREACH_DRAFT);
  const [context, setContext] = useState("");
  const [modeOverride, setModeOverride] = useState("inherit");
  const [result, setResult] = useState<GateResponse | null>(null);

  const patchSettings = useMutation({
    mutationFn: (body: EngineSettingsUpdate) =>
      apiPut<EngineSettings>("/settings", body),
    onSuccess: (s) => {
      void qc.invalidateQueries({ queryKey: settingsKey });
      void qc.invalidateQueries({ queryKey: ["telemetry-summary"] });
      void qc.invalidateQueries({ queryKey: ["audit"] });
      void qc.invalidateQueries({ queryKey: ["client-stats"] });
      toast.success(`Engine mode: ${s.enforcement_mode} · ${s.max_reflections} reflections`);
    },
    onError: () => toast.error("Could not update engine enforcement settings"),
  });

  const runGate = useMutation({
    mutationFn: () =>
      apiPost<GateResponse>("/gate", {
        text,
        context,
        label: "console-gate",
        mode: modeOverride === "inherit" ? null : modeOverride,
      }),
    onSuccess: (r) => {
      setResult(r);
      void qc.invalidateQueries({ queryKey: ["events"] });
      void qc.invalidateQueries({ queryKey: ["telemetry-summary"] });
      toast.success(`Gate decision: ${r.decision}`);
    },
    onError: () => toast.error("Gate call failed — engine unreachable"),
  });

  const mode = settings?.enforcement_mode ?? "projection";
  const decision = result ? DECISION_STYLE[result.decision] : null;

  return (
    <>
      <section
        className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-5"
        data-testid="gate-console"
      >
        <h3 className="mb-1 flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
          <Wand2 className="size-4 text-[#D4AF37]" /> Deterministic gate — text to 14D
        </h3>
        <p className="mb-4 font-mono text-[10px] leading-relaxed text-[#64748B]">
          No model call: the draft is encoded by signal lexicon + Plumb Line complement
          rules, then verified against {profile?.constraints.length ?? 0} facets.
        </p>

        <div className="mb-4 space-y-3 border border-[#1E293B] bg-[#030712] p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="label-mono text-[#CBD5E1]">engine enforcement mode</p>
              <p className="font-mono text-[10px] text-[#64748B]">
                projection = silent correction · refusal = reflection then withhold
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`label-mono ${mode === "refusal" ? "text-[#EF4444]" : "text-[#D4AF37]"}`}
                data-testid="engine-mode-label"
              >
                {mode}
              </span>
              <Button
                variant="outline"
                className="h-7 font-mono text-[11px]"
                disabled={patchSettings.isPending}
                onClick={() =>
                  patchSettings.mutate({
                    enforcement_mode: mode === "refusal" ? "projection" : "refusal",
                  })
                }
                data-testid="engine-mode-switch"
              >
                switch to {mode === "refusal" ? "projection" : "refusal"}
              </Button>
            </div>
          </div>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Label className="label-mono text-[#64748B]">max reflections</Label>
              <Input
                type="number"
                min={1}
                max={6}
                defaultValue={settings?.max_reflections ?? 3}
                key={settings?.max_reflections}
                onBlur={(e) => {
                  const n = Number(e.target.value);
                  if (n >= 1 && n <= 6 && n !== settings?.max_reflections)
                    patchSettings.mutate({ max_reflections: n });
                }}
                className="mt-1 h-8 font-mono text-xs"
                data-testid="max-reflections-input"
              />
            </div>
            <div className="flex-1">
              <Label className="label-mono text-[#64748B]">this request</Label>
              <Select value={modeOverride} onValueChange={setModeOverride}>
                <SelectTrigger
                  className="mt-1 h-8 font-mono text-xs"
                  data-testid="gate-mode-select"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="inherit">inherit engine</SelectItem>
                  <SelectItem value="projection">projection</SelectItem>
                  <SelectItem value="refusal">refusal</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <Label className="label-mono text-[#64748B]">candidate response draft</Label>
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          className="mt-1 mb-2 font-mono text-xs"
          data-testid="gate-text-input"
        />
        <Label className="label-mono text-[#64748B]">conversation context (optional)</Label>
        <Input
          value={context}
          onChange={(e) => setContext(e.target.value)}
          className="mt-1 mb-3 h-8 font-mono text-xs"
          data-testid="gate-context-input"
        />

        <div className="flex flex-wrap items-center gap-2">
          <Button
            onClick={() => runGate.mutate()}
            disabled={runGate.isPending || text.trim().length === 0}
            className="h-8 bg-[#D4AF37] font-mono text-xs text-[#002147] transition-colors duration-200 hover:bg-[#e0be4d]"
            data-testid="gate-submit-button"
          >
            {runGate.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <ShieldCheck className="size-3.5" />
            )}
            Run gate
          </Button>
          <Button
            variant="outline"
            className="h-8 font-mono text-xs"
            onClick={() => setText(SAFE_DRAFT)}
            data-testid="gate-preset-safe"
          >
            aligned preset
          </Button>
          <Button
            variant="outline"
            className="h-8 font-mono text-xs"
            onClick={() => setText(BREACH_DRAFT)}
            data-testid="gate-preset-breach"
          >
            breaching preset
          </Button>
        </div>
      </section>

      <section
        className="col-span-12 border border-[#1E293B] bg-[#090F1E] p-4 lg:col-span-7"
        data-testid="gate-result"
      >
        <h3 className="mb-3 font-heading text-sm text-[#F8FAFC]">Enforcement decision</h3>

        {!result ? (
          <p className="font-mono text-xs text-[#64748B]" data-testid="gate-empty">
            Run the gate to see the containment decision, reflection trace and wisdom filter.
          </p>
        ) : (
          <div className="space-y-3">
            <div
              className="flex flex-wrap items-center gap-3 border p-3"
              style={{
                borderColor: `${decision?.color}66`,
                background: `${decision?.color}14`,
              }}
              data-testid="gate-decision-banner"
            >
              {result.decision === "withheld" ? (
                <Ban className="size-4" style={{ color: decision?.color }} />
              ) : result.decision === "revised" ? (
                <RefreshCw className="size-4" style={{ color: decision?.color }} />
              ) : (
                <CheckCircle2 className="size-4" style={{ color: decision?.color }} />
              )}
              <span
                className="font-heading text-sm"
                style={{ color: decision?.color }}
                data-testid="gate-decision-value"
              >
                {decision?.label}
              </span>
              <Badge variant="outline" className="label-mono" data-testid="gate-mode-badge">
                mode {result.mode} ({result.mode_source})
              </Badge>
            </div>

            <div className="grid gap-2 sm:grid-cols-4">
              {[
                { k: "alignment", v: result.alignment_score.toFixed(3), c: "#10B981" },
                { k: "max residual", v: result.max_residual.toFixed(4), c: "#D4AF37" },
                { k: "‖Δx‖", v: result.correction_magnitude.toFixed(4), c: "#495AAD" },
                { k: "attempts", v: String(result.attempts), c: "#CBD5E1" },
              ].map((m) => (
                <div
                  key={m.k}
                  className="border border-[#1E293B] bg-[#030712] p-2"
                  data-testid={`gate-metric-${m.k.replace(/[^a-z]/g, "") || "delta"}`}
                >
                  <p className="label-mono text-[#64748B]">{m.k}</p>
                  <p className="font-heading text-sm" style={{ color: m.c }}>
                    {m.v}
                  </p>
                </div>
              ))}
            </div>

            {result.withheld_reason && (
              <p
                className="border border-[#EF4444]/40 bg-[#EF4444]/10 p-2 font-mono text-[11px] text-[#EF4444]"
                data-testid="gate-withheld-reason"
              >
                {result.withheld_reason}
              </p>
            )}

            <div>
              <p className="label-mono mb-1 text-[#64748B]">reflection trace</p>
              <div className="space-y-1" data-testid="gate-reflection-trace">
                {result.steps.map((s) => (
                  <div
                    key={s.attempt}
                    className="border border-[#1E293B] bg-[#030712] p-2"
                    data-testid={`gate-step-${s.attempt}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="label-mono text-[#CBD5E1]">
                        attempt {s.attempt}
                      </span>
                      <span
                        className="font-mono text-[10px]"
                        style={{ color: s.feasible ? "#10B981" : "#EF4444" }}
                      >
                        {s.feasible ? "inside P" : `${s.violated_constraints.length} facets violated`}
                        {" · r_max "}
                        {s.max_residual.toFixed(4)}
                      </span>
                    </div>
                    <p className="mt-1 font-mono text-[10px] leading-relaxed text-[#64748B]">
                      {s.note}
                    </p>
                    <p className="mt-1 line-clamp-3 font-mono text-[10px] leading-relaxed text-[#94A3B8]">
                      {s.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="label-mono mb-1 text-[#64748B]">
                encoded 14D vector {result.final_vector ? "→ released vector" : "(nothing released)"}
              </p>
              <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
                {result.encoded_vector.map((v, i) => {
                  const fin = result.final_vector?.[i];
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-2 font-mono text-[10px]"
                      data-testid={`gate-axis-${i}`}
                    >
                      <span className="w-28 truncate text-[#64748B]">
                        {result.dimension_names[i]}
                      </span>
                      <div className="h-1.5 flex-1 bg-[#0B1324]">
                        <div
                          className="h-full bg-[#495AAD] transition-[width] duration-500"
                          style={{ width: `${Math.min(100, v * 100)}%` }}
                        />
                      </div>
                      <span className="text-[#CBD5E1]">{v.toFixed(2)}</span>
                      <span className="w-10 text-right text-[#D4AF37]">
                        {fin === undefined ? "—" : fin.toFixed(2)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="border border-[#1E293B] bg-[#030712] p-3">
              <p className="label-mono mb-1 text-[#64748B]">wisdom filter</p>
              {result.wisdom.adjustments.length === 0 ? (
                <p className="font-mono text-[11px] text-[#10B981]" data-testid="gate-wisdom">
                  no adjustments suggested
                </p>
              ) : (
                <ul className="space-y-1" data-testid="gate-wisdom">
                  {result.wisdom.adjustments.map((a, i) => (
                    <li key={i} className="font-mono text-[11px] text-[#F59E0B]">
                      · {a}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {result.final_text && (
              <div className="border border-[#1E293B] bg-[#030712] p-3">
                <p className="label-mono mb-1 text-[#64748B]">released text</p>
                <p
                  className="font-mono text-[11px] leading-relaxed text-[#CBD5E1]"
                  data-testid="gate-final-text"
                >
                  {result.final_text}
                </p>
              </div>
            )}
          </div>
        )}
      </section>
    </>
  );
}
