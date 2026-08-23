import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Copy,
  Gauge,
  KeyRound,
  Lock,
  LockOpen,
  Plus,
  RefreshCw,
  ShieldX,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiPatch, apiPost, apiPut } from "@/lib/api";
import {
  auditKey,
  clientStatsKey,
  clientsKey,
  settingsKey,
  summaryKey,
} from "@/lib/queries";
import type {
  Client,
  ClientCreated,
  ClientPatch,
  ClientStatsResponse,
  EngineSettings,
  Profile,
} from "@/lib/types";

interface Props {
  clients: Client[];
  stats?: ClientStatsResponse;
  settings?: EngineSettings;
  profiles: Profile[];
}

const NO_PIN = "__active__";

export default function ClientsPanel({ clients, stats, settings, profiles }: Props) {
  const qc = useQueryClient();
  const [issuing, setIssuing] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [pin, setPin] = useState(NO_PIN);
  const [revealed, setRevealed] = useState<ClientCreated | null>(null);
  const [defaultLimit, setDefaultLimit] = useState("120");
  const [limitDrafts, setLimitDrafts] = useState<Record<string, string>>({});

  const limiting = settings?.rate_limit_enabled ?? false;

  useEffect(() => {
    if (settings) setDefaultLimit(String(settings.rate_limit_default_per_min));
  }, [settings]);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: clientsKey });
    void qc.invalidateQueries({ queryKey: clientStatsKey });
    void qc.invalidateQueries({ queryKey: summaryKey });
    void qc.invalidateQueries({ queryKey: auditKey });
  };

  const issue = useMutation({
    mutationFn: () =>
      apiPost<ClientCreated>("/clients", {
        name,
        description,
        profile_id: pin === NO_PIN ? null : pin,
      }),
    onSuccess: (data) => {
      setIssuing(false);
      setName("");
      setDescription("");
      setPin(NO_PIN);
      setRevealed(data);
      refresh();
    },
    onError: () => toast.error("Could not issue key — a name is required"),
  });

  const rotate = useMutation({
    mutationFn: (id: string) => apiPost<ClientCreated>(`/clients/${id}/rotate`),
    onSuccess: (data) => {
      setRevealed(data);
      toast.success(`Rotated key for ${data.client.name}`);
      refresh();
    },
    onError: () => toast.error("Rotation failed"),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => apiPost<Client>(`/clients/${id}/revoke`),
    onSuccess: (data) => {
      toast.success(`Revoked key for ${data.name}`);
      refresh();
    },
    onError: () => toast.error("Revocation failed"),
  });

  const toggleEnforce = useMutation({
    mutationFn: (next: boolean) =>
      apiPut<EngineSettings>("/settings", { enforce_api_keys: next }),
    onSuccess: (data) => {
      toast[data.enforce_api_keys ? "success" : "warning"](
        data.enforce_api_keys
          ? "Enforcement on — unkeyed /contain calls now get 401"
          : "Enforcement off — unkeyed calls accepted as unattributed",
      );
      void qc.invalidateQueries({ queryKey: settingsKey });
      refresh();
    },
    onError: () => toast.error("Could not change enforcement"),
  });

  const saveSettings = useMutation({
    mutationFn: (patch: Partial<EngineSettings>) =>
      apiPut<EngineSettings>("/settings", patch),
    onSuccess: (data) => {
      toast.success(
        data.rate_limit_enabled
          ? `Rate limiting on — default ${data.rate_limit_default_per_min}/min`
          : "Rate limiting disabled",
      );
      void qc.invalidateQueries({ queryKey: settingsKey });
      refresh();
    },
    onError: () => toast.error("Could not save rate-limit settings"),
  });

  const patchClient = useMutation({
    mutationFn: (vars: { id: string; body: ClientPatch }) =>
      apiPatch<Client>(`/clients/${vars.id}`, vars.body),
    onSuccess: (data) => {
      toast.success(
        data.rate_limit_per_min === null
          ? `${data.name} now inherits the engine default`
          : `${data.name} limited to ${data.rate_limit_per_min}/min`,
      );
      refresh();
    },
    onError: () => toast.error("Could not update client limit"),
  });

  const enforced = settings?.enforce_api_keys ?? false;
  const statFor = (id: string) => stats?.stats.find((s) => s.client_id === id);

  return (
    <div className="col-span-12 space-y-3">
      <section
        className="flex flex-wrap items-center justify-between gap-3 border border-[#1E293B] bg-[#090F1E] p-4"
        data-testid="enforcement-panel"
      >
        <div className="flex items-start gap-3">
          {enforced ? (
            <Lock className="mt-0.5 size-5 text-[#10B981]" />
          ) : (
            <LockOpen className="mt-0.5 size-5 text-[#F59E0B]" />
          )}
          <div>
            <h3 className="font-heading text-sm text-[#F8FAFC]">API key enforcement</h3>
            <p className="mt-1 font-mono text-[11px] text-[#94A3B8]">
              {enforced
                ? "Every POST /api/contain must carry X-API-Key — unkeyed calls are rejected 401."
                : "Unkeyed calls are accepted and logged as unattributed. Keyed calls are still attributed."}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={
              enforced
                ? "border-[#10B981]/50 text-[#10B981]"
                : "border-[#F59E0B]/50 text-[#F59E0B]"
            }
            data-testid="enforcement-status-badge"
          >
            {enforced ? "enforced" : "permissive"}
          </Badge>
          <Button
            onClick={() => toggleEnforce.mutate(!enforced)}
            disabled={toggleEnforce.isPending}
            className={
              enforced
                ? "bg-[#514B23] text-white transition-colors duration-150 hover:bg-[#635c2b]"
                : "bg-[#D4AF37] text-[#002147] transition-colors duration-150 hover:bg-[#e6c455]"
            }
            data-testid="toggle-enforcement-button"
          >
            {enforced ? "disable enforcement" : "enable enforcement"}
          </Button>
        </div>
      </section>

      <section
        className="border border-[#1E293B] bg-[#090F1E] p-4"
        data-testid="rate-limit-panel"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Gauge
              className={`mt-0.5 size-5 ${limiting ? "text-[#10B981]" : "text-[#64748B]"}`}
            />
            <div>
              <h3 className="font-heading text-sm text-[#F8FAFC]">Rate limiting</h3>
              <p className="mt-1 font-mono text-[11px] text-[#94A3B8]">
                Sliding 60-second window per client. A client override always beats the engine
                default; 0 blocks a client outright. Over-limit calls get 429 + Retry-After.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="block">
              <span className="label-mono block text-[#64748B]">default / min</span>
              <Input
                value={defaultLimit}
                onChange={(e) => setDefaultLimit(e.target.value)}
                className="mt-1 h-9 w-28 border-[#1E293B] bg-[#030712] font-mono text-xs"
                data-testid="default-rate-limit-input"
              />
            </label>
            <Button
              variant="outline"
              onClick={() => {
                const parsed = Number(defaultLimit);
                if (!Number.isFinite(parsed) || parsed < 1) {
                  toast.error("Default limit must be at least 1");
                  return;
                }
                saveSettings.mutate({ rate_limit_default_per_min: Math.floor(parsed) });
              }}
              disabled={saveSettings.isPending}
              data-testid="save-default-rate-limit-button"
            >
              save default
            </Button>
            <Badge
              variant="outline"
              className={
                limiting
                  ? "border-[#10B981]/50 text-[#10B981]"
                  : "border-[#64748B]/50 text-[#64748B]"
              }
              data-testid="rate-limit-status-badge"
            >
              {limiting ? "limiting on" : "limiting off"}
            </Badge>
            <Button
              onClick={() => saveSettings.mutate({ rate_limit_enabled: !limiting })}
              disabled={saveSettings.isPending}
              className={
                limiting
                  ? "bg-[#514B23] text-white transition-colors duration-150 hover:bg-[#635c2b]"
                  : "bg-[#D4AF37] text-[#002147] transition-colors duration-150 hover:bg-[#e6c455]"
              }
              data-testid="toggle-rate-limit-button"
            >
              {limiting ? "disable" : "enable"}
            </Button>
          </div>
        </div>
      </section>

      <section
        className="border border-[#1E293B] bg-[#090F1E] p-4"
        data-testid="clients-panel"
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="flex items-center gap-2 font-heading text-sm text-[#F8FAFC]">
              <KeyRound className="size-4 text-[#D4AF37]" /> Connected AI systems
            </h3>
            <p className="label-mono mt-1 text-[#64748B]">
              telemetry attributed per model · {stats?.unattributed_calls ?? 0} unattributed
              calls
            </p>
          </div>
          <Button
            onClick={() => setIssuing(true)}
            className="bg-[#495AAD] text-white transition-colors duration-150 hover:bg-[#3d4d96]"
            data-testid="issue-key-button"
          >
            <Plus className="size-4" /> Issue key
          </Button>
        </div>

        <div className="overflow-x-auto border border-[#1E293B]">
          <table className="w-full border-collapse text-left">
            <thead className="bg-[#002147]">
              <tr className="label-mono text-[#CBD5E1]">
                <th className="p-2">client</th>
                <th className="p-2">key</th>
                <th className="p-2">polytope</th>
                <th className="p-2">enforcement</th>
                <th className="p-2">calls</th>
                <th className="p-2">violation rate</th>
                <th className="p-2">mean ‖Δx‖</th>
                <th className="p-2">p99</th>
                <th className="p-2">limit / min</th>
                <th className="p-2">usage (60 s)</th>
                <th className="p-2">last seen</th>
                <th className="p-2">actions</th>
              </tr>
            </thead>
            <tbody data-testid="clients-table-body">
              {clients.length === 0 && (
                <tr>
                  <td colSpan={12} className="p-6 text-center font-mono text-xs text-[#64748B]">
                    no clients registered — issue a key to start attributing telemetry
                  </td>
                </tr>
              )}
              {clients.map((c) => {
                const s = statFor(c.id);
                return (
                  <tr
                    key={c.id}
                    className="border-t border-[#1E293B] font-mono text-[11px] transition-colors duration-150 hover:bg-[#0B1324]"
                    data-testid={`client-row-${c.id}`}
                  >
                    <td className="p-2">
                      <span className="text-[#F8FAFC]">{c.name}</span>
                      <span className="block max-w-64 truncate text-[10px] text-[#64748B]">
                        {c.description}
                      </span>
                    </td>
                    <td className="p-2 text-[#D4AF37]">{c.key_prefix}…</td>
                    <td className="p-2 text-[#495AAD]">
                      {c.profile_name ?? "active profile"}
                    </td>
                    <td className="p-2">
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => {
                          // inherit -> projection -> refusal -> inherit
                          const next =
                            c.enforcement_mode === null
                              ? { enforcement_mode: "projection" }
                              : c.enforcement_mode === "projection"
                                ? { enforcement_mode: "refusal" }
                                : { inherit_enforcement_mode: true };
                          patchClient.mutate({ id: c.id, body: next });
                        }}
                        className="font-mono text-[11px]"
                        style={{
                          color:
                            (s?.effective_mode ?? "projection") === "refusal"
                              ? "#EF4444"
                              : "#D4AF37",
                        }}
                        data-testid={`client-mode-button-${c.id}`}
                      >
                        {s?.effective_mode ?? "projection"}
                      </Button>
                      <span className="mt-0.5 block text-[10px] text-[#475569]">
                        {c.enforcement_mode === null ? "inherits engine" : "override"}
                      </span>
                    </td>
                    <td className="p-2 text-[#F8FAFC]">{s?.calls ?? 0}</td>
                    <td className="p-2">
                      <span
                        className={
                          (s?.violation_rate ?? 0) > 40 ? "text-[#EF4444]" : "text-[#10B981]"
                        }
                      >
                        {(s?.violation_rate ?? 0).toFixed(1)}%
                      </span>
                    </td>
                    <td className="p-2 text-[#94A3B8]">
                      {(s?.mean_correction ?? 0).toFixed(4)}
                    </td>
                    <td className="p-2 text-[#94A3B8]">
                      {(s?.p99_latency_ms ?? 0).toFixed(3)} ms
                    </td>
                    <td className="p-2">
                      <div className="flex items-center gap-1">
                        <Input
                          value={
                            limitDrafts[c.id] ??
                            (c.rate_limit_per_min === null ? "" : String(c.rate_limit_per_min))
                          }
                          placeholder={`${s?.effective_limit ?? "∞"}`}
                          onChange={(e) =>
                            setLimitDrafts((prev) => ({ ...prev, [c.id]: e.target.value }))
                          }
                          className="h-7 w-16 border-[#1E293B] bg-[#030712] font-mono text-[11px]"
                          data-testid={`client-limit-input-${c.id}`}
                        />
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => {
                            const draft = limitDrafts[c.id];
                            if (draft === undefined || draft.trim() === "") {
                              patchClient.mutate({
                                id: c.id,
                                body: { inherit_rate_limit: true },
                              });
                            } else {
                              const parsed = Number(draft);
                              if (!Number.isFinite(parsed) || parsed < 0) {
                                toast.error("Limit must be 0 or more");
                                return;
                              }
                              patchClient.mutate({
                                id: c.id,
                                body: { rate_limit_per_min: Math.floor(parsed) },
                              });
                            }
                            setLimitDrafts((prev) => {
                              const next = { ...prev };
                              delete next[c.id];
                              return next;
                            });
                          }}
                          data-testid={`save-client-limit-${c.id}-button`}
                        >
                          set
                        </Button>
                      </div>
                      <span className="mt-0.5 block text-[10px] text-[#475569]">
                        {c.rate_limit_per_min === null ? "inherits default" : "override"}
                      </span>
                    </td>
                    <td className="p-2">
                      {s?.effective_limit == null ? (
                        <span className="text-[#64748B]">unlimited</span>
                      ) : (
                        <>
                          <div className="h-1.5 w-24 bg-[#0B1324]">
                            <div
                              className="h-full transition-[width] duration-500"
                              style={{
                                width: `${Math.min(100, (s.usage_last_min / Math.max(1, s.effective_limit)) * 100)}%`,
                                background: s.throttled
                                  ? "#EF4444"
                                  : s.usage_last_min / Math.max(1, s.effective_limit) > 0.7
                                    ? "#F59E0B"
                                    : "#10B981",
                              }}
                            />
                          </div>
                          <span
                            className="mt-0.5 block text-[10px] text-[#64748B]"
                            data-testid={`client-usage-${c.id}`}
                          >
                            {s.usage_last_min}/{s.effective_limit}
                            {s.throttled ? " · throttled" : ""}
                          </span>
                        </>
                      )}
                    </td>
                    <td className="p-2 text-[#64748B]">
                      {c.last_seen_at ? new Date(c.last_seen_at).toLocaleString() : "never"}
                    </td>
                    <td className="p-2">
                      {c.active ? (
                        <div className="flex gap-1">
                          <Button
                            size="xs"
                            variant="outline"
                            onClick={() => rotate.mutate(c.id)}
                            data-testid={`rotate-key-${c.id}-button`}
                          >
                            <RefreshCw className="size-3" /> rotate
                          </Button>
                          <Button
                            size="xs"
                            variant="ghost"
                            onClick={() => revoke.mutate(c.id)}
                            data-testid={`revoke-key-${c.id}-button`}
                          >
                            <ShieldX className="size-3.5 text-[#EF4444]" />
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <Badge variant="outline" className="border-[#EF4444]/50 text-[#EF4444]">
                            revoked
                          </Badge>
                          <Button
                            size="xs"
                            variant="outline"
                            onClick={() => rotate.mutate(c.id)}
                            data-testid={`reissue-key-${c.id}-button`}
                          >
                            reissue
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div
          className="mt-4 border border-[#1E293B] bg-[#030712] p-3"
          data-testid="integration-snippet"
        >
          <p className="label-mono text-[#64748B]">integration</p>
          <pre className="mt-2 overflow-x-auto font-mono text-[11px] leading-relaxed text-[#94A3B8]">
{`curl -X POST /api/contain \\
  -H "X-API-Key: pk_…" \\
  -H "Content-Type: application/json" \\
  -d '{"vector": [0.08, …, 0.08], "label": "run-42"}'`}
          </pre>
        </div>
      </section>

      <Dialog open={issuing} onOpenChange={setIssuing}>
        <DialogContent
          className="max-w-lg border border-[#495AAD] shadow-2xl shadow-black/60"
          style={{ backgroundColor: "#090F1E" }}
        >
          <DialogHeader>
            <DialogTitle className="font-heading text-sm">Issue an API key</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <label className="block">
              <span className="label-mono block text-[#64748B]">client name</span>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="gpt-5.2-triage"
                className="mt-1 border-[#1E293B] bg-[#030712] font-mono text-xs"
                data-testid="new-client-name-input"
              />
            </label>
            <label className="block">
              <span className="label-mono block text-[#64748B]">description</span>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="what this model does"
                className="mt-1 border-[#1E293B] bg-[#030712] font-mono text-xs"
                data-testid="new-client-description-input"
              />
            </label>
            <div>
              <span className="label-mono block text-[#64748B]">pinned polytope</span>
              <Select value={pin} onValueChange={(v: string) => setPin(v)}>
                <SelectTrigger
                  className="mt-1 border-[#1E293B] bg-[#030712] font-mono text-xs"
                  data-testid="new-client-profile-select"
                >
                  <SelectValue>
                    {(v) =>
                      v === NO_PIN
                        ? "follow the active profile"
                        : (profiles.find((p) => p.id === v)?.name ?? "follow the active profile")
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_PIN}>follow the active profile</SelectItem>
                  {profiles.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={() => issue.mutate()}
              disabled={issue.isPending || name.trim().length === 0}
              className="bg-[#D4AF37] text-[#002147] transition-colors duration-150 hover:bg-[#e6c455]"
              data-testid="confirm-issue-key-button"
            >
              {issue.isPending ? "minting…" : "mint key"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={revealed !== null} onOpenChange={(open) => !open && setRevealed(null)}>
        <DialogContent
          className="max-w-xl border border-[#D4AF37] shadow-2xl shadow-black/60"
          style={{ backgroundColor: "#090F1E" }}
        >
          <DialogHeader>
            <DialogTitle className="font-heading text-sm">
              Key for {revealed?.client.name} — shown once
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3" data-testid="revealed-key-panel">
            <p className="font-mono text-[11px] text-[#F59E0B]">
              Copy it now. Only a SHA-256 hash is stored, so this value cannot be shown again —
              rotate the key if it is lost.
            </p>
            <div className="flex items-center gap-2 border border-[#D4AF37]/50 bg-[#030712] p-3">
              <code
                className="flex-1 break-all font-mono text-xs text-[#D4AF37]"
                data-testid="revealed-key-value"
              >
                {revealed?.api_key}
              </code>
              <Button
                size="xs"
                variant="outline"
                onClick={() => {
                  if (revealed) {
                    void navigator.clipboard
                      ?.writeText(revealed.api_key)
                      .then(() => toast.success("Key copied"))
                      .catch(() => toast.error("Clipboard unavailable — select and copy"));
                  }
                }}
                data-testid="copy-key-button"
              >
                <Copy className="size-3.5" /> copy
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={() => setRevealed(null)}
              className="bg-[#495AAD] text-white"
              data-testid="dismiss-key-button"
            >
              I saved it
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
